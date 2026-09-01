import json
import torch
import torch.nn.functional as F
from ml.embedding_service import (
    get_text_embedding_tensor,
    get_batch_embeddings_tensor,
    get_device,
    neural_cross_rerank,
    build_song_profile_text
)
from ml.query_planner import decompose_query, normalize_mood
from rank_bm25 import BM25Okapi
from config import settings
import requests
from typing import List, Dict, Optional, Tuple

device = get_device()


def reciprocal_rank_fusion(
    dense_scores: torch.Tensor,
    sparse_scores: torch.Tensor,
    k: int = None
) -> torch.Tensor:
    """Combine dense and sparse scores using Reciprocal Rank Fusion."""
    if k is None:
        k = settings.RRF_K

    # argsort gives indices that would sort; inverse_argsort gives ranks
    dense_ranks = torch.argsort(torch.argsort(dense_scores, descending=True)) + 1
    sparse_ranks = torch.argsort(torch.argsort(sparse_scores, descending=True)) + 1

    dense_rrf = 1.0 / (k + dense_ranks.float())
    sparse_rrf = 1.0 / (k + sparse_ranks.float())

    return dense_rrf + sparse_rrf


def _metadata_filter(
    library_songs: list,
    mood: str = None,
    tempo_range: list = None,
    energy_range: list = None
) -> list:
    """Filter library songs by metadata constraints. Songs with missing metadata pass through."""
    normalized_mood = normalize_mood(mood) if mood else None

    filtered_indices = []
    for i, s in enumerate(library_songs):
        if normalized_mood and s.mood:
            song_mood = normalize_mood(s.mood)
            if song_mood and song_mood != normalized_mood:
                continue
        if tempo_range and s.tempo:
            if not (tempo_range[0] <= s.tempo <= tempo_range[1]):
                continue
        if energy_range and s.energy:
            if not (energy_range[0] <= s.energy <= energy_range[1]):
                continue
        filtered_indices.append(i)

    return filtered_indices


def mmr_rerank(
    candidates: list,
    candidate_embeddings: torch.Tensor,
    query_embedding: torch.Tensor,
    lambda_param: float = None,
    top_k: int = None
) -> list:
    """Apply Maximal Marginal Relevance to diversify the final playlist."""
    if lambda_param is None:
        lambda_param = settings.MMR_LAMBDA
    if top_k is None:
        top_k = settings.TOP_K

    if len(candidates) <= top_k:
        return candidates

    query_sim = F.cosine_similarity(query_embedding, candidate_embeddings, dim=1)

    selected = []
    remaining = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        if not remaining:
            break

        best_score = -float('inf')
        best_idx = remaining[0]

        for idx in remaining:
            relevance = query_sim[idx].item()

            if selected:
                selected_embs = candidate_embeddings[selected]
                candidate_emb = candidate_embeddings[idx].unsqueeze(0)
                sim_to_selected = F.cosine_similarity(candidate_emb, selected_embs, dim=1).max().item()
            else:
                sim_to_selected = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidates[i] for i in selected]


def pytorch_database_rag_search(
    user_prompt: str,
    library_songs: list,
    planner_plan: dict = None,
    top_k: int = None,
    taste_vector: list = None
) -> list:
    """Hybrid RAG search: Dense + Sparse -> RRF Fusion -> Cross-Encoder Rerank -> MMR."""
    if top_k is None:
        top_k = settings.TOP_K

    if not library_songs:
        return []

    # Build planner context if available
    if planner_plan is None:
        plan = decompose_query(user_prompt)
    else:
        plan = planner_plan

    # Use HyDE description if available, otherwise fall back to raw query
    embedding_query = plan["hyde_description"] if plan["hyde_description"] else user_prompt
    print(f"[RAG] Embedding query: \"{embedding_query[:80]}...\"")

    # Pre-filter by metadata before expensive vector search
    filter_indices = _metadata_filter(
        library_songs,
        mood=plan.get("mood"),
        tempo_range=plan.get("tempo_range"),
        energy_range=plan.get("energy_range")
    )

    if len(filter_indices) == 0:
        print("[RAG] Metadata filter removed all songs - falling back to unfiltered")
        filtered_songs = library_songs
        filter_indices = list(range(len(library_songs)))
    else:
        filtered_songs = [library_songs[i] for i in filter_indices]
        print(f"[RAG] Metadata filter: {len(library_songs)} -> {len(filtered_songs)} candidates")

    lib_docs = []
    for s in filtered_songs:
        if getattr(s, 'embedding', None):
            doc = f"Track: '{s.title}' by {s.artist}. Mood: {s.mood}. Tempo: {s.tempo} BPM. Energy: {s.energy}."
        else:
            doc = build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
        lib_docs.append(doc)

    # Dense retrieval: bi-encoder cosine similarity
    prompt_tensor = get_batch_embeddings_tensor([embedding_query])

    # Blend taste vector if available: final = (1 - weight) * query + weight * taste
    if taste_vector is not None:
        taste_tensor = torch.tensor([taste_vector], dtype=torch.float32, device=device)
        weight = settings.TASTE_WEIGHT
        prompt_tensor = (1 - weight) * prompt_tensor + weight * taste_tensor
        print(f"[RAG] Taste blending applied (weight={weight})")

    if all(getattr(s, 'embedding', None) for s in filtered_songs):
        try:
            lib_vectors = torch.tensor(
                [json.loads(s.embedding) for s in filtered_songs],
                dtype=torch.float32, device=device
            )
        except Exception:
            lib_vectors = get_batch_embeddings_tensor(lib_docs)
    else:
        lib_vectors = get_batch_embeddings_tensor(lib_docs)

    dense_scores = torch.matmul(lib_vectors, prompt_tensor.T).squeeze(-1)
    print(f"[RAG] Dense scores - min: {dense_scores.min():.4f}, max: {dense_scores.max():.4f}")

    # Sparse retrieval: BM25 lexical matching
    all_keywords = " ".join(plan.get("keywords", []))
    bm25_query = f"{user_prompt} {all_keywords}"
    tokenized_query = bm25_query.lower().split()
    tokenized_corpus = [doc.lower().split() for doc in lib_docs]

    if tokenized_corpus:
        bm25 = BM25Okapi(tokenized_corpus)
        sparse_scores = torch.tensor(
            bm25.get_scores(tokenized_query),
            dtype=torch.float32, device=device
        )
    else:
        sparse_scores = torch.zeros(len(filtered_songs), device=device)

    print(f"[RAG] Sparse scores - min: {sparse_scores.min():.4f}, max: {sparse_scores.max():.4f}")

    # Reciprocal rank fusion
    rrf_scores = reciprocal_rank_fusion(dense_scores, sparse_scores)
    print(f"[RAG] RRF scores - min: {rrf_scores.min():.6f}, max: {rrf_scores.max():.6f}")

    # Cross-encoder reranking on top 2x candidates to allow MMR selection
    rrf_top_k = min(top_k * 2, len(filtered_songs))
    rrf_top_indices = torch.argsort(rrf_scores, descending=True)[:rrf_top_k]

    rerank_docs = [lib_docs[i] for i in rrf_top_indices]
    cross_scores = neural_cross_rerank(user_prompt, rerank_docs)
    cross_scores_tensor = torch.tensor(cross_scores, dtype=torch.float32, device=device)

    # Sigmoid maps raw logits to [0, 1] for fair combination with RRF
    cross_scores_normalized = torch.sigmoid(cross_scores_tensor)

    rrf_of_top = rrf_scores[rrf_top_indices]

    # Normalize RRF scores to 0-1
    rrf_min = rrf_of_top.min()
    rrf_max = rrf_of_top.max()
    if rrf_max > rrf_min:
        rrf_normalized = (rrf_of_top - rrf_min) / (rrf_max - rrf_min)
    else:
        rrf_normalized = torch.ones_like(rrf_of_top) * 0.5

    # 60% cross-encoder + 40% rank fusion
    combined = 0.6 * cross_scores_normalized + 0.4 * rrf_normalized

    candidates = [
        (combined[j].item(), filtered_songs[rrf_top_indices[j]])
        for j in range(len(rrf_top_indices))
    ]
    candidates.sort(key=lambda x: x[0], reverse=True)
    print(f"[RAG] Cross-encoder reranked top {len(candidates)} candidates")

    # MMR diversity reranking
    candidate_songs = [s for _, s in candidates]
    candidate_docs = [
        build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
        for s in candidate_songs
    ]
    candidate_embeddings = get_batch_embeddings_tensor(candidate_docs)

    diversified = mmr_rerank(candidates, candidate_embeddings, prompt_tensor)
    print(f"[RAG] MMR diversified to {len(diversified)} results")

    print(f"\n[RAG] Final ranking:")
    for i, (score, song) in enumerate(diversified[:10]):
        print(f"  {i+1}. {song.title} by {song.artist} (mood={song.mood}, {song.tempo:.0f} BPM) - score: {score:.4f}")

    return diversified[:top_k]


def enrich_discovered_songs(new_songs: list) -> list:
    """Enrich zero-shot song discoveries with album art and preview URLs from iTunes."""
    from utils.spotify import search_itunes

    enriched = []
    for song in new_songs:
        title = song.get("title", "")
        artist = song.get("artist", "")

        itunes_results = search_itunes(title + " " + artist, limit=1)
        if itunes_results:
            it = itunes_results[0]
            song["album_art_url"] = it.get("artworkUrl100", it.get("album_art_url", ""))
            song["preview_url"] = it.get("previewUrl", it.get("preview_url", None))
            song["spotify_url"] = it.get("trackViewUrl", "")
            song["spotify_id"] = str(it.get("trackId", ""))
        else:
            song["album_art_url"] = song.get("album_art_url", "")
            song["preview_url"] = song.get("preview_url", None)

        enriched.append(song)

    return enriched


def generate_ai_dj_synthesis(
    user_prompt: str,
    ranked_songs: list,
    planner_plan: dict = None,
    max_songs: int = None
) -> dict:
    """Use Ollama to generate a curated playlist with per-track explanations."""
    if max_songs is None:
        max_songs = settings.MAX_PLAYLIST_SONGS

    if not ranked_songs:
        # No library matches - ask Ollama for zero-shot suggestions
        try:
            fallback_prompt = f"""You are MoodBeats AI DJ. The user wants: "{user_prompt}"
No songs in their library match this vibe. Suggest 6-10 songs that would fit.

Respond in JSON:
{{
  "playlist_title": "Creative playlist name",
  "ai_dj_note": "2-3 sentence note about why these songs fit",
  "ordered_library_ids": [],
  "track_explanations": {{}},
  "new_song_recommendations": [
    {{"title": "Song Title", "artist": "Artist Name", "reason": "why it fits"}}
  ],
  "quality_score": 5,
  "quality_notes": "No library matches - these are external suggestions"
}}"""
            resp = requests.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": fallback_prompt,
                    "format": "json",
                    "stream": False,
                    "options": {"num_predict": 1000, "temperature": 0.4}
                },
                timeout=settings.OLLAMA_TIMEOUT_SECONDS
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "{}")
                try:
                    curation = json.loads(raw)
                except json.JSONDecodeError:
                    repaired = raw.rstrip()
                    if repaired.endswith('"'):
                        repaired += '}'
                    open_braces = repaired.count('{') - repaired.count('}')
                    open_brackets = repaired.count('[') - repaired.count(']')
                    repaired += ']' * open_brackets + '}' * open_braces
                    try:
                        curation = json.loads(repaired)
                        print(f"[AI DJ] JSON repaired successfully (fallback)")
                    except json.JSONDecodeError:
                        print(f"[AI DJ] Could not repair JSON (fallback), using fallback")
                        curation = {}
                return {
                    "playlist_title": curation.get("playlist_title", "Playlist: " + user_prompt),
                    "ai_dj_note": curation.get("ai_dj_note", ""),
                    "ordered_library_ids": [],
                    "new_song_recommendations": curation.get("new_song_recommendations", []),
                    "track_explanations": {},
                    "quality_score": curation.get("quality_score", 5),
                    "quality_notes": curation.get("quality_notes", "")
                }
        except Exception as e:
            print(f"[AI DJ] Fallback Ollama call failed: {e}")

        return {
            "playlist_title": f"Playlist: {user_prompt}",
            "ai_dj_note": f"No matching songs in your library. Here are some suggestions!",
            "ordered_library_ids": [],
            "new_song_recommendations": [],
            "track_explanations": {},
            "quality_score": 0,
            "quality_notes": "No songs to curate."
        }

    song_context = ""
    for i, (score, song) in enumerate(ranked_songs[:max_songs]):
        song_context += f"\n{i+1}. \"{song.title}\" by {song.artist} | Mood: {song.mood} | BPM: {song.tempo:.0f} | Energy: {song.energy:.2f} | Relevance: {score:.4f}"

    planner_context = ""
    if planner_plan:
        planner_context = f"""
Search plan:
- Mood: {planner_plan.get('mood', 'any')}
- Tempo: {planner_plan.get('tempo_range', [0, 200])}
- Energy: {planner_plan.get('energy_range', [0.0, 1.0])}
- Keywords: {', '.join(planner_plan.get('keywords', []))}
"""

    dj_prompt = f"""You are MoodBeats AI DJ. Curate a playlist from the user's library based on their vibe request.

User wants: "{user_prompt}"
{planner_context}

Available songs (ranked by AI relevance):
{song_context}

Your task:
1. Pick the best {max_songs} songs that match the vibe
2. Order them for optimal flow (energy arc, mood progression)
3. Give each selected song a brief "why this track" explanation (1 sentence)
4. Suggest 5-8 songs NOT in the library that would complement this playlist
5. Rate the overall playlist quality 1-10 with brief notes

Respond in JSON:
{{
  "playlist_title": "Creative playlist name",
  "ai_dj_note": "2-3 sentence DJ introduction",
  "ordered_library_ids": [list of song IDs in your chosen order],
  "track_explanations": {{"song_id": "why this track fits"}},
  "new_song_recommendations": [
    {{"title": "Song Title", "artist": "Artist Name", "reason": "why it complements"}}
  ],
  "quality_score": 7,
  "quality_notes": "Brief self-critique of the playlist"
}}"""

    try:
        resp = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": dj_prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "num_predict": 1500,
                    "temperature": 0.4
                }
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )

        if resp.status_code == 200:
            raw_response = resp.json().get("response", "{}")
            try:
                curation = json.loads(raw_response)
            except json.JSONDecodeError:
                # Repair truncated JSON by closing open brackets
                repaired = raw_response.rstrip()
                if repaired.endswith('"'):
                    repaired += '}'
                open_braces = repaired.count('{') - repaired.count('}')
                open_brackets = repaired.count('[') - repaired.count(']')
                repaired += ']' * open_brackets + '}' * open_braces
                try:
                    curation = json.loads(repaired)
                    print(f"[AI DJ] JSON repaired successfully")
                except json.JSONDecodeError:
                    print(f"[AI DJ] Could not repair JSON, using fallback")
                    curation = {}

            result = {
                "playlist_title": curation.get("playlist_title", "AI Curated Playlist"),
                "ai_dj_note": curation.get("ai_dj_note", f"Vibe: {user_prompt}"),
                "ordered_library_ids": curation.get("ordered_library_ids", []),
                "new_song_recommendations": curation.get("new_song_recommendations", []),
                "track_explanations": curation.get("track_explanations", {}),
                "quality_score": curation.get("quality_score"),
                "quality_notes": curation.get("quality_notes")
            }

            # Ensure types: ordered_library_ids must be ints, track_explanations keys must be strings
            result["ordered_library_ids"] = [int(x) for x in result["ordered_library_ids"] if x]
            result["track_explanations"] = {str(k): v for k, v in result["track_explanations"].items()}

            return result

    except Exception as e:
        print(f"[AI DJ] Ollama synthesis failed: {e}")

    # Fallback: return ranked songs without AI curation
    return {
        "playlist_title": f"Playlist: {user_prompt}",
        "ai_dj_note": f"Auto-generated from your library based on: {user_prompt}",
        "ordered_library_ids": [song.id for _, song in ranked_songs[:max_songs]],
        "new_song_recommendations": [],
        "track_explanations": {},
        "quality_score": None,
        "quality_notes": "AI DJ unavailable - using raw RAG ranking."
    }
