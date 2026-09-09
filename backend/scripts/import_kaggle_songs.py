"""
Import 114K Spotify songs from Kaggle dataset into MoodBeats database.
Also builds FAISS index for fast similarity search.

Usage:
    1. Download dataset.csv from https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset
    2. Place it in backend/data/dataset.csv
    3. Run from backend/: python scripts/import_kaggle_songs.py
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models import Base, Song
from config import settings
from ml.knowledge_service import knowledge_service

CSV_PATH = Path(__file__).parent.parent / 'data' / 'dataset.csv'
BATCH_SIZE = 128
DEMO_USER_ID = 15


def load_csv():
    if not CSV_PATH.exists():
        print(f"ERROR: Dataset not found at {CSV_PATH}")
        print("Download from: https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset")
        print("Place dataset.csv in backend/data/")
        sys.exit(1)
    df = pd.read_csv(CSV_PATH)
    df = df.drop_duplicates(subset=['track_id'])
    print(f"Loaded {len(df):,} tracks from {CSV_PATH.name}")
    return df


def classify_batch(row):
    features = {
        'energy': float(getattr(row, 'energy', 0.5)),
        'valence': float(getattr(row, 'valence', 0.5)),
        'danceability': float(getattr(row, 'danceability', 0.5)),
        'acousticness': float(getattr(row, 'acousticness', 0.3)),
        'instrumentalness': float(getattr(row, 'instrumentalness', 0.0)),
        'speechiness': float(getattr(row, 'speechiness', 0.05)),
        'tempo': float(getattr(row, 'tempo', 120)),
    }
    mood, confidence, _ = knowledge_service.classify_mood_from_features(features)
    return mood, confidence


def build_song_text(row):
    """Use canonical knowledge_service profile builder for embedding alignment."""
    features = {
        'energy': float(getattr(row, 'energy', 0.5)),
        'valence': float(getattr(row, 'valence', 0.5)),
        'danceability': float(getattr(row, 'danceability', 0.5)),
        'acousticness': float(getattr(row, 'acousticness', 0.0)),
        'instrumentalness': float(getattr(row, 'instrumentalness', 0.0)),
        'speechiness': float(getattr(row, 'speechiness', 0.05)),
        'tempo': float(getattr(row, 'tempo', 120.0)),
    }
    return knowledge_service.build_song_profile(
        title=str(getattr(row, 'track_name', 'Unknown'))[:200],
        artist=str(getattr(row, 'artists', 'Unknown')).strip("[]'")[:200],
        genre=str(getattr(row, 'track_genre', 'unknown')),
        audio_features=features
    )


def generate_embeddings(df):
    from ml.embedding_service import get_batch_embeddings_tensor

    print(f"\nGenerating embeddings for {len(df):,} songs...")
    all_embeddings = []
    total_batches = (len(df) + BATCH_SIZE - 1) // BATCH_SIZE
    start = time.time()

    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1

        texts = [build_song_text(row) for row in batch.itertuples()]
        embeddings = get_batch_embeddings_tensor(texts)
        all_embeddings.append(embeddings.cpu().numpy())

        elapsed = time.time() - start
        eta = (elapsed / batch_num) * (total_batches - batch_num) if batch_num > 0 else 0
        if batch_num % 5 == 0 or batch_num == total_batches:
            print(f"  Batch {batch_num}/{total_batches} | {i+len(batch):,}/{len(df):,} | ETA: {eta:.0f}s")

    return np.vstack(all_embeddings)


def import_to_database(df, embeddings):
    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as session:
        existing = session.query(Song).filter(Song.user_id == DEMO_USER_ID).count()
        if existing > 0:
            print(f"\nUser {DEMO_USER_ID} has {existing:,} songs.")
            if "--force" in sys.argv or "-y" in sys.argv:
                resp = 'y'
            else:
                try:
                    resp = input("Clear and re-import? (y/n): ").strip().lower()
                except EOFError:
                    resp = 'n'
            if resp != 'y':
                print("Aborted.")
                return 0
            session.query(Song).filter(Song.user_id == DEMO_USER_ID).delete()
            session.commit()
            print(f"Cleared {existing:,} songs.")

    imported = 0
    skipped = 0

    with Session(engine) as session:
        for idx, row in enumerate(df.itertuples()):
            try:
                if pd.isna(getattr(row, 'track_name', None)) or pd.isna(getattr(row, 'track_id', None)):
                    skipped += 1
                    continue

                track_id = str(row.track_id)
                title = str(getattr(row, 'track_name', 'Unknown'))[:200]
                artist = str(getattr(row, 'artists', 'Unknown')).strip("[]'")[:200]
                energy = float(getattr(row, 'energy', 0.5))
                valence = float(getattr(row, 'valence', 0.5))
                tempo = float(getattr(row, 'tempo', 120))
                danceability = float(getattr(row, 'danceability', 0.5))
                duration_ms = float(getattr(row, 'duration_ms', 0))

                mood, confidence = classify_batch(row)

                song = Song(
                    user_id=DEMO_USER_ID,
                    title=title,
                    artist=artist,
                    spotify_id=track_id,
                    spotify_url=f"https://open.spotify.com/track/{track_id}",
                    album_art_url=None,
                    preview_url=None,
                    duration_sec=duration_ms / 1000.0,
                    tempo=tempo,
                    energy=energy,
                    danceability=danceability,
                    valence=valence,
                    mood=mood,
                    mood_confidence=confidence,
                    lyrics_sentiment=0.0,
                    embedding=json.dumps(embeddings[idx].tolist()),
                    genre=str(getattr(row, 'track_genre', 'unknown')),
                    acousticness=float(getattr(row, 'acousticness', 0.0)),
                    instrumentalness=float(getattr(row, 'instrumentalness', 0.0)),
                    speechiness=float(getattr(row, 'speechiness', 0.0)),
                    liveness=float(getattr(row, 'liveness', 0.0)),
                )
                session.add(song)
                imported += 1

                if imported % BATCH_SIZE == 0:
                    session.commit()
                    print(f"  Imported {imported:,} songs...")

            except Exception as e:
                skipped += 1
                continue

        session.commit()

    print(f"\nImport complete: {imported:,} imported, {skipped:,} skipped")
    return imported


def build_faiss_index():
    print("\nBuilding FAISS index...")
    try:
        import faiss
    except ImportError:
        print("ERROR: faiss-cpu is not installed. Install it with: pip install faiss-cpu")
        return

    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as session:
        songs = session.query(Song).filter(
            Song.user_id == DEMO_USER_ID,
            Song.embedding.isnot(None)
        ).all()

        if not songs:
            print("No songs with embeddings found.")
            return

        embeddings = np.array([
            json.loads(s.embedding) for s in songs
        ]).astype('float32')

        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)
        faiss.normalize_L2(embeddings)
        index.add(embeddings)

        index_path = Path(__file__).parent.parent / 'ml' / 'song_index.faiss'
        faiss.write_index(index, str(index_path))

        song_ids = [songs[i].id for i in range(len(songs))]
        mapping_path = Path(__file__).parent.parent / 'ml' / 'song_id_mapping.json'
        with open(mapping_path, 'w') as f:
            json.dump(song_ids, f)

        print(f"FAISS index: {index.ntotal:,} vectors, dim={dimension}")
        print(f"Saved: {index_path}")


def main():
    print("=" * 60)
    print("MOODBEATS SONG IMPORTER")
    print("=" * 60)

    knowledge_service.load()
    df = load_csv()
    embeddings = generate_embeddings(df)
    imported = import_to_database(df, embeddings)

    if imported > 0:
        build_faiss_index()

    stats = knowledge_service.get_stats()
    print(f"\n{'=' * 60}")
    print("DONE")
    print(f"{'=' * 60}")
    print(f"Songs imported: {imported:,}")
    print(f"Mood categories: {stats['mood_categories']}")
    print(f"Genre clusters: {stats['genre_clusters']}")


if __name__ == '__main__':
    main()