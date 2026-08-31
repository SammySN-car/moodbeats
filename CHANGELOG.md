# MoodBeats — Improvement Tracker

> Living document. Updated after every task.
> Sections: **Planned** → **In Progress** → **Done** → **Discovered (bugs/ideas)**

---

## 🔴 CRITICAL — Must Do First

- [ ] **Feedback Loop / Implicit Signals**
  - Add `play_count`, `skip_count`, `saved`, `last_played_at`, `listening_duration_sec` to Song model or new `ListeningEvent` model
  - Wire frontend play/stop events back to API
  - Impact: Unlocks all personalization

- [ ] **User Taste Profile Vector**
  - Compute per-user taste vector by averaging embeddings of top-played/saved songs
  - Bias RAG results toward actual user taste, not just the prompt
  - Impact: Recommendations feel personal, not generic

---

## 🗑️ REDUNDANT — Remove or Consolidate

- [ ] **`ml/music_corpus.py` — empty file**
  - 0 lines, 0 imports, 0 references anywhere
  - Action: Delete it

- [ ] **iTunes search duplicated 3 times**
  - `utils/spotify.py` → `search_spotify_tracks()` — used by songs router
  - `routers/songs.py` → `search_artist_discography()` — inline iTunes call
  - `ml/rag_playlist_generator.py` → `_get_dynamic_public_discoveries()` + `enrich_discovered_songs()` — inline iTunes calls
  - Same API endpoint, same pattern, 3 different copies
  - Action: Consolidate into one `utils/spotify.py` function, import everywhere

- [ ] **YouTube scraper `find_verified_official_audio_yt()` in songs.py**
  - Regex-parses YouTube HTML `ytInitialData` — breaks whenever YouTube changes structure
  - Heavy, fragile, 50 lines of scraping for something `yt-dlp` does in 3 lines
  - Action: Replace with `yt-dlp` or move to a separate utility with proper error handling

- [ ] **Hardcoded confidence scores in `mood_classifier.py`**
  - Returns fixed values: 0.94, 0.91, 0.88, 0.92, 0.86, 0.80, 0.78
  - These are not real probabilities — they're magic numbers pretending to be confidence
  - Action: Either compute real confidence or rename to `mood_strength` / drop the field

- [ ] **`config.py` → `OLLAMA_TIMEOUT_SECONDS` and `OLLAMA_MAX_TOKENS`**
  - Only used in one place (`rag_playlist_generator.py` → `generate_ai_dj_synthesis`)
  - Not truly redundant, but worth noting: Ollama settings are tightly coupled to one function
  - Action: Keep for now, but if Ollama is removed later, clean these up too

- [ ] **Song model `lyrics` field — stored but never used after embedding**
  - Lyrics are fetched, sentiment-analyzed, then embedded into the song profile text
  - The raw lyrics text is stored in DB (`lyrics` column) but never read again anywhere
  - Action: Either remove the column or surface lyrics in the frontend player

- [ ] **`preview_url` stored but inconsistently used**
  - Stored on Song model, but the player uses Spotify preview or YouTube — not this URL
  - The 30s preview playback in the frontend likely goes through YouTube embed, not `preview_url`
  - Action: Verify actual usage. If unused, remove to simplify the model

- [ ] **Duplicate `__pycache__` directories**
  - 14 `.pyc` files across 4 `__pycache__` folders committed to disk
  - Action: Add `__pycache__/` and `*.pyc` to `.gitignore`

---

## 🟡 HIGH — Important Next Steps

- [ ] **Per-track "Why This Track?" explanations**
  - Extend `ai_dj_note` from playlist-level to per-track
  - Spotify research: recommendations with explanations have **4x higher engagement**
  - Impact: Users understand and trust the recommendations

- [ ] **Listening History endpoint**
  - Add `GET /api/history` returning recently played tracks with timestamps
  - Powers "recently played" UI in frontend
  - Impact: Retention + data for taste profile

- [ ] **Song Similarity / "More Like This"**
  - `GET /api/songs/{id}/similar` — cosine similarity against user's other song embeddings
  - Very cheap (just math on existing vectors)
  - Impact: Natural discovery flow

---

## 🟢 MEDIUM — Improvements

- [ ] **Adaptive hybrid weights in RAG**
  - Current: hardcoded 0.65 dense + 0.35 sparse
  - Abstract prompts ("rainy night vibes") → weight dense higher
  - Specific prompts ("Eminem tracks") → weight sparse/BM25 higher
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

## 🔵 NICE TO HAVE

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

- [ ] **YouTube scraper hardening**
  - Current: regex parsing of `ytInitialData` HTML — fragile, breaks on YouTube changes
  - Use `yt-dlp` library for reliable extraction
  - Impact: Stability

---

## ✅ DONE

> (Tasks completed will be logged here with date and details)

---

## 🐛 BUGS FOUND

> (Bugs discovered during work will be logged here)

---

## 💡 IDEAS (Unsorted)

> (New ideas that come up during implementation)

- Mood-based color theming: auto-shift the UI accent color based on the currently playing track's mood
- Spotify OAuth: replace iTunes search with real Spotify Web API for higher-quality metadata
- Offline mode: cache song metadata and embeddings for offline browsing
- Collaborative playlists: share playlists between users
- Song lyrics display in the player (synced lyrics if available)