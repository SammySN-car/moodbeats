# MoodBeats — Complete AI Context & Architecture Source of Truth (v5.2)

> **⚠️ FOR AI ASSISTANTS & DEVELOPERS**: This file is the single source of truth for the MoodBeats project.
> Read this ENTIRE file before making any changes, refactoring code, or answering questions.
> Designed for ANY AI coding agent (Cursor, GitHub Copilot, Gemini CLI, Claude Code, Aider, Antigravity, ChatGPT, etc.)

---

## 📌 1. Project Overview & Philosophy

- **Project**: MoodBeats — Spotify-Native AI Music Mood Classifier & Database-Driven PyTorch Hybrid RAG Playlist Builder.
- **Developer**: Samar.
- **Storage Philosophy**: **100% Zero-Storage** — 0 MB disk space. No raw audio files stored. Audio feature extraction runs in RAM (< 0.3s). Full playback streams live on-the-fly via YouTube Topic official audio and Spotify embeds.
- **Deep Learning Layer**: **Pure PyTorch Native Tensors (`torch.Tensor`)** with `torch.inference_mode()` on CPU/CUDA.
- **RAG Architecture**:
  - **Direct Database Search**: RAG operates directly on the user's **actual imported `Song` records** in SQLite.
  - **Bi-Encoder Dense Vectors**: `sentence-transformers/all-MiniLM-L6-v2` with PyTorch L2 normalization & `torch.matmul`.
  - **Sparse Lexical Matching**: `rank_bm25` BM25Okapi scoring across song descriptions & lyrics.
  - **Hybrid Convex Fusion**: Combines dense semantic tensors + sparse lexical tensors (`0.65 * dense + 0.35 * sparse`).
  - **Deep Neural Reranker**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (sub-50ms full cross-attention on candidate songs).
  - **50-Song Discovery Engine**: Generates 50 rich recommendations per prompt by fusing LLM seed songs with verified streaming releases.
  - **Zero-Duplicate Filter**: Canonical song key normalization (`_normalize_song_key`) ensures 0 duplicate tracks or remix repeats.
- **Dual-Stream Playback Engine**:
  - **Mode A (30s Preview)**: Instant HTML5 audio playback of 30-second preview clips with scrubbable progress bar.
  - **Mode B (Full Track)**: Backend queries YouTube official Topic channels for verified studio audio, filtering out reactions, memes, and gameplay videos.
- **UI Aesthetic**: Full-width, calm, space-efficient dark Spotify design system (`src/style.css`).

---

## 📁 2. Project Directory Map

```
moodbeats/
├── MOODBEATS_AI_CONTEXT.md             ← THIS FILE (Complete AI context guide)
├── ARCHITECTURE_FLOW_AND_AUDIT.md      ← System architecture & optimization audit
├── IMPLEMENTATION_PLAN.md              ← Master implementation plan & execution record
├── backend/
│   ├── main.py                         ✅ PyTorch Lifespan Pre-warming + CORS + router registration
│   ├── config.py                       ✅ Settings (50 discoveries, 35s Ollama timeout, thresholds)
│   ├── database.py                     ✅ SQLAlchemy engine + session + PRAGMA FK listener
│   ├── models.py                       ✅ User, Song (4 audio features, UniqueConstraint), Playlist, PlaylistItem
│   ├── schemas.py                      ✅ Pydantic v2 schemas (SuggestedSong, SongResponse, PlaylistResponse)
│   ├── requirements.txt                ✅ PyTorch + Transformers + rank-bm25 + Librosa
│   ├── utils/
│   │   ├── auth.py                     ✅ bcrypt hash, JWT create/decode, get_current_user
│   │   └── spotify.py                  ✅ Public oEmbed + In-Memory 4-Feature Audio Extractor
│   ├── ml/
│   │   ├── lyrics_fetcher.py           ✅ Title-cleaning regex + lyrics.ovh API
│   │   ├── sentiment.py                ✅ DistilBERT sentiment pipeline
│   │   ├── mood_classifier.py          ✅ 5-mood rule classifier (happy, chill, sad, energetic, romantic)
│   │   ├── embedding_service.py        ✅ Pure PyTorch Bi-Encoder & Cross-Encoder Neural Engine
│   │   └── rag_playlist_generator.py   ✅ PyTorch Hybrid RAG + Cross-Encoder + Ollama AI DJ + 50-Track Dedup
│   └── routers/
│       ├── auth.py                     ✅ /api/auth (register, login, me)
│       ├── songs.py                    ✅ /api/songs (search, import, list, detail, delete, artist, youtube-id)
│       ├── playlists.py                ✅ /api/playlists (generate, create, list, delete)
│       └── analytics.py               ✅ /api/analytics (mood-distribution, stats)
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── README.md                       ✅ Frontend developer documentation
    └── src/
        ├── App.vue                     ✅ Root layout, calm top bar & global BottomPlayer mount
        ├── main.js                     ✅ Vue app initialization & router mount
        ├── router.js                   ✅ Route definitions & auth navigation guards
        ├── style.css                   ✅ Full-width calm Spotify-dark design system
        ├── api/
        │   └── client.js               ✅ Axios instance with JWT interceptor & 401 handling
        ├── composables/
        │   └── usePlayer.js            ✅ Global reactive dual-stream audio state
        ├── views/
        │   ├── Login.vue               ✅ Centered glass auth login card
        │   ├── Signup.vue              ✅ Account registration card
        │   └── Dashboard.vue           ✅ Tabbed interface (Discover, Library, Search & Import, Analytics)
        └── components/
            ├── BottomPlayer.vue        ✅ Persistent floating bottom player with YouTube stream drawer
            ├── ImportSong.vue          ✅ Artist Discography (50 tracks) & Track Search / URL Import
            ├── SongLibrary.vue         ✅ Real-time search filter + Mood pills + Spotify embeds
            ├── MoodDiscover.vue        ✅ AI DJ prompt input, liner notes, and 50-song discovery grid
            └── MoodAnalytics.vue       ✅ KPI cards (Total Songs, Avg BPM, Energy) & Mood Doughnut Chart
```

---

## 📡 3. REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | `POST` | Create new user account |
| `/api/auth/login` | `POST` | Authenticate and return JWT access token |
| `/api/songs/search?q=...` | `GET` | Live public track metadata search |
| `/api/songs/artist?name=...` | `GET` | Fetch top 50 official tracks for any artist |
| `/api/songs/import` | `POST` | Ingest Spotify URL, extract 4 audio features in-memory, store 384d embedding |
| `/api/songs` | `GET` | Fetch user's saved song library |
| `/api/songs/{id}` | `DELETE` | Remove song from user's library |
| `/api/songs/youtube-id?title=...&artist=...` | `GET` | Resolve verified official YouTube Topic studio audio ID |
| `/api/playlists/generate` | `POST` | Run PyTorch Hybrid RAG + Cross-Encoder + Ollama AI DJ on vibe prompt |
| `/api/analytics/stats` | `GET` | Return total songs, average BPM, and average energy % |
| `/api/analytics/mood-distribution` | `GET` | Return counts of songs categorized by mood |

---

## 🎧 4. Verified Dual-Stream Playback Engine

1. **30-Second Preview Stream**:
   * Uses HTML5 `Audio(track.preview_url)` in `usePlayer.js`.
   * Fast, zero-login, interactive scrubber.
2. **Verified Official Studio YouTube Stream**:
   * Resolved by `/api/songs/youtube-id`.
   * Targets official YouTube Topic channels (`"{Artist} - {Title} Topic"`) and official audio distributor releases.
   * Strictly filters out non-music videos (reactions, gameplay, memes, tutorials, 10-hour loops).
   * Streamed live into the docked bottom player bar with 0 MB disk space used.

---

## 🛡️ 5. Zero-Duplicate Recommendation Engine

All outputs pass through canonical key normalization:

```python
def _normalize_song_key(title: str, artist: str = "") -> str:
    # Strips (Remix), [Slowed + Reverb], [Sped Up], (feat. X), (Official Audio), etc.
    t = re.sub(r'[\(\[\{].*?[\)\]\}]', '', title)
    t = re.sub(r'[-–—].*$', '', t)
    t = re.sub(r'[^\w\s]', '', t).strip().lower()
    
    a = re.sub(r'[\(\[\{].*?[\)\]\}]', '', artist)
    a = re.sub(r'[^\w\s]', '', a).strip().lower()
    a_first = a.split()[0] if a else ""
    return f"{t}_{a_first}"
```

* **Cross-Boundary Filter**: Library songs are automatically excluded from the recommendation output.
* **Remix / Edit Rejection**: Prevents duplicate versions of the same underlying track from appearing in the 50 results.
