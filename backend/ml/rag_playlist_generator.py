# =============================================================================
# RAG PLAYLIST GENERATOR -------------------------------------- PyTorch Hybrid RAG + Cross-Encoder + Ollama AI DJ
# =============================================================================
# Pipeline:
#   1. Query Planner (Ollama decomposes user prompt into structured plan)
#   2. Metadata Pre-Filter (filter by mood/tempo/energy BEFORE vector search)
#   3. Dense Retrieval (bi-encoder cosine similarity)
#   4. Sparse Retrieval (BM25 lexical matching)
#   5. Reciprocal Rank Fusion (RRF) -------------------------------------- no weight tuning needed
#   6. Cross-Encoder Reranking (neural quality scoring)
#   7. MMR Diversity Reranking (prevent all-same-mood playlists)
#   8. AI DJ Synthesis (Ollama generates playlist + per-track explanations)
# =============================================================================

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


# =============================================================================
# SECTION 1: Reciprocal Rank Fusion (RRF)
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
# SECTION 2: Metadata Pre-Filter
# =============================================================================
# Why: If the planner extracts mood/tempo/energy constraints, we can filter
# candidates BEFORE expensive neural reranking. This reduces the search space
# and eliminates obviously wrong candidates early.
#
# Mood matching: uses fuzzy matching -------------------------------------- "melancholic" matches "sad",
# "aggressive" matches "energetic", etc. via normalize_mood().
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

    Mood matching is fuzzy: "melancholic" maps to "sad", "aggressive" to "energetic", etc.
    """
    # Normalize the mood to canonical form
    normalized_mood = normalize_mood(mood) if mood else None

    filtered_indices = []

    for i, s in enumerate(library_songs):
        # Mood filter: fuzzy match via normalize_mood
        if normalized_mood and s.mood:
            song_mood = normalize_mood(s.mood)
            if song_mood and song_mood != normalized_mood:
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
# SECTION 3: Maximal Marginal Relevance (MMR) -------------------------------------- Diversity Reranking
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
        candidate_embeddings: Tensor of shape (N, 384) -------------------------------------- embeddings of candidates
        query_embedding: Tensor of shape (1, 384) -------------------------------------- query embedding
        lambda_param: Balance between relevance and diversity (0=diversity, 1=relevance)
        top_k: Number of results to return

    Returns:
        Diversified list of (score, song) tuples
    """
    if lambda_param is None:
        lambda_param = settings.MMR_LAMBDA
    if top_k is None:
        top_k = settings.TOP_K

    if len(candidates) <= top_k:
        return candidates

    # Compute query-candidate similarities
    query_sim = F.cosine_similarity(query_embedding, candidate_embeddings, dim=1)

    # Track selected and remaining
    selected = []
    remaining = list(range(len(candidates)))

    for _ in range(min(top_k, len(candidates))):
        if not remaining:
            break

        best_score = -float('inf')
        best_idx = remaining[0]

        for idx in remaining:
            # Relevance: how well does this candidate match the query?
            relevance = query_sim[idx].item()

            # Diversity: how similar is this candidate to already-selected ones?
            if selected:
                selected_embs = candidate_embeddings[selected]
                candidate_emb = candidate_embeddings[idx].unsqueeze(0)
                sim_to_selected = F.cosine_similarity(candidate_emb, selected_embs, dim=1).max().item()
            else:
                sim_to_selected = 0.0

            # MMR score: balance relevance and diversity
            mmr_score = lambda_param * relevance - (1 - lambda_param) * sim_to_selected

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidates[i] for i in selected]


# =============================================================================
# SECTION 4: PyTorch Hybrid RAG Search -------------------------------------- The Core Pipeline
# =============================================================================
# This is the heart of MoodBeats' recommendation engine.
# It combines dense (neural) and sparse (lexical) retrieval, fuses them
# with RRF, reranks with a cross-encoder, and diversifies with MMR.
# =============================================================================

def pytorch_database_rag_search(
    user_prompt: str,
    library_songs: list,
    planner_plan: dict = None,
    top_k: int = None
) -> list:
    """
    Hybrid RAG search: Dense (Bi-encoder) + Sparse (BM25) -> RRF Fusion -> Rerank -> MMR.

    Args:
        user_prompt: The user's vibe description
        library_songs: List of Song ORM objects from database
        planner_plan: Pre-computed plan from Query Planner (optional)
        top_k: Number of results to return

    Returns:
        List of (score, song) tuples, ranked by relevance
    """
    if top_k is None:
        top_k = settings.TOP_K

    if not library_songs:
        return []

    # ------------------------------------------------------------------
    # Step 1: Query Planning
    # ------------------------------------------------------------------
    # If a plan wasn't provided, decompose the prompt now.
    # The plan gives us HyDE descriptions, expanded queries, and
    # metadata constraints (mood, tempo, energy).
    # ------------------------------------------------------------------

    if planner_plan is None:
        plan = decompose_query(user_prompt)
    else:
        plan = planner_plan

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
        print("[RAG] Metadata filter removed all songs -------------------------------------- falling back to unfiltered")
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
        if getattr(s, 'embedding', None):
            doc = f"Track: '{s.title}' by {s.artist}. Mood: {s.mood}. Tempo: {s.tempo} BPM. Energy: {s.energy}."
        else:
            doc = build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
        lib_docs.append(doc)

    # ------------------------------------------------------------------
    # Step 4: Dense Retrieval -------------------------------------- Bi-encoder matrix dot-product
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

    print(f"[RAG] Dense scores -------------------------------------- min: {dense_scores.min():.4f}, max: {dense_scores.max():.4f}")

    # ------------------------------------------------------------------
    # Step 5: Sparse Retrieval -------------------------------------- BM25 lexical matching
    # ------------------------------------------------------------------
    # BM25 catches exact keyword matches that dense retrieval might miss.
    # We combine original prompt keywords + planner keywords for BM25.
    # ------------------------------------------------------------------

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

    print(f"[RAG] Sparse scores -------------------------------------- min: {sparse_scores.min():.4f}, max: {sparse_scores.max():.4f}")

    # ------------------------------------------------------------------
    # Step 6: Reciprocal Rank Fusion (RRF)
    # ------------------------------------------------------------------
    # Combine dense and sparse scores using rank-based fusion.
    # This replaces the old hardcoded 0.65/0.35 weighting.
    # ------------------------------------------------------------------

    rrf_scores = reciprocal_rank_fusion(dense_scores, sparse_scores)

    print(f"[RAG] RRF scores -------------------------------------- min: {rrf_scores.min():.6f}, max: {rrf_scores.max():.6f}")

    # ------------------------------------------------------------------
    # Step 7: Cross-Encoder Reranking
    # ------------------------------------------------------------------
    # The cross-encoder re-scores each (query, document) pair directly.
    # This is more accurate than bi-encoder but O(n) -------------------------------------- only feasible
    # after RRF has reduced the candidate set.
    # ------------------------------------------------------------------

    # Top candidates from RRF (we'll rerank the top 2x to allow MMR to select)
    rrf_top_k = min(top_k * 2, len(filtered_songs))
    rrf_top_indices = torch.argsort(rrf_scores, descending=True)[:rrf_top_k]

    rerank_docs = [lib_docs[i] for i in rrf_top_indices]
    cross_scores = neural_cross_rerank(user_prompt, rerank_docs)
    cross_scores_tensor = torch.tensor(cross_scores, dtype=torch.float32, device=device)

    # Normalize cross-encoder scores to 0-1 range using sigmoid
    # The ms-marco model outputs raw logits (negative = low relevance)
    # Sigmoid maps them to [0, 1] for fair combination with RRF scores
    cross_scores_normalized = torch.sigmoid(cross_scores_tensor)

    # Combine RRF and cross-encoder scores (both now in 0-1 range)
    rrf_of_top = rrf_scores[rrf_top_indices]

    # Normalize RRF scores to 0-1 range too
    rrf_min = rrf_of_top.min()
    rrf_max = rrf_of_top.max()
    if rrf_max > rrf_min:
        rrf_normalized = (rrf_of_top - rrf_min) / (rrf_max - rrf_min)
    else:
        rrf_normalized = torch.ones_like(rrf_of_top) * 0.5

    # Weighted combination: 60% semantic (cross-encoder) + 40% rank fusion (RRF)
    combined = 0.6 * cross_scores_normalized + 0.4 * rrf_normalized

    # Create (score, song) tuples
    candidates = [
        (combined[j].item(), filtered_songs[rrf_top_indices[j]])
        for j in range(len(rrf_top_indices))
    ]

    # Sort by combined score
    candidates.sort(key=lambda x: x[0], reverse=True)

    print(f"[RAG] Cross-encoder reranked top {len(candidates)} candidates")

    # ------------------------------------------------------------------
    # Step 8: MMR Diversity Reranking
    # ------------------------------------------------------------------
    # Prevent all-same-mood playlists by penalizing redundant candidates.
    # ------------------------------------------------------------------

    # Build embeddings for MMR
    candidate_songs = [s for _, s in candidates]
    candidate_docs = [
        build_song_profile_text(s.title, s.artist, s.mood or "chill", s.tempo or 120.0, s.energy or 0.5)
        for s in candidate_songs
    ]
    candidate_embeddings = get_batch_embeddings_tensor(candidate_docs)

    diversified = mmr_rerank(candidates, candidate_embeddings, prompt_tensor)

    print(f"[RAG] MMR diversified to {len(diversified)} results")

    # Print final ranking
    print(f"\n[RAG] Final ranking:")
    for i, (score, song) in enumerate(diversified[:10]):
        print(f"  {i+1}. {song.title} by {song.artist} (mood={song.mood}, {song.tempo:.0f} BPM) -------------------------------------- score: {score:.4f}")

    return diversified[:top_k]


# =============================================================================
# SECTION 5: External API -------------------------------------- Enrich New Discoveries
# =============================================================================

def enrich_discovered_songs(new_songs: list) -> list:
    """
    Enrich zero-shot song discoveries with album art from iTunes.

    Takes the list of dicts from AI DJ's new_song_recommendations
    and adds album_art_url to each.
    """
    from utils.spotify import search_itunes

    enriched = []
    for song in new_songs:
        title = song.get("title", "")
        artist = song.get("artist", "")

        itunes_results = search_itunes(f"{title} {artist}", limit=1)
        if itunes_results:
            song["album_art_url"] = itunes_results[0].get("album_art_url", "")
        else:
            song["album_art_url"] = ""

        enriched.append(song)

    return enriched


# =============================================================================
# SECTION 6: AI DJ Synthesis -------------------------------------- Ollama Generates the Playlist Narrative
# =============================================================================

def generate_ai_dj_synthesis(
    user_prompt: str,
    ranked_songs: list,
    planner_plan: dict = None,
    max_songs: int = None
) -> dict:
    """
    Use Ollama to generate a curated playlist with per-track explanations.

    Args:
        user_prompt: The user's vibe description
        ranked_songs: List of (score, song) tuples from RAG search
        planner_plan: Pre-computed plan from Query Planner
        max_songs: Maximum songs in the playlist

    Returns:
        Dict with playlist_title, ai_dj_note, ordered_library_ids,
        new_song_recommendations, track_explanations, quality_score, quality_notes
    """
    if max_songs is None:
        max_songs = settings.MAX_PLAYLIST_SONGS

    if not ranked_songs:
        return {
            "playlist_title": "Empty Playlist",
            "ai_dj_note": "No matching songs found in your library.",
            "ordered_library_ids": [],
            "new_song_recommendations": [],
            "track_explanations": {},
            "quality_score": 0,
            "quality_notes": "No songs to curate."
        }

    # Build context from ranked songs
    song_context = ""
    for i, (score, song) in enumerate(ranked_songs[:max_songs]):
        song_context += f"\n{i+1}. \"{song.title}\" by {song.artist} | Mood: {song.mood} | BPM: {song.tempo:.0f} | Energy: {song.energy:.2f} | Relevance: {score:.4f}"

    # Build planner context if available
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
4. Suggest 2-3 songs NOT in the library that would complement this playlist
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
                    "num_predict": 800,
                    "temperature": 0.4
                }
            },
            timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )

        if resp.status_code == 200:
            raw_response = resp.json().get("response", "{}")
            curation = json.loads(raw_response)

            # Validate and fill defaults
            result = {
                "playlist_title": curation.get("playlist_title", "AI Curated Playlist"),
                "ai_dj_note": curation.get("ai_dj_note", f"Vibe: {user_prompt}"),
                "ordered_library_ids": curation.get("ordered_library_ids", []),
                "new_song_recommendations": curation.get("new_song_recommendations", []),
                "track_explanations": curation.get("track_explanations", {}),
                "quality_score": curation.get("quality_score"),
                "quality_notes": curation.get("quality_notes")
            }

            # Ensure ordered_library_ids are integers
            result["ordered_library_ids"] = [int(x) for x in result["ordered_library_ids"] if x]

            # Ensure track_explanations keys are strings (JSON keys are strings)
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
        "quality_notes": "AI DJ unavailable -------------------------------------- using raw RAG ranking."
    }