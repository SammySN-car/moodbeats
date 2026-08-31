# MoodBeats â€” Improvement Tracker

> Living document. Updated after every task.
> Sections: **Planned** â†’ **In Progress** â†’ **Done** â†’ **Discovered (bugs/ideas)**

---

## ðŸ”´ CRITICAL â€” Must Do First

- [ ] **Feedback Loop / Implicit Signals**
  - Add `play_count`, `skip_count`, `saved`, `last_played_at`, `listening_duration_sec` to Song model or new `ListeningEvent` model
  - Wire frontend play/stop events back to API
  - Impact: Unlocks all personalization

- [ ] **User Taste Profile Vector**
  - Compute per-user taste vector by averaging embeddings of top-played/saved songs
  - Bias RAG results toward actual user taste, not just the prompt
  - Impact: Recommendations feel personal, not generic

---

## ðŸ—‘ï¸ REDUNDANT â€” Remove or Consolidate

- [x] **`ml/music_corpus.py` â€” empty file**
  - Deleted. 0 lines, 0 imports, 0 references.
  - Completed: 2026-08-31

- [x] **iTunes search duplicated 3 times**
  - Consolidated into `utils/spotify.py` with 4 functions:
    - `search_itunes()` â€” raw iTunes API (single source of truth)
    - `search_spotify_tracks()` â€” normalized search results
    - `search_artist_discography()` â€” artist discography with dedup
    - `verify_track_on_itunes()` â€” single track verification
  - All callers (`routers/songs.py`, `ml/rag_playlist_generator.py`) now import from `utils/spotify.py`
  - Completed: 2026-08-31

- [x] **YouTube scraper `find_verified_official_audio_yt()` in songs.py**
  - Replaced 50-line regex HTML scraper with `find_youtube_video_id()` using `yt-dlp`
  - Added `yt-dlp>=2024.0.0` to `requirements.txt`
  - Completed: 2026-08-31

- [x] **Hardcoded confidence scores in `mood_classifier.py`**
  - Renamed return value from `confidence` to `mood_strength` with docstring clarifying it's not a real probability
  - Completed: 2026-08-31

- [x] **Song model `lyrics` column â€” stored but never used after embedding**
  - Removed `lyrics` column from `models.py`
  - `lyrics_sentiment` still stored (used by mood classifier)
  - Raw lyrics fetched, sentiment-analyzed, embedded into profile text â€” then discarded (correct behavior)
  - Completed: 2026-08-31

- [ ] **`preview_url` stored but inconsistently used**
  - VERIFIED: `preview_url` IS used â€” required by `extract_audio_features_from_preview()` to download 30s audio for feature extraction
  - Kept. Not redundant.

- [x] **Duplicate `__pycache__` directories**
  - Handled by `.gitignore` â€” excluded from all git operations
  - Completed: 2026-08-31

---

## ðŸŸ¡ HIGH â€” Important Next Steps

- [ ] **Per-track "Why This Track?" explanations**
  - Extend `ai_dj_note` from playlist-level to per-track
  - Spotify research: recommendations with explanations have **4x higher engagement**
  - Impact: Users understand and trust the recommendations

- [ ] **Listening History endpoint**
  - Add `GET /api/history` returning recently played tracks with timestamps
  - Powers "recently played" UI in frontend
  - Impact: Retention + data for taste profile

- [ ] **Song Similarity / "More Like This"**
  - `GET /api/songs/{id}/similar` â€” cosine similarity against user's other song embeddings
  - Very cheap (just math on existing vectors)
  - Impact: Natural discovery flow

---

## ðŸŸ¢ MEDIUM â€” Improvements

- [ ] **Adaptive hybrid weights in RAG**
  - Current: hardcoded 0.65 dense + 0.35 sparse
  - Abstract prompts ("rainy night vibes") â†’ weight dense higher
  - Specific prompts ("Eminem tracks") â†’ weight sparse/BM25 higher
  - Impact: Better retrieval quality per query type

- [ ] **Fast-path for simple queries**
  - If prompt <5 words and contains known mood keywords, skip cross-encoder reranking
  - Direct embedding similarity search
  - Impact: Lower latency for common queries

- [ ] **Playlist edit operations**
  - Add/remove individual tracks from existing playlists
  - Reorder tracks within a playlist
  - Duplicate a playlist
  - Currently: can only create or delete
  - Impact: Basic CRUD completeness

- [ ] **Smart Queue**
  - Auto-fill next track based on similarity when current track ends
  - Or let user manually queue tracks
  - Currently: nothing plays after track ends
  - Impact: Continuous listening experience

---

## ðŸ”µ NICE TO HAVE

- [ ] **Daily Auto-Mix**
  - Generate "Daily Mix" on first login based on recent listening patterns
  - No prompt required
  - Impact: Retention, passive discovery

- [ ] **Artist/Album metadata enrichment**
  - Store `album_name`, `genre`, `release_date` from iTunes (already fetched but discarded)
  - Enables better filtering and discovery
  - Impact: Richer library view

- [ ] **Embedding model upgrade**
  - Current: `all-MiniLM-L6-v2` (general-purpose text, ~59 MTEB)
  - Options: `Qwen3-Embedding-8B` (70.58 MTEB) or music-specific models
  - Impact: Better semantic search quality

- [ ] **Listening Insights / Stats**
  - Top tracks this week vs this month
  - Mood trends over time
  - Genre distribution chart
  - Currently: only mood distribution + basic averages
  - Impact: Engaging analytics dashboard

---

## âœ… DONE

### 2026-08-31 â€” Redundant Code Cleanup
- Deleted `ml/music_corpus.py` (empty file)
- Consolidated iTunes search: 3 duplicated implementations â†’ 1 unified `search_itunes()` in `utils/spotify.py`
- Added 3 new consolidated functions: `search_artist_discography()`, `verify_track_on_itunes()`, `search_spotify_tracks()`
- Updated `routers/songs.py` to use consolidated functions
- Updated `ml/rag_playlist_generator.py` to use consolidated functions
- Replaced YouTube HTML scraper (50 lines regex) with `yt-dlp` (3 lines)
- Added `yt-dlp>=2024.0.0` to `requirements.txt`
- Renamed `mood_confidence` â†’ `mood_strength` in `mood_classifier.py` return
- Removed unused `lyrics` column from Song model
- Verified `preview_url` IS used (audio feature extraction) â€” kept
- Added `.gitignore` excluding `__pycache__`, `.pyc`, `node_modules`, `.db`
- Added AGPL-3.0 LICENSE (full text)
- Added README.md with architecture, API docs, setup instructions
- Added CHANGELOG.md improvement tracker
- Pushed to GitHub: https://github.com/SammySN-car/moodbeats

### 2026-08-30 â€” Initial Aurora Redesign
- Complete Vue 3 frontend with Aurora warm-dark theme
- FastAPI backend with PyTorch RAG pipeline
- Hybrid search: dense embeddings + BM25 + cross-encoder rerank
- Audio feature extraction: tempo, energy, danceability, valence (librosa)
- Ollama AI DJ for playlist generation

---

## ðŸ› BUGS FOUND

> (Bugs discovered during work will be logged here)

---

## ðŸ’¡ IDEAS (Unsorted)

> (New ideas that come up during implementation)

- Mood-based color theming: auto-shift the UI accent color based on the currently playing track's mood
- Spotify OAuth: replace iTunes search with real Spotify Web API for higher-quality metadata
- Offline mode: cache song metadata and embeddings for offline browsing
- Collaborative playlists: share playlists between users
- Song lyrics display in the player (synced lyrics if available)