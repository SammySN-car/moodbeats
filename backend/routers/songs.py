import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import Song, User
from schemas import SongResponse, SpotifyImportRequest, SpotifySearchResult, iTunesImportRequest
from utils.auth import get_current_user
from utils.spotify import (
    parse_track_id, fetch_spotify_track_info, search_spotify_tracks,
    search_artist_discography, find_youtube_video_id
)
from ml.lyrics_fetcher import fetch_lyrics
from ml.sentiment import analyze_sentiment
from ml.mood_classifier import classify_mood
from ml.embedding_service import get_text_embedding_tensor, build_song_profile_text

router = APIRouter(prefix="/api/songs", tags=["Songs"])


@router.get("/youtube-id")
def get_youtube_id(title: str, artist: Optional[str] = ""):
    """Find official audio on YouTube via yt-dlp."""
    vid = find_youtube_video_id(artist or "", title)
    return {"video_id": vid}


@router.get("/search", response_model=List[SpotifySearchResult])
def search_tracks(
    q: str,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    try:
        return search_spotify_tracks(q.strip(), limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {str(e)}")


@router.get("/artist")
def search_artist(
    name: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Fetch artist discography via consolidated iTunes search."""
    if not name or len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Artist name must be at least 2 characters")
    try:
        return search_artist_discography(name.strip(), limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Artist search failed: {str(e)}")


@router.post("/import", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def import_spotify_song(
    payload: SpotifyImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        track_id = parse_track_id(payload.spotify_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Prevent duplicate imports for the same user
    existing = db.query(Song).filter(Song.user_id == current_user.id, Song.spotify_id == track_id).first()
    if existing:
        return existing

    # 1. Fetch metadata & 4 real audio features in memory (< 0.5s)
    try:
        track_info = fetch_spotify_track_info(payload.spotify_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch track: {str(e)}")

    # 2. Fetch lyrics & analyze sentiment
    lyrics_text = fetch_lyrics(track_info["artist"], track_info["title"])
    sentiment_score = analyze_sentiment(lyrics_text) if lyrics_text else 0.0

    # 3. Classify Mood using audio metrics + sentiment
    audio_features = {
        "tempo": track_info["tempo"],
        "energy": track_info["energy"],
        "danceability": track_info["danceability"],
        "valence": track_info["valence"]
    }
    mood_label, mood_strength = classify_mood(audio_features, sentiment_score)

    # 4. Generate 384d Dense Embedding Vector
    profile_text = build_song_profile_text(
        title=track_info["title"],
        artist=track_info["artist"],
        mood=mood_label,
        tempo=track_info["tempo"],
        energy=track_info["energy"]
    )
    embedding_vec = get_text_embedding_tensor(profile_text)

    # 5. Persist to SQLite Database
    new_song = Song(
        user_id=current_user.id,
        spotify_id=track_info["spotify_id"],
        spotify_url=track_info["spotify_url"],
        title=track_info["title"],
        artist=track_info["artist"],
        album_art_url=track_info["album_art_url"],
        preview_url=track_info["preview_url"],
        duration_sec=track_info["duration_sec"],
        tempo=track_info["tempo"],
        energy=track_info["energy"],
        danceability=track_info["danceability"],
        valence=track_info["valence"],
        lyrics_sentiment=sentiment_score,
        mood=mood_label,
        mood_confidence=mood_strength,
        embedding=json.dumps(embedding_vec)
    )
    db.add(new_song)
    db.commit()
    db.refresh(new_song)
    return new_song


@router.post("/import-itunes", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def import_itunes_song(
    payload: iTunesImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import a song from iTunes by title + artist search."""
    from utils.spotify import search_itunes
    import json

    # Search iTunes
    results = search_itunes(payload.title + " " + payload.artist, limit=1)
    if not results:
        raise HTTPException(status_code=404, detail="Song not found on iTunes")

    track = results[0]
    itunes_id = str(track.get("trackId", ""))

    # Check duplicate
    existing = db.query(Song).filter(
        Song.user_id == current_user.id,
        Song.spotify_id == itunes_id
    ).first()
    if existing:
        return existing

    title = track.get("trackName", payload.title)
    artist = track.get("artistName", payload.artist)
    preview_url = track.get("previewUrl")
    album_art = track.get("artworkUrl100", "")
    duration_ms = track.get("trackTimeMillis", 0)

    # Basic audio features from iTunes (limited — no real analysis)
    # Use reasonable defaults for mood classification
    audio_features = {"tempo": 100.0, "energy": 0.5, "danceability": 0.5, "valence": 0.5}
    mood_label, mood_strength = classify_mood(audio_features, 0.0)

    # Generate embedding
    profile_text = build_song_profile_text(
        title=title, artist=artist, mood=mood_label,
        tempo=100.0, energy=0.5
    )
    embedding_vec = get_text_embedding_tensor(profile_text)

    new_song = Song(
        user_id=current_user.id,
        spotify_id=itunes_id,
        spotify_url=track.get("trackViewUrl", ""),
        title=title,
        artist=artist,
        album_art_url=album_art,
        preview_url=preview_url,
        duration_sec=duration_ms / 1000.0,
        tempo=100.0,
        energy=0.5,
        danceability=0.5,
        valence=0.5,
        lyrics_sentiment=0.0,
        mood=mood_label,
        mood_confidence=mood_strength,
        embedding=json.dumps(embedding_vec)
    )
    db.add(new_song)
    db.commit()
    db.refresh(new_song)
    return new_song


@router.get("", response_model=List[SongResponse])
def list_songs(
    mood: Optional[str] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Song).filter(Song.user_id == current_user.id)
    if mood:
        query = query.filter(Song.mood == mood.lower())
    return query.order_by(Song.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/count")
def count_songs(
    mood: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Song).filter(Song.user_id == current_user.id)
    if mood:
        query = query.filter(Song.mood == mood.lower())
    return {"count": query.count()}


@router.get("/{song_id}", response_model=SongResponse)
def get_song(song_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id, Song.user_id == current_user.id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    return song


@router.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_song(song_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id, Song.user_id == current_user.id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found")
    db.delete(song)
    db.commit()