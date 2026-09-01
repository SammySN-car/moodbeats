# MoodBeats — AI Context & Architecture Source of Truth (v6.0)

> **FOR AI ASSISTANTS & DEVELOPERS**: This file is the single source of truth for the MoodBeats project.
> Read this ENTIRE file before making any changes, refactoring code, or answering questions.

---

## 1. Project Overview

- **Project**: MoodBeats — AI-powered music discovery platform with PyTorch Hybrid RAG pipeline.
- **Developer**: Samar.
- **Stack**: Vue 3 (Vite) + FastAPI + SQLAlchemy/SQLite + PyTorch + Ollama (llama3.2).
- **GitHub**: `https://github.com/SammySN-car/moodbeats` (AGPL-3.0)
- **Version**: v6.0.0

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
  MOODBEATS_AI_CONTEXT.md          ← THIS FILE
  CHANGELOG.md                     ← Living improvement tracker (updated after every task)
  README.md, LICENSE (AGPL-3.0), .gitignore, DESIGN_SYSTEM.md, USER_FLOW.md
  backend/
    main.py                        FastAPI app v6.0, CORS, router registration
    config.py                      Settings (TASTE_WEIGHT=0.3, RRF_K=60, MMR_LAMBDA=0.7, etc.)
    database.py                    SQLAlchemy engine + session
    models.py                      User, Song, ListeningEvent, Playlist, PlaylistItem
    schemas.py                     Pydantic v2 schemas
    moodbeats.db                   SQLite database (0.19 MB)
    utils/
      auth.py                      JWT auth, bcrypt
      spotify.py                   oEmbed + iTunes search + audio extraction
    ml/
      embedding_service.py         Bi-encoder, cross-encoder, PyTorch tensor ops
      rag_playlist_generator.py    RRF fusion, MMR diversity, AI DJ synthesis, taste blending
      query_planner.py             Ollama-based query decomposition, HyDE, mood normalization
      mood_classifier.py           5-mood rule classifier
      lyrics_fetcher.py            Lyrics.ovh API
      sentiment.py                 DistilBERT sentiment
    routers/
      auth.py                      /api/auth (register, login, me)
      songs.py                     /api/songs (CRUD, search, import, import-itunes, youtube-id)
      playlists.py                 /api/playlists (generate, create, list, delete)
      listening.py                 /api/listening (event, history, taste)
      analytics.py                 /api/analytics (mood-distribution, stats)
  frontend/
    src/
      App.vue, main.js, router.js, style.css
      api/client.js                Axios with JWT interceptor
      composables/usePlayer.js     Global audio state + feedback events (fire-and-forget)
      views/Login.vue, Signup.vue, Dashboard.vue
      components/
        BottomPlayer.vue           Persistent bottom player with YouTube drawer
        ImportSong.vue             Artist discography + track search + "In Library" badge
        SongLibrary.vue            Library with play_count/skip_count/saved badges
        MoodDiscover.vue           AI DJ prompt + taste indicator + recommendations
        MoodAnalytics.vue          KPI cards + mood chart
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
| `/api/songs` | GET | User's song library |
| `/api/songs` | POST | Import Spotify URL |
| `/api/songs/{id}` | GET | Song detail with feedback stats |
| `/api/songs/{id}` | DELETE | Remove from library |
| `/api/songs/search?q=...` | GET | Live track search |
| `/api/songs/artist?name=...&limit=50` | GET | Artist discography |
| `/api/songs/import-itunes` | POST | Import by title+artist (iTunes) |
| `/api/songs/youtube-id?title=...&artist=...` | GET | Resolve YouTube Topic ID |

### Playlists
| Endpoint | Method | Description |
|---|---|---|
| `/api/playlists/generate` | POST | RAG + AI DJ playlist generation |
| `/api/playlists` | GET | List all playlists |
| `/api/playlists` | POST | Create manual playlist |
| `/api/playlists/{id}` | DELETE | Delete playlist |

### Listening Feedback
| Endpoint | Method | Description |
|---|---|---|
| `/api/listening/event` | POST | Record play/skip/save event |
| `/api/listening/history` | GET | Recent listening history |
| `/api/listening/taste` | POST | Force recompute taste vector |

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
- **Demo songs**: User `demo@test.com` / `demo1234` (user_id=15) has 5 seeded songs, 48 total in DB.

---

## 6. Code Style

- **User style**: Notebook-style with clear section headers, step-by-step print statements, descriptive comments.
- **PowerShell**: Heredocs don't work, triple-quoted strings mangle, backticks cause errors — use Task agents or Python scripts for complex edits.
- **Database**: SQLite, relative URL (`sqlite:///./moodbeats.db`), scripts must run from `backend/`.
- **Before pushing**: User wants to test everything first.
- **CHANGELOG.md**: Must be updated after every task.

---

## 7. Testing

### E2E Test Phases (all passing)
1. Frontend loads
2. Auth (register + login)
3. Library (songs list)
4. Events (play/skip/save)
5. Aggregates (play_count, skip_count)
6. History (listening history)
7. Taste (taste vector recomputation)
8. RAG generate (playlist generation)
9. Song detail (feedback fields)

### Running Tests
```bash
cd backend
python -c "from main import app; print('Import OK')"
python -c "from ml.rag_playlist_generator import pytorch_database_rag_search; print('RAG OK')"
```

---

## 8. Git Status

- **Last commit**: `29fbdd7` — "Add feedback loop, taste profile, and import system"
- **Pushed to**: `https://github.com/SammySN-car/moodbeats` (main branch)
- **Working tree**: Clean (all changes committed)
