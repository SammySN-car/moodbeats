import re
import json
import requests
import torch
from rank_bm25 import BM25Okapi
from config import settings
from ml.embedding_service import (
    get_device,
    get_batch_embeddings_tensor,
    neural_cross_rerank,
    build_song_profile_text
)

def _normalize_song_key(title: str, artist: str = "") -> str:
    """Normalize title and artist to eliminate duplicate remixes, slowed/sped-up versions, and edits."""
    # Remove bracketed/parenthetical text (e.g. (Remix), [Slowed + Reverb], (feat. X))
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', title)
    t = re.sub(r'[-–—].*$', '', t)
    t = re.sub(r'[^\w\s]', '', t).strip().lower()

    # Normalize artist
    a = re.sub(r'[\(\[\{].*?[\)\]\}]', '', artist)
    a = re.sub(r'[^\w\s]', '', a).strip().lower()
    a_first = a.split()[0] if a else ""

    return f"{t}_{a_first}"

def pytorch_database_rag_search(user_prompt: str, library_songs: list) -> list:
    """
    Pure PyTorch Database-Driven RAG Search on Actual User Library Songs:
    1. Dense Bi-Encoder Matrix Dot-Product (384d)
    2. Sparse BM25 Lexical Keyword Matching
    3. Convex Hybrid Fusion (0.65 Dense + 0.35 Sparse)
    4. Neural Cross-Encoder Reranking (< 50ms)
    """
    if not library_songs:
        return []

    device = get_device()
    prompt_tensor = get_batch_embeddings_tensor([user_prompt])

    # 1. Multi-Aspect Documents from actual DB songs
    lib_docs = []
    for s in library_songs:
        if s.embedding:
            doc = f"Track: '{s.title}' by {s.artist}. Mood: {s.mood}. Tempo: {s.tempo} BPM. Energy: {s.energy}."
        else:
            doc = build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
        lib_docs.append(doc)

    # 2. Dense Tensor Matrix Multiplication (Cosine Similarity)
    if all(getattr(s, 'embedding', None) for s in library_songs):
        try:
            lib_vectors = torch.tensor([json.loads(s.embedding) for s in library_songs], dtype=torch.float32, device=device)
        except Exception:
            lib_vectors = get_batch_embeddings_tensor(lib_docs)
    else:
        lib_vectors = get_batch_embeddings_tensor(lib_docs)

    dense_scores = torch.matmul(lib_vectors, prompt_tensor.T).squeeze(-1)

    # 3. Sparse BM25 Lexical Search
    bm25_lib = BM25Okapi([d.lower().split() for d in lib_docs])
    sparse_raw = torch.tensor(bm25_lib.get_scores(user_prompt.lower().split()), dtype=torch.float32, device=device)
    max_sparse = torch.max(sparse_raw)
    sparse_scores = sparse_raw / (max_sparse if max_sparse > 0 else 1.0)

    # 4. Hybrid Convex Fusion
    hybrid_scores = 0.65 * dense_scores + 0.35 * sparse_scores
    top_k = min(settings.RERANKER_TOP_K, len(library_songs))
    topk_scores, topk_indices = torch.topk(hybrid_scores, k=top_k)

    candidate_songs = [library_songs[i] for i in topk_indices.tolist()]
    candidate_docs = [lib_docs[i] for i in topk_indices.tolist()]

    # 5. PyTorch Neural Cross-Encoder Reranking
    cross_scores = neural_cross_rerank(user_prompt, candidate_docs)
    rerank_indices = sorted(range(len(cross_scores)), key=lambda i: cross_scores[i], reverse=True)

    # Adaptive Threshold
    threshold = -6.0 if len(library_songs) <= 5 else -4.0
    ranked_library_songs = [(cross_scores[i], candidate_songs[i]) for i in rerank_indices if cross_scores[i] > threshold]

    # If library is small and nothing passed threshold, return the single closest relative match
    if not ranked_library_songs and len(candidate_songs) > 0 and len(library_songs) <= 5:
        best_idx = rerank_indices[0]
        ranked_library_songs = [(cross_scores[best_idx], candidate_songs[best_idx])]

    return ranked_library_songs

def _clean_track_title(title: str) -> str:
    """Clean Ollama prefix formatting like 'Song 1: Tokyo Drift' -> 'Tokyo Drift'."""
    return re.sub(r'^(Song\s*\d+:?|\d+[\.\)]\s*)', '', title.strip()).strip(' "\'')

def enrich_discovered_songs(new_song_list: list) -> list[dict]:
    """Auto-verifies against official streaming databases, deduplicates, and fetches artwork."""
    enriched = []
    seen_keys = set()

    for rec in new_song_list:
        raw_title = rec.get("title", "")
        title = _clean_track_title(raw_title)
        artist = rec.get("artist", "").strip(' "\'')
        if not title:
            continue

        norm_key = _normalize_song_key(title, artist)
        if norm_key in seen_keys:
            continue

        art_url = rec.get("album_art_url")
        preview_url = rec.get("preview_url")

        # Verify on official music database
        if not art_url or not preview_url:
            try:
                res = requests.get(
                    "https://itunes.apple.com/search",
                    params={"term": f"{title} {artist}", "entity": "song", "limit": 1},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=3
                )
                if res.status_code == 200 and res.json().get("results"):
                    item = res.json()["results"][0]
                    title = item.get("trackName", title)
                    artist = item.get("artistName", artist)
                    art_url = item.get("artworkUrl100")
                    preview_url = item.get("previewUrl")
            except Exception:
                pass

        # Re-check normalized key after official title resolution
        final_key = _normalize_song_key(title, artist)
        if final_key in seen_keys:
            continue

        # Only include tracks verified in official streaming database
        if art_url:
            seen_keys.add(norm_key)
            seen_keys.add(final_key)
            enriched.append({
                "title": title,
                "artist": artist,
                "album_art_url": art_url,
                "preview_url": preview_url,
                "spotify_url": f"https://open.spotify.com/search/{title} {artist}",
                "spotify_id": f"disc_{abs(hash(title))}"
            })
    return enriched

def _get_dynamic_public_discoveries(user_prompt: str, limit: int = 50, existing_keys: set = None) -> list[dict]:
    """Dynamically search verified official releases for up to 50 vibe-matching tracks without duplicates."""
    clean_query = re.sub(r'[^\w\s]', '', user_prompt)
    words = [w for w in clean_query.split() if len(w) > 2]
    url = "https://itunes.apple.com/search"
    headers = {"User-Agent": "Mozilla/5.0"}

    results = []
    seen = set(existing_keys) if existing_keys else set()

    # Search queries to pull 50 diverse, unique tracks
    search_queries = [
        " ".join(words[:4]),
        f"{words[0]} {words[-1]}" if len(words) > 1 else words[0],
        f"{words[0]} top hits" if words else "top hits",
        f"{words[0]} music" if words else "pop"
    ]

    for sq in search_queries:
        if len(results) >= limit:
            break
        try:
            r = requests.get(url, params={"term": sq, "entity": "song", "limit": limit}, headers=headers, timeout=5)
            if r.status_code == 200:
                for item in r.json().get("results", []):
                    title, artist = item.get("trackName", ""), item.get("artistName", "")
                    art_url = item.get("artworkUrl100")
                    if title and artist and art_url:
                        k = _normalize_song_key(title, artist)
                        if k not in seen:
                            seen.add(k)
                            results.append({
                                "title": title,
                                "artist": artist,
                                "album_art_url": art_url,
                                "preview_url": item.get("previewUrl")
                            })
                            if len(results) >= limit:
                                break
        except Exception:
            continue

    return results[:limit]

def generate_ai_dj_synthesis(user_prompt: str, library_songs: list) -> dict:
    """Ollama AI DJ: Arranges library songs and dynamically recommends 50 verified official songs with 0 duplicates."""
    valid_ids = [s.id for _, s in library_songs]
    tracks_str = "\n".join([
        f"- ID {s.id}: '{s.title}' by {s.artist} (Mood: {s.mood}, Tempo: {round(s.tempo or 0)} BPM, Energy: {round((s.energy or 0)*100)}%)"
        for _, s in library_songs
    ])

    # Track library song keys so they are never duplicated in recommended tracks
    library_keys = {_normalize_song_key(s.title, s.artist or "") for _, s in library_songs}

    dynamic_discoveries = _get_dynamic_public_discoveries(user_prompt, limit=settings.MAX_NEW_DISCOVERIES, existing_keys=library_keys)

    fallback_result = {
        "playlist_title": f"Vibe: {user_prompt[:25].capitalize()}",
        "ai_dj_note": f"A curated set matching your vibe: '{user_prompt}'.",
        "ordered_library_ids": valid_ids[:settings.MAX_PLAYLIST_SONGS],
        "new_song_recommendations": dynamic_discoveries
    }

    prompt = f"""You are MoodBeats AI DJ, a master music curator.
User requested this vibe: "{user_prompt}"

Matching songs in user's library:
{tracks_str if tracks_str else "None"}

Perform two tasks:
1. Select and arrange library songs in optimal sequence using ONLY valid IDs: {valid_ids}.
2. Zero-shot recommend 4-5 REAL famous iconic songs that capture this exact vibe.

Respond in valid JSON ONLY:
{{
  "playlist_title": "Creative 2-4 word playlist title",
  "ai_dj_note": "2-sentence curator note explaining the mood progression and vibe",
  "ordered_library_ids": {valid_ids[:settings.MAX_PLAYLIST_SONGS]},
  "new_song_recommendations": [
    {{"title": "Real Song Title 1", "artist": "Real Artist 1"}},
    {{"title": "Real Song Title 2", "artist": "Real Artist 2"}}
  ]
}}"""

    try:
        resp = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "num_predict": settings.OLLAMA_MAX_TOKENS,
                    "temperature": 0.7
                }
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            parsed = json.loads(resp.json().get("response", "{}"))
            raw_ids = parsed.get("ordered_library_ids", [])
            cleaned_ids = [sid for sid in raw_ids if sid in valid_ids and raw_ids.count(sid) == 1]
            raw_recs = parsed.get("new_song_recommendations", [])

            # Filter and deduplicate LLM raw seeds
            seen_recs = set(library_keys)
            valid_recs = []
            for r in raw_recs:
                t = _clean_track_title(r.get("title", ""))
                a = r.get("artist", "")
                if t and "song 1" not in t.lower():
                    k = _normalize_song_key(t, a)
                    if k not in seen_recs:
                        seen_recs.add(k)
                        valid_recs.append({"title": t, "artist": a})

            # Merge LLM seeds + dynamic discoveries with deduplication
            merged_recs = list(valid_recs)
            for d in dynamic_discoveries:
                k = _normalize_song_key(d["title"], d.get("artist", ""))
                if k not in seen_recs:
                    seen_recs.add(k)
                    merged_recs.append(d)
                if len(merged_recs) >= settings.MAX_NEW_DISCOVERIES:
                    break

            return {
                "playlist_title": parsed.get("playlist_title", fallback_result["playlist_title"]),
                "ai_dj_note": parsed.get("ai_dj_note", fallback_result["ai_dj_note"]),
                "ordered_library_ids": cleaned_ids if cleaned_ids else valid_ids[:settings.MAX_PLAYLIST_SONGS],
                "new_song_recommendations": merged_recs[:settings.MAX_NEW_DISCOVERIES]
            }
    except Exception:
        pass
    return fallback_result