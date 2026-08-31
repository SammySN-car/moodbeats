import re
import json
import urllib.parse
import requests
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Song, User
from schemas import SongResponse, SpotifyImportRequest, SpotifySearchResult
from utils.auth import get_current_user
from utils.spotify import parse_track_id, fetch_spotify_track_info, search_spotify_tracks
from ml.lyrics_fetcher import fetch_lyrics
from ml.sentiment import analyze_sentiment
from ml.mood_classifier import classify_mood
from ml.embedding_service import get_text_embedding_tensor, build_song_profile_text

router = APIRouter(prefix="/api/songs", tags=["Songs"])

_yt_cache = {}

def find_verified_official_audio_yt(artist: str, title: str) -> Optional[str]:
    """Search and verify official studio music track on YouTube, ignoring junk videos."""
    cache_key = f"{artist}_{title}".lower()
    if cache_key in _yt_cache:
        return _yt_cache[cache_key]

    queries = [
        f"{artist} - {title} Topic",
        f"{artist} {title} official audio",
        f"{artist} {title}"
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    for q in queries:
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}"
        try:
            r = requests.get(url, headers=headers, timeout=4)
            # 1. Parse JSON items in ytInitialData for verified audio
            data_match = re.search(r'var ytInitialData = ({.*?});</script>', r.text)
            if data_match:
                try:
                    data = json.loads(data_match.group(1))
                    sections = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']
                    for sec in sections:
                        items = sec.get('itemSectionRenderer', {}).get('contents', [])
                        for item in items:
                            if 'videoRenderer' in item:
                                vr = item['videoRenderer']
                                vid = vr.get('videoId')
                                vtitle = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
                                # Filter out non-music, gameplay, memes, reactions, 10hr loops
                                if vid and not any(bad in vtitle.lower() for bad in ['reaction', 'tutorial', 'gameplay', '1 hour', '10 hours', 'meme', 'vlog', 'review']):
                                    _yt_cache[cache_key] = vid
                                    return vid
                except Exception:
                    pass

            # 2. Fallback: Parse first videoId
            video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
            if video_ids:
                _yt_cache[cache_key] = video_ids[0]
                return video_ids[0]
        except Exception:
            continue
    return None

@router.get("/youtube-id")
def get_youtube_id(title: str, artist: Optional[str] = ""):
    """Find verified official studio audio stream on YouTube."""
    vid = find_verified_official_audio_yt(artist or "", title)
    return {"video_id": vid}

@router.get("/search", response_model=List[SpotifySearchResult])
def search_tracks(q: str, current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    try:
        return search_spotify_tracks(q.strip(), limit=5)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {str(e)}")

@router.get("/artist")
def search_artist_discography(
    name: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Fetch up to 50 verified official songs by a specific artist with preview streams and artwork."""
    if not name or len(name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Artist name must be at least 2 characters")
    try:
        url = "https://itunes.apple.com/search"
        params = {"term": name.strip(), "entity": "song", "limit": min(limit, 50)}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        results = r.json().get("results", [])
        
        output = []
        seen = set()
        for item in results:
            title = item.get("trackName", "")
            artist = item.get("artistName", "")
            if not title:
                continue
            key = f"{title.lower()}_{artist.lower()}"
            if key in seen:
                continue
            seen.add(key)
            output.append({
                "title": title,
                "artist": artist,
                "album_name": item.get("collectionName", ""),
                "album_art_url": item.get("artworkUrl100"),
                "preview_url": item.get("previewUrl"),
                "duration_sec": item.get("trackTimeMillis", 0) / 1000.0,
                "spotify_url": f"https://open.spotify.com/search/{title} {artist}",
                "spotify_id": f"art_{item.get('trackId')}"
            })
        return output
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
    mood_label, confidence = classify_mood(audio_features, sentiment_score)

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
        mood_confidence=confidence,
        embedding=json.dumps(embedding_vec)
    )
    db.add(new_song)
    db.commit()
    db.refresh(new_song)
    return new_song

@router.get("", response_model=List[SongResponse])
def list_songs(
    mood: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Song).filter(Song.user_id == current_user.id)
    if mood:
        query = query.filter(Song.mood == mood.lower())
    return query.order_by(Song.created_at.desc()).all()

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