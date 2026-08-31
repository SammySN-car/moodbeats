# MoodBeats

AI-powered music discovery platform with a Retrieval-Augmented Generation (RAG) pipeline, neural reranking, and real-time audio feature extraction.

> **License:** AGPL-3.0 — see [LICENSE](LICENSE)

---

## What It Does

MoodBeats lets you describe any vibe, mood, or setting in natural language ("late night highway drive in the rain with synthwave vibes") and generates a curated playlist from **your own music library** plus **zero-shot discoveries** of new tracks.

### Core Pipeline

```
User Prompt
  → Bi-Encoder Dense Search (384d embeddings, cosine similarity)
  → BM25 Sparse Lexical Search (keyword matching)
  → Hybrid Convex Fusion (0.65 Dense + 0.35 Sparse)
  → Neural Cross-Encoder Reranking (ms-marco MiniLM)
  → Ollama AI DJ (sequencing + zero-shot recommendations)
  → iTunes Verification (album art + preview streams)
```

### Audio Feature Extraction

No Spotify API key required. Imports via Spotify URL, then:

1. Fetches 30s preview stream from iTunes
2. Converts to WAV via ffmpeg (in-memory, zero disk)
3. Extracts **Tempo (BPM)**, **Energy (RMS)**, **Danceability (onset strength)**, **Valence (spectral brightness)** using librosa
4. Classifies mood from audio features + lyrics sentiment (DistilBERT)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vue 3, Vite, vue-router, chart.js, lucide-vue-next |
| **Backend** | FastAPI, SQLAlchemy, SQLite, PyJWT, bcrypt |
| **ML/NLP** | PyTorch, sentence-transformers, cross-encoders, DistilBERT sentiment |
| **Search** | BM25 (rank_bm25), dense embeddings, hybrid fusion |
| **LLM** | Ollama (llama3.2) for AI DJ synthesis |
| **Metadata** | iTunes Search API, YouTube HTML scraping, lyrics.ovh |

---

## Project Structure

```
moodbeats-redesign/
 backend/
    main.py              # FastAPI app, model pre-warming
    config.py            # Settings (Ollama, thresholds, secrets)
    database.py          # SQLAlchemy engine + session
    models.py            # User, Song, Playlist, PlaylistItem
    schemas.py           # Pydantic request/response models
    routers/
       auth.py          # Register, login, JWT
       songs.py         # Import, search, artist discography, YouTube
       playlists.py     # AI generation, CRUD
       analytics.py     # Mood distribution, stats
    ml/
       embedding_service.py    # Bi-encoder, cross-encoder, embeddings
       rag_playlist_generator.py  # Hybrid search + Ollama DJ
       mood_classifier.py      # Rule-based mood from audio features
       lyrics_fetcher.py       # Lyrics from public API
       sentiment.py            # DistilBERT sentiment analysis
    utils/
        auth.py          # Password hashing, JWT, auth dependency
        spotify.py       # Spotify URL parsing, iTunes search, audio extraction
 frontend/
    src/
        App.vue          # Header, routing, bottom player
        views/           # Login, Signup, Dashboard
        components/      # MoodDiscover, SongLibrary, MoodAnalytics, ImportSong, BottomPlayer
        composables/     # usePlayer (shared audio state)
        api/             # Axios client
 DESIGN_SYSTEM.md         # Aurora UI design tokens & component specs
 USER_FLOW.md             # User flow diagrams
 CHANGELOG.md             # Improvement tracker
 LICENSE                  # AGPL-3.0
```

---

## Getting Started

### Backend

```bash
cd backend
pip install -r requirements.txt
# Requires ffmpeg installed on system
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Ollama (optional, for AI DJ)

```bash
ollama pull llama3.2
# Runs on localhost:11434 by default
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/auth/me` | Current user info |
| GET | `/api/songs` | List user's songs (filter by mood) |
| GET | `/api/songs/search?q=` | Search tracks (iTunes) |
| GET | `/api/songs/artist?name=` | Artist discography |
| POST | `/api/songs/import` | Import from Spotify URL |
| DELETE | `/api/songs/{id}` | Remove song |
| GET | `/api/songs/youtube-id` | Find YouTube stream |
| POST | `/api/playlists/generate` | AI mood playlist |
| POST | `/api/playlists` | Create manual playlist |
| GET | `/api/playlists` | List playlists |
| DELETE | `/api/playlists/{id}` | Delete playlist |
| GET | `/api/analytics/mood-distribution` | Mood breakdown |
| GET | `/api/analytics/stats` | Library stats |

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** — see [LICENSE](LICENSE) for details.

You may use, modify, and distribute this software under the AGPL-3.0 terms. If you modify and run this software as a network service, you must provide the source code of your modified version to all users of that service.