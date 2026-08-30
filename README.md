# 🎵 MoodBeats

> **Spotify-Native AI Music Mood Classifier & Database-Driven PyTorch Hybrid RAG Playlist Builder**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![Vue 3](https://img.shields.io/badge/Vue.js-3.0%2B-4FC08D.svg)](https://vuejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Key Highlights

* ⚡ **Pure PyTorch Hybrid RAG Search**: Dense 384d semantic vectors (`all-MiniLM-L6-v2`) + Sparse BM25Okapi lexical matching over SQLite database library songs.
* 🧠 **Neural Cross-Encoder Reranking**: Sub-50ms deep transformer cross-attention using `cross-encoder/ms-marco-MiniLM-L-6-v2`.
* 🎙️ **Local AI DJ (Ollama LLM)**: Dynamic playlist titles, emotional curator liner notes, and 50+ non-repeating recommendations per vibe.
* 💾 **100% Zero-Storage Philosophy**: 0 MB disk space. In-memory 4-feature audio extraction (`tempo`, `energy`, `danceability`, `valence`) in RAM (< 0.3s).
* 🎧 **Dual-Stream Playback**: Persistent in-app audio player supporting 30s preview clips and verified official studio YouTube streams.
* 🎤 **50-Song Artist Discography**: 1-click exploration of complete artist catalogs with live audio previews and instant library importing.
* 🌿 **Calm Spotify-Dark UI**: Full-width, space-efficient, responsive Vue 3 interface.

---

## 📁 Repository Overview

* [`ARCHITECTURE_FLOW_AND_AUDIT.md`](./ARCHITECTURE_FLOW_AND_AUDIT.md): Detailed system architecture, mathematical formulations, and component audits.
* [`MOODBEATS_AI_CONTEXT.md`](./MOODBEATS_AI_CONTEXT.md): Complete single-source-of-truth context guide for AI assistants and developers.
* [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md): Full implementation plan, milestones, and verification benchmarks.
* `backend/`: FastAPI backend with PyTorch neural pipeline, Librosa audio engine, and SQLite database.
* `frontend/`: Vue 3 + Vite SPA with persistent dual-mode floating player.

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** to start discovering music!

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
