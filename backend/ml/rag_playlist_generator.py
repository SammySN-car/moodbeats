# =============================================================================
# RAG PLAYLIST GENERATOR — Advanced RAG Pipeline
# =============================================================================
# Architecture (v2):
#   1. Query Planner    — Ollama decomposes prompt into structured search plan
#   2. Hybrid Retrieve  — Dense (384d) + Sparse (BM25) with Reciprocal Rank Fusion
#   3. Metadata Filter  — Pre-filter by mood/tempo/energy from planner
#   4. Neural Rerank    — Cross-Encoder reranking with quality gate
#   5. Diversity (MMR)  — Maximal Marginal Relevance for playlist variety
#   6. AI DJ + Critique — Ollama generates playlist with per-track explanations
# =============================================================================

import re
import json
import requests
import torch
import torch.nn.functional as F
from rank_bm25 import BM25Okapi
from config import settings
from ml.embedding_service import (
    get_device,
    get_batch_embeddings_tensor,
    neural_cross_rerank,
    build_song_profile_text
)
from ml.query_planner import decompose_query
from utils.spotify import search_itunes, verify_track_on_itunes


# =============================================================================
# SECTION 1: Utility Functions
# =============================================================================

def _normalize_song_key(title: str, artist: str = "") -> str:
    """Normalize title and artist to eliminate duplicate remixes, slowed/sped-up versions, and edits."""
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', title)
    t = re.sub(r'[-–—].*$', '', t)
    t = re.sub(r'[^\w\s]', '', t).strip().lower()

    a = re.sub(r'[\(\[\{].*?[\)\]\}]', '', artist)
    a = re.sub(r'[^\w\s]', '', a).strip().lower()
    a_first = a.split()[0] if a else ""

    return f"{t}_{a_first}"


def _clean_track_title(title: str) -> str:
    """Clean Ollama prefix formatting like 'Song 1: Tokyo Drift' -> 'Tokyo Drift'."""
    return re.sub(r'^(Song\s*\d+:?|\d+[\.\)]\s*)', '', title.strip()).strip(' "\'')


# =============================================================================
# SECTION 2: Reciprocal Rank Fusion (RRF)
# =============================================================================
# Why RRF over weighted sum?
# Weighted sum (0.65*dense + 0.35*sparse) requires tuning and fails when
# one method dominates. RRF naturally adapts by using rank positions instead
# of raw scores. Source: Agile Infoways (50+ enterprise RAG deployments)
# showed RRF lifts recall@10 by 8-14 points over weighted fusion.
#
# Formula: RRF_score(d) = sum( 1 / (k + rank_i(d)) ) for each retrieval method
# =============================================================================

def reciprocal_rank_fusion(
    dense_scores: torch.Tensor,
    sparse_scores: torch.Tensor,
    k: int = None
) -> torch.Tensor:
    """
    Combine dense and sparse scores using Reciprocal Rank Fusion.

    Args:
        dense_scores: Raw cosine similarity scores from bi-encoder
        sparse_scores: Normalized BM25 scores
        k: RRF constant (default from config). Higher k = less aggressive rank discounting.

    Returns:
        Combined RRF scores as a tensor
    """
    if k is None:
        k = settings.RRF_K

    # Get rank positions (1-indexed) for each method
    # argsort gives indices that would sort the array; inverse_argsort gives ranks
    dense_ranks = torch.argsort(torch.argsort(dense_scores, descending=True)) + 1  # 1-indexed
    sparse_ranks = torch.argsort(torch.argsort(sparse_scores, descending=True)) + 1

    # RRF formula: 1 / (k + rank)
    dense_rrf = 1.0 / (k + dense_ranks.float())
    sparse_rrf = 1.0 / (k + sparse_ranks.float())

    # Sum RRF scores from both methods
    combined = dense_rrf + sparse_rrf

    return combined


# =============================================================================
# SECTION 3: Metadata Pre-Filter
# =============================================================================
# Why: If the planner extracts mood/tempo/energy constraints, we can filter
# candidates BEFORE expensive neural reranking. This reduces the search space
# and eliminates obviously wrong candidates early.
# =============================================================================

def _metadata_filter(
    library_songs: list,
    mood: str = None,
    tempo_range: list = None,
    energy_range: list = None
) -> list:
    """
    Filter library songs by metadata constraints from the query planner.

    Returns indices of songs that pass ALL filters.
    Songs with missing metadata pass through (we don't penalize missing data).
    """
    filtered_indices = []

    for i, s in enumerate(library_songs):
        # Mood filter: exact match
        if mood and s.mood and s.mood.lower() != mood.lower():
            continue

        # Tempo filter: check if song tempo falls within range
        if tempo_range and s.tempo:
            if not (tempo_range[0] <= s.tempo <= tempo_range[1]):
                continue

        # Energy filter: check if song energy falls within range
        if energy_range and s.energy:
            if not (energy_range[0] <= s.energy <= energy_range[1]):
                continue

        filtered_indices.append(i)

    return filtered_indices


# =============================================================================
# SECTION 4: Maximal Marginal Relevance (MMR) — Diversity Reranking
# =============================================================================
# Why: Without diversity, playlists can be all the same mood/tempo.
# MMR balances relevance with diversity by penalizing candidates that are
# too similar to already-selected candidates.
#
# Formula: MMR(d) = lambda * relevance(d) - (1-lambda) * max_sim(d, selected)
# lambda=0.7 means 70% relevance, 30% diversity
# =============================================================================

def mmr_rerank(
    candidates: list,
    candidate_embeddings: torch.Tensor,
    query_embedding: torch.Tensor,
    lambda_param: float = None,
    top_k: int = None
) -> list:
    """
    Apply Maximal Marginal Relevance to diversify the final playlist.

    Args:
        candidates: List of (score, song) tuples
        candidate_embeddings: Tensor of shape (N, 384) — embeddings of candidates
        query_embedding: Tensor of shape (1, 384) — query embedding
        lambda_param: Tradeoff between relevance and diversity (0-1)
        top_k: Number of candidates to return

    Returns:
        Re-ranked list of (score, song) tuples with diversity
    """
    if lambda_param is None:
        lambda_param = settings.MMR_LAMBDA
    if top_k is None:
        top_k = min(settings.MAX_PLAYLIST_SONGS, len(candidates))

    if len(candidates) <= 1:
        return candidates[:top_k]

    # Compute relevance scores (cosine similarity to query)
    relevance_scores = F.cosine_similarity(
        candidate_embeddings, query_embedding, dim=1
    )

    # Normalize relevance to [0, 1]
    rel_min = relevance_scores.min()
    rel_max = relevance_scores.max()
    if rel_max - rel_min > 0:
        relevance_scores = (relevance_scores - rel_min) / (rel_max - rel_min)

    # Compute inter-candidate similarity matrix
    # sim_matrix[i][j] = cosine similarity between candidate i and candidate j
    sim_matrix = F.cosine_similarity(
        candidate_embeddings.unsqueeze(1),
        candidate_embeddings.unsqueeze(0),
        dim=2
    )

    # Greedy MMR selection
    selected_indices = []
    remaining_indices = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        if not remaining_indices:
            break

        best_score = -float('inf')
        best_idx = remaining_indices[0]

        for idx in remaining_indices:
            # Relevance component
            rel = relevance_scores[idx].item()

            # Diversity component: max similarity to any already-selected candidate
            if selected_indices:
                max_sim = max(sim_matrix[idx][s].item() for s in selected_indices)
            else:
                max_sim = 0.0

            # MMR score
            mmr_score = lambda_param * rel - (1 - lambda_param) * max_sim

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)

    return [candidates[i] for i in selected_indices]


# =============================================================================
# SECTION 5: Main RAG Search Pipeline
# =============================================================================
# This is the core function. Flow:
#   User Prompt
#     -> Query Planner (Ollama decomposes into structured plan)
#     -> Metadata Pre-Filter (filter by mood/tempo/energy)
#     -> Dense Search (384d bi-encoder embeddings)
#     -> Sparse Search (BM25 lexical matching)
#     -> RRF Fusion (reciprocal rank fusion, not hardcoded weights)
#     -> Cross-Encoder Reranking (neural quality scoring)
#     -> MMR Diversity (prevent all-same-mood playlists)
#     -> Return ranked results
# =============================================================================

def pytorch_database_rag_search(user_prompt: str, library_songs: list) -> list:
    """
    Advanced PyTorch RAG Search on User Library Songs.

    Pipeline:
      1. Query Planner — Ollama decomposes prompt (HyDE + expansion + metadata)
      2. Metadata Pre-Filter — Filter candidates by mood/tempo/energy
      3. Dense + Sparse Retrieval — Bi-encoder + BM25
      4. RRF Fusion — Reciprocal Rank Fusion (not hardcoded weights)
      5. Cross-Encoder Reranking — Neural quality scoring
      6. MMR Diversity — Maximal Marginal Relevance for playlist variety
    """
    if not library_songs:
        return []

    device = get_device()

    # ------------------------------------------------------------------
    # Step 1: Query Planner — decompose the user prompt
    # ------------------------------------------------------------------
    # The planner uses Ollama to extract:
    #   - HyDE description (for better embedding)
    #   - Expanded queries (for multi-query retrieval)
    #   - Mood/tempo/energy ranges (for metadata filtering)
    #   - Keywords (for BM25 boosting)
    # ------------------------------------------------------------------

    if settings.PLANNER_ENABLED:
        plan = decompose_query(user_prompt)
    else:
        plan = {
            "hyde_description": user_prompt,
            "expanded_queries": [user_prompt],
            "mood": None,
            "tempo_range": [0, 200],
            "energy_range": [0.0, 1.0],
            "keywords": [],
            "search_paths": ["semantic"]
        }

    # Use HyDE description as the primary embedding query if available
    # HyDE generates a hypothetical ideal track description that is
    # semantically closer to real document chunks than the raw query
    embedding_query = plan["hyde_description"] if plan["hyde_description"] else user_prompt

    print(f"[RAG] Embedding query: \"{embedding_query[:80]}...\"")

    # ------------------------------------------------------------------
    # Step 2: Metadata Pre-Filter
    # ------------------------------------------------------------------
    # If the planner extracted mood/tempo/energy constraints,
    # filter candidates BEFORE expensive vector search.
    # ------------------------------------------------------------------

    filter_indices = _metadata_filter(
        library_songs,
        mood=plan.get("mood"),
        tempo_range=plan.get("tempo_range"),
        energy_range=plan.get("energy_range")
    )

    # If metadata filtering removes ALL songs, fall back to unfiltered
    if len(filter_indices) == 0:
        print("[RAG] Metadata filter removed all songs — falling back to unfiltered")
        filtered_songs = library_songs
        filter_indices = list(range(len(library_songs)))
    else:
        filtered_songs = [library_songs[i] for i in filter_indices]
        print(f"[RAG] Metadata filter: {len(library_songs)} -> {len(filtered_songs)} candidates")

    # ------------------------------------------------------------------
    # Step 3: Build document representations
    # ------------------------------------------------------------------

    lib_docs = []
    for s in filtered_songs:
        if s.embedding:
            doc = f"Track: '{s.title}' by {s.artist}. Mood: {s.mood}. Tempo: {s.tempo} BPM. Energy: {s.energy}."
        else:
            doc = build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
        lib_docs.append(doc)

    # ------------------------------------------------------------------
    # Step 4: Dense Retrieval — Bi-encoder matrix dot-product
    # ------------------------------------------------------------------
    # Embed the (possibly HyDE-expanded) query and compute cosine
    # similarity against all candidate embeddings.
    # ------------------------------------------------------------------

    prompt_tensor = get_batch_embeddings_tensor([embedding_query])

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

    print(f"[RAG] Dense scores — min: {dense_scores.min():.4f}, max: {dense_scores.max():.4f}")

    # ------------------------------------------------------------------
    # Step 5: Sparse Retrieval — BM25 lexical matching
    # ------------------------------------------------------------------
    # BM25 catches exact keyword matches that dense retrieval might miss.
    # We combine original prompt keywords + planner keywords for BM25.
    # ------------------------------------------------------------------

    bm25_lib = BM25Okapi([d.lower().split() for d in lib_docs])

    # Use original prompt + keywords for BM25 query
    bm25_query = user_prompt.lower().split()
    if plan.get("keywords"):
        bm25_query.extend([k.lower() for k in plan["keywords"]])

    sparse_raw = torch.tensor(
        bm25_lib.get_scores(bm25_query),
        dtype=torch.float32, device=device
    )
    max_sparse = torch.max(sparse_raw)
    sparse_scores = sparse_raw / (max_sparse if max_sparse > 0 else 1.0)

    print(f"[RAG] Sparse scores — min: {sparse_scores.min():.4f}, max: {sparse_scores.max():.4f}")

    # ------------------------------------------------------------------
    # Step 6: Reciprocal Rank Fusion (RRF)
    # ------------------------------------------------------------------
    # Replace hardcoded 0.65/0.35 with RRF. No weight tuning needed.
    # Source: Agile Infoways showed RRF lifts recall@10 by 8-14 points.
    # ------------------------------------------------------------------

    hybrid_scores = reciprocal_rank_fusion(dense_scores, sparse_scores)

    print(f"[RAG] RRF scores — min: {hybrid_scores.min():.6f}, max: {hybrid_scores.max():.6f}")

    # ------------------------------------------------------------------
    # Step 7: Select top-K candidates for neural reranking
    # ------------------------------------------------------------------

    top_k = min(settings.RERANKER_TOP_K, len(filtered_songs))
    topk_scores, topk_indices = torch.topk(hybrid_scores, k=top_k)

    candidate_songs = [filtered_songs[i] for i in topk_indices.tolist()]
    candidate_docs = [lib_docs[i] for i in topk_indices.tolist()]

    print(f"[RAG] Top-{top_k} candidates selected for neural reranking")

    # ------------------------------------------------------------------
    # Step 8: Cross-Encoder Neural Reranking
    # ------------------------------------------------------------------
    # Cross-encoder reads (query, document) pairs and scores relevance.
    # Much more accurate than bi-encoder but slower — only used on top-K.
    # ------------------------------------------------------------------

    cross_scores = neural_cross_rerank(embedding_query, candidate_docs)
    rerank_indices = sorted(range(len(cross_scores)), key=lambda i: cross_scores[i], reverse=True)

    # Adaptive threshold: stricter for larger libraries
    threshold = -6.0 if len(filtered_songs) <= 5 else -4.0
    ranked_library_songs = [
        (cross_scores[i], candidate_songs[i])
        for i in rerank_indices
        if cross_scores[i] > threshold
    ]

    # If nothing passed threshold but library is small, take the best one
    if not ranked_library_songs and len(candidate_songs) > 0 and len(filtered_songs) <= 5:
        best_idx = rerank_indices[0]
        ranked_library_songs = [(cross_scores[best_idx], candidate_songs[best_idx])]

    print(f"[RAG] After reranking: {len(ranked_library_songs)} songs passed threshold")

    # ------------------------------------------------------------------
    # Step 9: MMR Diversity Reranking
    # ------------------------------------------------------------------
    # Prevent all-same-mood playlists by applying Maximal Marginal Relevance.
    # Balances relevance with diversity (configurable via MMR_LAMBDA).
    # ------------------------------------------------------------------

    if len(ranked_library_songs) > 1:
        # Get embeddings for MMR diversity computation
        mmr_songs = [s for _, s in ranked_library_songs]
        mmr_docs = [
            build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
            for s in mmr_songs
        ]
        mmr_embeddings = get_batch_embeddings_tensor(mmr_docs)

        ranked_library_songs = mmr_rerank(
            ranked_library_songs,
            mmr_embeddings,
            prompt_tensor
        )

        print(f"[RAG] After MMR diversity: {len(ranked_library_songs)} songs")

    return ranked_library_songs


# =============================================================================
# SECTION 6: iTunes Enrichment & Discovery
# =============================================================================

def enrich_discovered_songs(new_song_list: list) -> list[dict]:
    """Auto-verifies against iTunes, deduplicates, and fetches artwork."""
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

        if not art_url or not preview_url:
            verified = verify_track_on_itunes(title, artist)
            if verified:
                title = verified["title"]
                artist = verified["artist"]
                art_url = verified["album_art_url"]
                preview_url = verified["preview_url"]

        final_key = _normalize_song_key(title, artist)
        if final_key in seen_keys:
            continue

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
    """Dynamically search iTunes for up to 50 vibe-matching tracks without duplicates."""
    clean_query = re.sub(r'[^\w\s]', '', user_prompt)
    words = [w for w in clean_query.split() if len(w) > 2]

    results = []
    seen = set(existing_keys) if existing_keys else set()

    search_queries = [
        " ".join(words[:4]),
        f"{words[0]} {words[-1]}" if len(words) > 1 else words[0],
        f"{words[0]} top hits" if words else "top hits",
        f"{words[0]} music" if words else "pop"
    ]

    for sq in search_queries:
        if len(results) >= limit:
            break
        raw = search_itunes(sq, entity="song", limit=limit)
        for item in raw:
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

    return results[:limit]


# =============================================================================
# SECTION 7: AI DJ Synthesis with Per-Track Explanations
# =============================================================================
# Upgraded prompt now includes:
#   - Per-track "why_track" explanations
#   - Critique score for playlist quality
#   - Uses query planner output for better context
# =============================================================================

def generate_ai_dj_synthesis(
    user_prompt: str,
    library_songs: list,
    planner_plan: dict = None
) -> dict:
    """
    Ollama AI DJ: Arranges library songs and recommends new songs.

    Now includes per-track explanations and quality self-critique.
    """

    valid_ids = [s.id for _, s in library_songs]
    tracks_str = "\n".join([
        f"- ID {s.id}: '{s.title}' by {s.artist} (Mood: {s.mood}, Tempo: {round(s.tempo or 0)} BPM, Energy: {round((s.energy or 0)*100)}%)"
        for _, s in library_songs
    ])

    library_keys = {_normalize_song_key(s.title, s.artist or "") for _, s in library_songs}
    dynamic_discoveries = _get_dynamic_public_discoveries(user_prompt, limit=settings.MAX_NEW_DISCOVERIES, existing_keys=library_keys)

    fallback_result = {
        "playlist_title": f"Vibe: {user_prompt[:25].capitalize()}",
        "ai_dj_note": f"A curated set matching your vibe: '{user_prompt}'.",
        "ordered_library_ids": valid_ids[:settings.MAX_PLAYLIST_SONGS],
        "new_song_recommendations": dynamic_discoveries
    }

    # ------------------------------------------------------------------
    # Build context from planner if available
    # ------------------------------------------------------------------
    planner_context = ""
    if planner_plan:
        if planner_plan.get("mood"):
            planner_context += f"\nDetected mood: {planner_plan['mood']}"
        if planner_plan.get("keywords"):
            planner_context += f"\nKey themes: {', '.join(planner_plan['keywords'][:5])}"
        if planner_plan.get("hyde_description"):
            planner_context += f"\nIdeal track feel: {planner_plan['hyde_description'][:150]}"

    # ------------------------------------------------------------------
    # Prompt now asks for per-track explanations
    # ------------------------------------------------------------------
    prompt = f"""You are MoodBeats AI DJ, a master music curator.
User requested this vibe: "{user_prompt}"
{planner_context}

Matching songs in user's library:
{tracks_str if tracks_str else "None"}

Perform these tasks:
1. Select and arrange library songs in optimal sequence using ONLY valid IDs: {valid_ids}.
2. For EACH library song you select, write a 1-sentence "why_track" explaining why it fits the vibe.
3. Zero-shot recommend 4-5 REAL famous iconic songs that capture this exact vibe.
4. Rate your own playlist quality from 1-10 (be honest — if it's below 7, suggest improvements).

Respond in valid JSON ONLY:
{{
  "playlist_title": "Creative 2-4 word playlist title",
  "ai_dj_note": "2-sentence curator note explaining the mood progression and vibe",
  "ordered_library_ids": [
    {{"id": 1, "why_track": "Explanation for why this track fits"}},
    {{"id": 2, "why_track": "Explanation for why this track fits"}}
  ],
  "new_song_recommendations": [
    {{"title": "Real Song Title 1", "artist": "Real Artist 1"}},
    {{"title": "Real Song Title 2", "artist": "Real Artist 2"}}
  ],
  "quality_score": 8,
  "quality_notes": "Brief self-critique of the playlist"
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
                    "num_predict": settings.OLLAMA_MAX_TOKENS + 100,
                    "temperature": 0.7
                }
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            parsed = json.loads(resp.json().get("response", "{}"))
            raw_ids = parsed.get("ordered_library_ids", [])

            # ------------------------------------------------------------------
            # Parse ordered_library_ids — now supports both formats:
            #   - Old: [1, 2, 3]
            #   - New: [{"id": 1, "why_track": "..."}, ...]
            # ------------------------------------------------------------------
            cleaned_ids = []
            track_explanations = {}
            for entry in raw_ids:
                if isinstance(entry, dict):
                    sid = entry.get("id")
                    why = entry.get("why_track", "")
                    if sid in valid_ids and sid not in cleaned_ids:
                        cleaned_ids.append(sid)
                        track_explanations[sid] = why
                elif isinstance(entry, int):
                    if entry in valid_ids and entry not in cleaned_ids:
                        cleaned_ids.append(entry)

            raw_recs = parsed.get("new_song_recommendations", [])

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

            merged_recs = list(valid_recs)
            for d in dynamic_discoveries:
                k = _normalize_song_key(d["title"], d.get("artist", ""))
                if k not in seen_recs:
                    seen_recs.add(k)
                    merged_recs.append(d)
                if len(merged_recs) >= settings.MAX_NEW_DISCOVERIES:
                    break

            result = {
                "playlist_title": parsed.get("playlist_title", fallback_result["playlist_title"]),
                "ai_dj_note": parsed.get("ai_dj_note", fallback_result["ai_dj_note"]),
                "ordered_library_ids": cleaned_ids if cleaned_ids else valid_ids[:settings.MAX_PLAYLIST_SONGS],
                "new_song_recommendations": merged_recs[:settings.MAX_NEW_DISCOVERIES],
                "track_explanations": track_explanations,
                "quality_score": parsed.get("quality_score", 0),
                "quality_notes": parsed.get("quality_notes", "")
            }

            print(f"[AI DJ] Playlist: {result['playlist_title']}")
            print(f"[AI DJ] Library tracks: {len(result['ordered_library_ids'])}")
            print(f"[AI DJ] Discoveries: {len(result['new_song_recommendations'])}")
            print(f"[AI DJ] Quality score: {result['quality_score']}/10")
            print(f"[AI DJ] Track explanations: {len(result['track_explanations'])} tracks explained")

            return result
    except Exception as e:
        print(f"[AI DJ] Ollama call failed: {e}")

    return fallback_result