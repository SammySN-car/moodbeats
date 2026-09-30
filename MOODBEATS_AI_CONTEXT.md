# MoodBeats — AI Context & Architecture Source of Truth (v6.1)

> **FOR AI ASSISTANTS & DEVELOPERS**: This file is the single source of truth for the MoodBeats project.
> Read this ENTIRE file before making any changes, refactoring code, or answering questions.

---

## 1. Project Overview

- **Project**: MoodBeats — AI-powered music discovery platform with PyTorch Hybrid RAG pipeline.
- **Developer**: Samar.
- **Stack**: Vue 3 (Vite) + FastAPI + SQLAlchemy/SQLite + PyTorch + Ollama (llama3.2).
- **GitHub**: `https://github.com/SammySN-car/moodbeats` (AGPL-3.0)
- **Version**: v6.1.0

### Core Architecture
- **100% Zero-Storage**: No raw audio files. Audio feature extraction runs in RAM.
- **PyTorch Native**: Bi-encoder, cross-encoder, RRF fusion, MMR diversity — all pure PyTorch tensors.
- **RAG Pipeline**: Query Planner → Metadata Pre-Filter → Dense+Sparse Retrieval → RRF Fusion → Cross-Encoder Rerank → MMR Diversity → AI DJ Synthesis.
- **Feedback Loop**: Play/skip/save events update song aggregates; taste vector computed from top-played songs.
- **Dual-Stream Playback**: 30s iTunes previews + YouTube Topic full tracks.

---

## 2. Directory Map

```
moodbeats-redesign/
  MOODBEATS_AI_CONTEXT.md          <- THIS FILE (v6.1 source of truth)
  CHANGELOG.md                     <- Living improvement tracker (updated after every task)
  README.md, LICENSE (AGPL-3.0), .gitignore, DESIGN_SYSTEM.md, USER_FLOW.md
  ARCHITECTURE_FLOW_AND_AUDIT.md   <- Historical v5.2 audit (superseded by this file)
  rag_upgrade.md                   <- RAG research + upgrade plan
  backend/
    main.py                        FastAPI app, CORS, model pre-warming, router registration
    config.py                      Settings (TASTE_WEIGHT, RRF_K, MMR_LAMBDA, DEMO_USER_ID, ...)
    database.py                    SQLAlchemy engine + session
    models.py                      User, Song, ListeningEvent, Playlist, PlaylistItem (+ utcnow helper)
    schemas.py                     Pydantic v2 request/response schemas
    moodbeats.db                   SQLite database
    utils/
      auth.py                      JWT auth, bcrypt, get_current_user dependency
      spotify.py                   Spotify URL parsing, iTunes search, preview audio extraction
    ml/
      embedding_service.py         Bi-encoder, cross-encoder, PyTorch tensor ops
      rag_playlist_generator.py    RRF fusion, MMR diversity, AI DJ synthesis, taste blending
      query_planner.py             Ollama query decomposition, HyDE, mood normalization
      knowledge_service.py         Mood/genre classification, song profile building
      faiss_service.py             FAISS index over knowledge-base embeddings
      lyrics_fetcher.py            Lyrics.ovh API
      sentiment.py                 DistilBERT sentiment
      music_knowledge_base.json    114K-track corpus (114 genres, 7 mood categories)
      song_index.faiss, song_encoder.pt, song_id_mapping.json
    routers/
      auth.py                      /api/auth (register, login, me)
      songs.py                     /api/songs (list, detail, delete, search, artist, import, youtube-id)
      playlists.py                 /api/playlists (list, detail, create, delete, generate, import-spotify)
      listening.py                 /api/listening (event, history)
      analytics.py                 /api/analytics (mood-distribution, stats)
    scripts/
      genre_classifier.py          Rule-based genre classifier (importlib-loaded by knowledge_service)
      import_kaggle_songs.py       Knowledge-base builder
    tests/                         38 pytest tests (conftest mocks torch/FAISS/spotify_scraper)
  frontend/
    src/
      App.vue, main.js, router.js, style.css
      api/client.js                Axios + JWT interceptor (VITE_API_URL)
      layouts/DefaultLayout.vue    Header, tab nav, bottom player mount
      shared/
        composables/usePlayer.js   Global audio state, preview/full modes, feedback events
        components/BaseBadge.vue, BaseEmptyState.vue, BaseSearchBar.vue, BaseSpinner.vue
      features/
        auth/views/Login.vue, Signup.vue
        home/views/HomeView.vue
        discover/views/DiscoverView.vue
        discover/components/MoodDiscover.vue, PlaylistHistory.vue, PlaylistDetail.vue
        library/views/LibraryView.vue
        library/components/SongLibrary.vue, SongDetail.vue
        import/views/ImportView.vue
        import/components/ImportSong.vue, SpotifyPlaylistImport.vue
        player/components/BottomPlayer.vue
        analytics/views/AnalyticsView.vue
        analytics/components/MoodAnalytics.vue
    src/__tests__/                 20 vitest tests (utils, usePlayer, useAlbumArt)
```

---

## 3. REST API Reference

### Auth
| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | POST | Create account |
| `/api/auth/login` | POST | Login, returns JWT |
| `/api/auth/me` | GET | Current user profile |

### Songs
| Endpoint | Method | Description |
|---|---|---|
| `/api/songs` | GET | User's song library (filter by mood) |
| `/api/songs/count` | GET | Library count |
| `/api/songs/{id}` | GET | Song detail with feedback stats |
| `/api/songs/{id}` | DELETE | Remove from library |
| `/api/songs/search?q=...` | GET | Live track search (iTunes) |
| `/api/songs/artist?name=...&limit=50` | GET | Artist discography |
| `/api/songs/import` | POST | Import from Spotify URL |
| `/api/songs/import-itunes` | POST | Import by title+artist (iTunes) |
| `/api/songs/youtube-id?title=...&artist=...` | GET | Resolve YouTube Topic ID |
| `/api/songs/album-art?...` | GET | Album art lookup/proxy |
| `/api/songs/preview-url?...` | GET | Preview URL lookup |

### Playlists
| Endpoint | Method | Description |
|---|---|---|
| `/api/playlists` | GET | List playlists (items with missing songs filtered) |
| `/api/playlists/{id}` | GET | Playlist detail with full track list |
| `/api/playlists` | POST | Create manual playlist from song IDs |
| `/api/playlists/{id}` | DELETE | Delete playlist |
| `/api/playlists/generate` | POST | RAG + AI DJ playlist generation |
| `/api/playlists/import-spotify` | POST | Import Spotify playlist (creates missing songs with extracted audio features) |

### Listening Feedback
| Endpoint | Method | Description |
|---|---|---|
| `/api/listening/event` | POST | Record play/skip/save/unsave event |
| `/api/listening/history` | GET | Recent listening history |

Note: taste vector is recomputed automatically every 10 events (no manual endpoint).

### Analytics
| Endpoint | Method | Description |
|---|---|---|
| `/api/analytics/stats` | GET | Total songs, avg BPM, avg energy |
| `/api/analytics/mood-distribution` | GET | Song counts by mood |

---

## 4. RAG Pipeline (Current v6.0)

1. **Query Planner** (`query_planner.py`): Ollama decomposes user prompt → HyDE description, mood/tempo/energy extraction, keyword override, stale detection with retry.
2. **Metadata Pre-Filter** (`rag_playlist_generator.py`): Filter songs by mood/tempo/energy BEFORE vector search. Fuzzy mood matching via `normalize_mood()`.
3. **Dense Retrieval**: Bi-encoder (`all-MiniLM-L6-v2`) cosine similarity on PyTorch tensors.
4. **Sparse Retrieval**: BM25Okapi lexical matching on song descriptions.
5. **Taste Blending**: If user has taste_vector, blends with query: `final = (1 - weight) * query + weight * taste`.
6. **RRF Fusion** (`reciprocal_rank_fusion`): Rank-based fusion (k=60), replaces old weighted sum.
7. **Cross-Encoder Rerank**: `ms-marco-MiniLM-L-6-v2` sigmoid-normalized scores.
8. **MMR Diversity** (`mmr_rerank`): Prevents all-same-mood playlists (lambda=0.7).
9. **AI DJ Synthesis**: Ollama generates playlist narrative + per-track explanations + 5-8 external song suggestions.
10. **Zero-Shot Fallback**: When 0 library songs match, Ollama suggests external songs directly.
11. **Enrichment** (`enrich_discovered_songs`): iTunes lookup for album art + preview URLs on suggested songs.

---

## 5. Feedback Loop & Taste Profile

### Event Recording (`listening.py`)
- Frontend sends fire-and-forget POST to `/api/listening/event` on play/skip/save.
- Creates `ListeningEvent` row, updates Song aggregates (play_count, skip_count, saved, last_played_at, total_listen_sec).
- Every 10 events, taste vector is recomputed.

### Taste Vector (`_recompute_taste_vector`)
- Averages embeddings of top-played songs (or saved songs if few plays).
- Stored on User as JSON string (384-dim).
- Blended into RAG query with TASTE_WEIGHT=0.3.

### Known Issues
- **Ollama KV-cache poisoning**: llama3.2 may reuse previous query's response. Workaround: retry on stale detection.
- **Ollama JSON truncation**: num_predict=1500 (main), 1000 (fallback) + JSON repair logic.
- **AI DJ positional indices**: LLM returns [1,2,3] instead of DB IDs [43,44,45] — mapped via positional index step in playlists.py.
- **Spotify Audio Features API deprecated (403s)**: audio features are now extracted locally from iTunes preview audio via librosa.
- **Demo account**: `demo@test.com` / `demo1234` (user_id=15) — large seeded library (~90K songs), 17 playlists.

---

## 6. Code Style

- **User style**: Notebook-style with clear section headers, step-by-step print statements, descriptive comments.
- **PowerShell**: Heredocs don't work, triple-quoted strings mangle, backticks cause errors — use Task agents or Python scripts for complex edits.
- **Database**: SQLite, relative URL (`sqlite:///./moodbeats.db`), scripts must run from `backend/`.
- **Before pushing**: User wants to test everything first.
- **CHANGELOG.md**: Must be updated after every task.

---

## 7. Testing

### Test Suites (all passing — 58 total)
- **Backend**: 38 pytest tests (`backend/tests/`) — auth, songs, playlists, listening, analytics, Spotify import, health. `conftest.py` mocks torch/FAISS/`spotify_scraper` so tests run without model loads.
- **Frontend**: 20 vitest tests (`frontend/src/__tests__/`) — utils, usePlayer, useAlbumArt.

### Running Tests
```bash
cd backend
python -m pytest tests/ -q

cd frontend
npm run test
```

### Linting
```bash
cd backend
ruff check .
```

### Smoke Checks
```bash
cd backend
python -c "from main import app; print('Import OK')"
python -c "from ml.rag_playlist_generator import pytorch_database_rag_search; print('RAG OK')"
```

---

## 8. Git Status

- **Last docs refresh**: 2026-09-30 (this file, v6.1)
- **Pushed to**: `https://github.com/SammySN-car/moodbeats` (main branch)

### Recent History
- `2e8d1ac` docs: add testing status and key features section to README
- `5e599dd` fix: replace deprecated datetime.utcnow() with timezone-aware equivalent
- `2281cd4` fix: repair mojibake encoding in README, CHANGELOG, and SongLibrary
- `e404b6c` fix: 11 UI/UX bugs from sandbox audit
- `5cf6ab8` fix: playlist plays full YouTube songs instead of 30s previews
- `701ae4f` feat: playlist detail page with play/delete + hide empty playlists
- `0c8d39f` fix: restore Spotify import song creation + playlist CRUD endpoints
