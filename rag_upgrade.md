# MoodBeats RAG Architecture Upgrade

> Research-backed upgrade plan. Last updated: 2026-08-31

---

## 1. Current Architecture Audit

### What we have today

`
User Prompt
    ↓
[Dense: all-MiniLM-L6-v2 (384d)] + [Sparse: BM25]
    ↓ Hardcoded 0.65 dense + 0.35 sparse fusion
    ↓ Top-15 candidates
    ↓ [Cross-Encoder: ms-marco-MiniLM-L-6-v2 reranking]
    ↓ Threshold filter
    ↓ Ollama AI DJ (llama3.2) — generates playlist + 1 note
`

### Weaknesses

| Problem | Impact |
|---------|--------|
| No query understanding | Raw prompt goes straight to embedding. `"rainy night vibes"` embedded as-is, loses nuance |
| Hardcoded fusion weights | 0.65/0.35 works for some queries, fails for others |
| No user modeling | Every user gets identical results for the same prompt |
| No feedback loop | System never learns from skips, saves, plays |
| No retrieval quality check | Cross-encoder reranks but has no self-awareness about result quality |
| Single retrieval pass | One shot, no iterative refinement |
| Playlist-level explanations only | User doesn't know WHY each track was chosen |
| No exploration mechanism | Can get stuck in a rut, always recommending similar tracks |
| No metadata pre-filtering | Searches entire library even when user specifies tempo/energy constraints |

---

## 2. Research Findings

### 2.1 What Spotify actually does (2026)

Source: music-tomorrow.com, dynamoi.com, Spotify Research, philippdubach.com

- **Three-layer architecture**: Offline (batch train deep collaborative filtering, hours), Nearline (update user embeddings seconds after a click), Online (millisecond responses per page load)
- **Multi-armed bandits**: Deliberately explore new genres to avoid filter bubbles. Netflix measures recommendation value by incrementality — the causal lift of showing a title vs not showing it
- **Semantic IDs**: LLMs for recommendation at scale using learned discrete tokens instead of raw embeddings
- **Prompted Playlists** (Dec 2025): Users type natural language instructions, system generates playlists from full listening history
- **Taste Profile Exclusion** (Oct 2025): Users can exclude one-off listens from influencing recommendations
- **AI DJ** (2023+): Uses an agentic router that decides per-query whether to invoke expensive LLM or fall back to fast keyword matching — an inference cost optimizer disguised as a product feature
- **Embed everything**: Lyrics, cover art, canvases, short-form video, press, social chatter — all embedded into a shared vector space alongside audio features
- **Contextual + Sequential User Embeddings**: User preferences evolve over time; the system tracks what you liked last week vs last month

### 2.2 SoulTuner-Agent (most advanced open-source music RAG)

Source: github.com/hgsanyang/SoulTuner-Agent (20 stars, 383 commits)

Architecture:
`
User sentence
     |
     v
+-------------------------------------------+
|  Agent (LangGraph)                         |
|  recall memory -> LLM plan -> route intent |
+---------------------+---------------------+
                      v
+-------------------------------------------+
|  Retrieval: Graph + MuQ Vector -> Fuse     |
+---------------------+---------------------+
                      v
+-------------------------------------------+
|  Ranking: multi-source fusion -> rerank    |
|  -> diversity -> per-track explanations    |
+-------------------------------------------+
`

Key design decisions:
- **Planner pattern**: LLM plans HOW to search (which intents, metadata filters, retrieval paths). Deterministic code validates the plan before any retrieval. The model does NOT invent songs — it plans the search.
- **Hybrid retrieval**: Neo4j graph (artist -> genre -> mood -> era relationships) + MuQ-MuLan audio embeddings (text-to-music similarity)
- **Long-term memory**: Likes, saves, skips, and session context recorded as traceable events. Useful preferences recalled in later conversations.
- **Per-track explanations**: Each result comes with a `why_track` field explaining the fit
- **Diversity reranking**: Prevents all-same-mood playlists
- **Web supplementation**: When library is too small, optionally fetch from web
- **35B trained Planner**: Fine-tuned specifically for their retrieval contract. 99.4% valid planning, 95.6% correct intent + route selection.

### 2.3 MusicRec-RAG (hhc25)

Source: github.com/hhc25/MusicRec-RAG

- ETL pipeline from YouTube + Spotify
- MongoDB data lake + ChromaDB vector store
- OpenAI text-embedding-3-small
- CrewAI agent orchestration
- LangChain conversation + memory
- Chainlit frontend

### 2.4 music-recommender-rag (camsset-developer)

Source: github.com/camsset-developer/music-recommender-rag

- Multi-source ingestion: Spotify + Last.fm + Genius APIs
- **Hybrid embeddings**: Text features (lyrics, genre tags) fused with audio features (tempo, energy, danceability)
- Vertex AI embeddings + BigQuery + GCS
- 60-80% semantic similarity on 392-song dataset
- Production deployment via Cloud Run + Docker

### 2.5 Production enterprise RAG patterns (2026)

Source: Agile Infoways (50+ deployments), Tezeract, Techment, n1n.ai

Findings:
- **#1 cause of bad RAG quality is bad retrieval**, not LLM quality. Galileo's "Seven Failure Points" report: retrieval-focused failures account for 10-30% of answer degradation.
- **RRF > weighted fusion**: "Run both in parallel, merge with Reciprocal Rank Fusion. Lifts recall@10 by 8-14 points compared to dense-only." (Agile Infoways)
- **Reranking is the unsung hero**: Biggest single-technique gain. Cross-encoder reranking improves precision@1 by 15-30%.
- **HyDE**: Generate hypothetical answer with LLM, embed THAT for retrieval. Improves recall for indirect questions by 20-40%. (Vucense, Haystack)
- **Query Expansion**: LLM produces 3-5 semantically varied queries, search with ALL, merge results. (Haystack cookbook)
- **Self-RAG**: LLM evaluates its own retrieval quality. Rejects low-quality results.
- **Agentic RAG**: LLM decomposes complex queries into sub-queries, retrieves for each, evaluates if it has enough context.
- **Eval-first development**: Set up RAGAS evaluation before writing any prompts.
- **Late chunking**: Embed full document first, then chunk. Each chunk carries context from full document.
- **Metadata pre-filtering**: Filter by structured fields (tempo, energy, mood) BEFORE vector search to reduce search space.

### 2.6 Advanced RAG techniques summary

Source: vucense.com, kindatechnical.com, haystack.deepset.ai, superml.org

| Technique | What it does | Impact | Cost |
|-----------|-------------|--------|------|
| HyDE | LLM generates hypothetical answer, embeds THAT | +20-40% recall on abstract queries | +1 LLM call (~1.5s) |
| Query Expansion | LLM generates 3-5 varied queries | +15-25% recall | +1 LLM call |
| RRF | Reciprocal Rank Fusion replaces weighted sum | +8-14% recall@10 | Free |
| Cross-Encoder Reranking | Re-score top candidates with cross-encoder | +15-30% precision@1 | ~200ms |
| Self-RAG | LLM evaluates retrieval quality | Fewer garbage results | +1 LLM call |
| Metadata Pre-filter | Filter by tempo/energy/mood before vector search | Faster + more accurate | Free |
| User Taste Bias | Average embeddings of user's history, bias results | Personalization | +DB query |
| Diversity Reranking (MMR) | Prevent all-same-mood playlists | Better UX | Free |
| Per-track explanations | LLM explains why each track fits | User trust | +1 LLM call |

---

## 3. Suggested Upgrades

### Phase 1: Query Planner (highest impact)

**What**: Instead of sending raw prompt to embedder, have Ollama decompose it into a structured search plan.

**How it works**:
`
User types: "late night drive in rain"
     |
     v
Ollama call (structured JSON output):
{
  "intents": ["mood", "scene", "activity"],
  "mood": "melancholic",
  "tempo_range": [60, 100],
  "energy_range": [0.1, 0.4],
  "keywords": ["atmospheric", "ambient", "synth", "rain"],
  "search_paths": ["mood_filter", "tempo_filter", "semantic"],
  "expanded_queries": [
    "melancholic atmospheric ambient music",
    "slow tempo synth for driving at night",
    "rainy mood lo-fi chill tracks"
  ],
  "hyde_description": "A slow atmospheric track with warm synth pads, gentle rain ambience, melancholic melody, perfect for late night highway driving"
}
`

Then:
- Use `hyde_description` as the embedding query (HyDE)
- Use `expanded_queries` for multi-query retrieval
- Use `mood_range`, `tempo_range`, `energy_range` as metadata pre-filters
- Use `keywords` for BM25

**Files to create/modify**:
- NEW: `ml/query_planner.py` — Ollama call to decompose prompt
- MODIFY: `ml/rag_playlist_generator.py` — use planner output
- MODIFY: `config.py` — add planner settings

**Estimated effort**: ~100 lines new code, ~50 lines modified

---

### Phase 2: RRF + Metadata Pre-filter

**What**: Replace hardcoded `0.65 * dense + 0.35 * sparse` with Reciprocal Rank Fusion. Use planner metadata to pre-filter candidates.

**RRF formula**:
`python
def rrf_score(rank, k=60):
    return 1.0 / (k + rank)
`

For each candidate song, sum RRF scores from dense search rank AND sparse search rank. No weight tuning needed.

**Metadata pre-filter**: Before vector search, filter library songs by tempo/energy/mood ranges from the planner. Reduces search space and eliminates obviously wrong candidates early.

**Files to modify**:
- `ml/rag_playlist_generator.py` — replace fusion logic

**Estimated effort**: ~30 lines modified

---

### Phase 3: User Taste Profile

**What**: Compute a `taste_vector` = weighted average of embeddings of user's recently played / saved / most-imported songs. Bias final rankings toward user's actual preferences.

**How it works**:
1. New DB model: `ListeningEvent` (song_id, user_id, event_type [play/skip/save], timestamp, duration_listened)
2. On each playlist generation, compute taste vector:
   `python
   taste_vector = weighted_average(
       [song.embedding for song in user.recent_songs],
       weights=[recency_weight, save_weight, play_count_weight]
   )
   `
3. After reranking, bias scores:
   `python
   final_score = 0.7 * rerank_score + 0.3 * cosine(taste_vector, candidate_embedding)
   `

**Files to create/modify**:
- NEW: `models.py` — add `ListeningEvent` model
- NEW: `routers/history.py` — endpoints for play/skip/save events
- MODIFY: `ml/rag_playlist_generator.py` — add taste bias
- MODIFY: `frontend/src/components/BottomPlayer.vue` — emit play/skip events

**Estimated effort**: ~80 lines new, ~20 lines modified

---

### Phase 4: Per-track Explanations

**What**: Extend the LLM prompt to generate a `why_track` field for each result. Instead of one playlist-level AI note, each track gets a 1-sentence explanation.

**Example output**:
`json
{
  "title": "Midnight City",
  "artist": "M83",
  "why_track": "Slow-building synth anthem with atmospheric pads that match your late-night rain vibe"
}
`

**Files to modify**:
- `ml/rag_playlist_generator.py` — modify LLM prompt
- `schemas.py` — add `why_track` field to response

**Estimated effort**: ~20 lines modified

---

### Phase 5: Exploration / Diversity

**What**: Add Maximal Marginal Relevance (MMR) to prevent all-same-mood playlists. Balance relevance with diversity.

**MMR formula**:
`python
mmr_score = lambda * relevance - (1 - lambda) * max_similarity_to_selected
`

Where `lambda` controls relevance vs diversity tradeoff (0.7 = mostly relevant, some diversity).

**Files to modify**:
- `ml/rag_playlist_generator.py` — add MMR after reranking

**Estimated effort**: ~25 lines new

---

### Phase 6 (future): Knowledge Graph

**What**: Add Neo4j or similar graph DB to store artist -> genre -> mood -> era relationships. Enables relational reasoning like `"artists similar to The Weeknd but in the synthwave genre"`.

This is what SoulTuner does and it's a significant architectural change. Defer until Phases 1-5 are working.

---

## 4. Implementation Priority

| Phase | What | Effort | Impact | Risk |
|-------|------|--------|--------|------|
| **1** | Query Planner (HyDE + Expansion + Decomposition) | ~150 lines | HIGHEST | Low — Ollama already available |
| **2** | RRF + Metadata Pre-filter | ~30 lines | HIGH | Low — drop-in replacement |
| **3** | User Taste Profile | ~100 lines | HIGH | Medium — needs new DB model + frontend events |
| **4** | Per-track Explanations | ~20 lines | MEDIUM | Low — prompt change only |
| **5** | Diversity (MMR) | ~25 lines | MEDIUM | Low — pure math |
| **6** | Knowledge Graph | ~500+ lines | HIGH | High — new infra (Neo4j) |

**Recommended order**: Phase 1 → Phase 2 → Phase 4 → Phase 5 → Phase 3 → Phase 6

Phase 3 (taste profile) requires frontend changes to emit play/skip events, so it's better to do the pure-backend improvements first.

---

## 5. Files Affected

### New files
- `ml/query_planner.py` — Query decomposition + HyDE generation
- `models.py` — `ListeningEvent` model (Phase 3)
- `routers/history.py` — Play/skip/save event endpoints (Phase 3)

### Modified files
- `ml/rag_playlist_generator.py` — Core RAG pipeline (Phases 1, 2, 4, 5)
- `ml/embedding_service.py` — Possibly adjust for HyDE embedding
- `config.py` — Add planner + taste profile settings
- `schemas.py` — Add `why_track` field, `ListeningEvent` schemas
- `main.py` — Include history router
- `frontend/src/components/BottomPlayer.vue` — Emit play/skip events (Phase 3)

### Unchanged files
- `ml/mood_classifier.py` — No changes needed
- `ml/sentiment.py` — No changes needed
- `ml/lyrics_fetcher.py` — No changes needed
- `utils/spotify.py` — No changes needed
- `routers/auth.py` — No changes needed
- `routers/songs.py` — No changes needed
- `routers/playlists.py` — No changes needed
- `routers/analytics.py` — No changes needed

---

## 6. Success Metrics

After implementation, measure:

| Metric | Current (estimate) | Target |
|--------|-------------------|--------|
| Recall@10 on abstract queries | ~60% | ~85% |
| User satisfaction (subjective) | Baseline | +30% |
| Playlist diversity (unique moods per playlist) | ~1-2 moods | ~3-4 moods |
| Time to first good recommendation | Baseline | -40% (metadata pre-filter) |
| Per-track explanation coverage | 0% | 100% |

---

## 7. References

1. SoulTuner-Agent — github.com/hgsanyang/SoulTuner-Agent
2. Spotify System Design — grokkingthesystemdesign.com
3. Inside Spotify's Recommendation System — music-tomorrow.com (2025)
4. Bandits and Agents: Netflix and Spotify (2026) — philippdubach.com
5. Production-Ready RAG Architecture Patterns (2026) — agileinfoways.com
6. Advanced RAG 2026: HyDE, Reranking & Hybrid Search — vucense.com
7. RAG in Production 2026: Advanced Retrieval Strategies — n1n.ai
8. Building Production RAG: Architecture, Chunking, Evaluation — premai.io
9. MusicRec-RAG — github.com/hhc25/MusicRec-RAG
10. music-recommender-rag — github.com/camsset-developer/music-recommender-rag
11. PyTorch RAG Architecture: Production Latency Budgets — markaicode.com
12. Advanced RAG Techniques (Neo4j) — neo4j.com/blog/genai
13. Haystack Query Expansion Cookbook — haystack.deepset.ai
14. Advanced RAG: Re-ranking, Query Expansion, and HyDE — kindatechnical.com
15. Spotify Research: Contextual and Sequential User Embeddings — research.spotify.com