import json
import re
import traceback
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
from models import Playlist, PlaylistItem, Song, User
from schemas import PlaylistCreate, PlaylistResponse, MoodPromptRequest, SuggestedSong
from utils.auth import get_current_user
from ml.embedding_service import get_text_embedding_tensor
from ml.knowledge_service import knowledge_service
from ml.rag_playlist_generator import (
    hybrid_faiss_rag_search,
    pytorch_database_rag_search,
    enrich_discovered_songs,
    generate_ai_dj_synthesis
)
from ml.faiss_service import faiss_service
from ml.query_planner import decompose_query
from config import settings

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])

@router.get("", response_model=list[PlaylistResponse])
def list_playlists(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List the user's previously generated playlists."""
    playlists = (
        db.query(Playlist)
        .filter(Playlist.user_id == current_user.id)
        .order_by(Playlist.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for pl in playlists:
        try:
            # Filter out items with deleted songs before validation
            valid_items = [item for item in pl.items if item.song is not None]
            pl.items = valid_items
            resp = PlaylistResponse.model_validate(pl)
            result.append(resp)
        except Exception:
            # Skip playlists that still fail validation
            continue
    return result

@router.get("/{playlist_id}", response_model=PlaylistResponse)
def get_playlist(
    playlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single playlist with all its tracks."""
    pl = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.user_id == current_user.id
    ).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Playlist not found")
    valid_items = [item for item in pl.items if item.song is not None]
    pl.items = valid_items
    return PlaylistResponse.model_validate(pl)

@router.post("", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def create_playlist(
    data: PlaylistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a playlist from a list of song IDs."""
    if data.song_ids:
        user_song_ids = set(
            s.id for s in db.query(Song.id).filter(
                Song.id.in_(data.song_ids),
                Song.user_id == current_user.id
            ).all()
        )
        invalid_ids = [sid for sid in data.song_ids if sid not in user_song_ids]
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"Invalid song IDs: {invalid_ids}. You can only add your own songs.")
    
    new_playlist = Playlist(user_id=current_user.id, name=data.name, is_auto=False)
    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)
    
    for idx, song_id in enumerate(data.song_ids):
        item = PlaylistItem(playlist_id=new_playlist.id, song_id=song_id, position=idx + 1)
        db.add(item)
    db.commit()
    db.refresh(new_playlist)
    return new_playlist


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a playlist."""
    playlist = db.query(Playlist).filter(
        Playlist.id == playlist_id,
        Playlist.user_id == current_user.id
    ).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(playlist)
    db.commit()

@router.post("/generate", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def generate_mood_playlist(
    payload: MoodPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_songs = db.query(Song).filter(Song.user_id == current_user.id).all()

        if settings.PLANNER_ENABLED:
            plan = decompose_query(payload.prompt)
        else:
            plan = None

        # Load user taste vector if available
        taste_vec = None
        if current_user.taste_vector:
            try:
                taste_vec = json.loads(current_user.taste_vector)
            except (json.JSONDecodeError, TypeError):
                taste_vec = None

        ranked_lib_songs = []
        if faiss_service.is_loaded:
            ranked_lib_songs = hybrid_faiss_rag_search(
                payload.prompt, db, user_id=current_user.id,
                planner_plan=plan, taste_vector=taste_vec
            )
        
        # Resilient fallback if FAISS is unbuilt or returns empty
        if not ranked_lib_songs:
            ranked_lib_songs = pytorch_database_rag_search(
                payload.prompt, user_songs, planner_plan=plan, taste_vector=taste_vec
            )

        curation = generate_ai_dj_synthesis(payload.prompt, ranked_lib_songs, planner_plan=plan)

        enriched_discoveries = enrich_discovered_songs(curation.get("new_song_recommendations", []))

        new_playlist = Playlist(
            user_id=current_user.id,
            name=curation.get("playlist_title", "AI Curated Playlist"),
            description=curation.get("ai_dj_note", f"Vibe: {payload.prompt}"),
            source_prompt=payload.prompt,
            is_auto=True
        )
        db.add(new_playlist)
        db.commit()
        db.refresh(new_playlist)

        lib_song_map = {s.id: s for _, s in ranked_lib_songs}
        ordered_ids_raw = curation.get("ordered_library_ids", [s.id for _, s in ranked_lib_songs])

        # The LLM may return positional indices (1, 2, 3...) instead of actual DB IDs.
        # Map positional indices to real IDs using the ranked order.
        ranked_id_order = [s.id for _, s in ranked_lib_songs]
        ordered_ids = []
        for sid in ordered_ids_raw:
            if sid in lib_song_map:
                # It's already a valid DB ID
                ordered_ids.append(sid)
            elif isinstance(sid, int) and 1 <= sid <= len(ranked_id_order):
                # It's a positional index - convert to DB ID
                ordered_ids.append(ranked_id_order[sid - 1])
            elif str(sid) in lib_song_map:
                # It's a string DB ID
                ordered_ids.append(int(sid))

        for idx, sid in enumerate(ordered_ids):
            if sid in lib_song_map:
                item = PlaylistItem(playlist_id=new_playlist.id, song_id=sid, position=idx+1)
                db.add(item)

        db.commit()
        db.refresh(new_playlist)

        response = PlaylistResponse.model_validate(new_playlist)
        response.new_recommendations = [SuggestedSong(**d) for d in enriched_discoveries]
        response.track_explanations = curation.get("track_explanations", {})
        response.quality_score = curation.get("quality_score")
        response.quality_notes = curation.get("quality_notes")
        return response
    except Exception as e:
        traceback.print_exc()
        raise

# --- Spotify Playlist Import ---

class SpotifyImportRequest(BaseModel):
    spotify_url: str = Field(..., description="Spotify playlist URL")

class SpotifyImportResponse(BaseModel):
    playlist_id: int
    playlist_name: str
    total_tracks: int
    imported_new: int
    linked_existing: int
    failed: int
    failed_samples: List[str] = Field(default_factory=list)


def parse_spotify_playlist_id(url: str) -> str:
    """Extract playlist ID from Spotify URL."""
    patterns = [
        r'spotify\.com/(?:embed/)?playlist/([a-zA-Z0-9]{22})',
        r'spotify:playlist:([a-zA-Z0-9]{22})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError("Invalid Spotify playlist URL. Expected format: https://open.spotify.com/playlist/{id}")


def _upsert_song_from_spotify(db: Session, user_id: int, track_data: dict) -> Song:
    """Find or create a Song from Spotify track data."""
    spotify_id = track_data["spotify_id"]
    
    existing = db.query(Song).filter(
        Song.user_id == user_id,
        Song.spotify_id == spotify_id
    ).first()
    if existing:
        return existing
    
    from utils.spotify import extract_audio_features_from_preview
    preview_url = track_data.get("preview_url")
    tempo, energy, danceability, valence = extract_audio_features_from_preview(preview_url)
    
    genre = knowledge_service.classify_genre_from_features({
        "tempo": tempo,
        "energy": energy,
        "danceability": danceability,
        "valence": valence,
        "acousticness": track_data.get("acousticness", 0.3),
        "instrumentalness": track_data.get("instrumentalness", 0.0),
        "speechiness": track_data.get("speechiness", 0.05),
        "liveness": track_data.get("liveness", 0.2),
    })
    
    mood, mood_confidence, _ = knowledge_service.classify_mood_from_features({
        "tempo": tempo,
        "energy": energy,
        "danceability": danceability,
        "valence": valence,
    })
    
    profile_text = knowledge_service.build_song_profile(
        title=track_data["title"],
        artist=track_data["artist"],
        genre=genre,
        mood=mood,
        tempo=tempo,
        energy=energy,
        danceability=danceability,
        valence=valence,
        lyrics_sentiment=0.0,
    )
    embedding_vec = get_text_embedding_tensor(profile_text)
    
    import json as _json
    new_song = Song(
        user_id=user_id,
        title=track_data["title"],
        artist=track_data["artist"],
        spotify_id=spotify_id,
        spotify_url=track_data.get("spotify_url", f"https://open.spotify.com/track/{spotify_id}"),
        album_art_url=track_data.get("album_art_url"),
        preview_url=preview_url,
        duration_sec=track_data.get("duration_ms", 0) / 1000.0,
        tempo=tempo,
        energy=energy,
        danceability=danceability,
        valence=valence,
        genre=genre,
        mood=mood,
        mood_confidence=mood_confidence,
        embedding=_json.dumps(embedding_vec) if embedding_vec else None,
    )
    db.add(new_song)
    db.flush()
    return new_song


@router.post("/import-spotify", response_model=SpotifyImportResponse)
def import_spotify_playlist(
    payload: SpotifyImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import a public Spotify playlist into MoodBeats.
    For each track:
      - If it already exists in the user's DB: links it to the playlist.
      - If it doesn't exist: creates a new Song with audio features,
        genre, and mood classification, then adds it to the playlist.
    """
    try:
        playlist_id_str = parse_spotify_playlist_id(payload.spotify_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        from spotify_scraper import SpotifyClient
        with SpotifyClient() as client:
            sp_playlist = client.get_playlist(
                f"https://open.spotify.com/playlist/{playlist_id_str}",
                max_tracks=None
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Spotify playlist: {str(e)}")

    if not sp_playlist or not sp_playlist.tracks:
        raise HTTPException(status_code=404, detail="Playlist not found or is empty")

    # Pre-build lookup for existing songs
    existing_songs = db.query(Song).filter(Song.user_id == current_user.id).all()
    existing_by_spotify_id = {}
    existing_by_title_artist = {}
    for s in existing_songs:
        if s.spotify_id:
            existing_by_spotify_id[s.spotify_id] = s
        key = (s.title.strip().lower(), s.artist.strip().lower())
        existing_by_title_artist[key] = s

    playlist_song_ids = []
    imported_new = 0
    linked_existing = 0
    failed = 0
    failed_samples = []

    for pt in sp_playlist.tracks:
        t = pt.track
        artists_str = ", ".join(a.name for a in t.artists)
        title = t.name.strip()
        spotify_track_id = t.id

        album_art = None
        if t.images:
            album_art = t.images[0].url if hasattr(t.images[0], 'url') else str(t.images[0])

        track_data = {
            "spotify_id": spotify_track_id,
            "title": title,
            "artist": artists_str,
            "preview_url": t.preview_url,
            "duration_ms": t.duration_ms or 0,
            "album_art_url": album_art,
            "spotify_url": f"https://open.spotify.com/track/{spotify_track_id}",
        }

        try:
            # Strategy 1: exact spotify_id match
            if spotify_track_id in existing_by_spotify_id:
                playlist_song_ids.append(existing_by_spotify_id[spotify_track_id].id)
                linked_existing += 1
                continue

            # Strategy 2: title + artist match
            primary_artist = t.artists[0].name.strip().lower() if t.artists else ""
            key_ta = (title.lower(), primary_artist)
            if key_ta in existing_by_title_artist:
                playlist_song_ids.append(existing_by_title_artist[key_ta].id)
                linked_existing += 1
                continue

            # Strategy 3: fuzzy match
            found = False
            for (db_title, db_artist), db_song in existing_by_title_artist.items():
                if title.lower() in db_title or db_title in title.lower():
                    if primary_artist in db_artist or db_artist in primary_artist:
                        playlist_song_ids.append(db_song.id)
                        linked_existing += 1
                        found = True
                        break
            if found:
                continue

            # No match — create new song
            new_song = _upsert_song_from_spotify(db, current_user.id, track_data)
            playlist_song_ids.append(new_song.id)
            imported_new += 1

        except Exception as e:
            failed += 1
            if len(failed_samples) < 10:
                failed_samples.append(f"{title} - {artists_str}: {str(e)[:80]}")

    db.commit()

    # Deduplicate preserving order
    seen = set()
    unique_ids = []
    for sid in playlist_song_ids:
        if sid not in seen:
            seen.add(sid)
            unique_ids.append(sid)

    # Create playlist
    new_playlist = Playlist(
        user_id=current_user.id,
        name=sp_playlist.name or "Imported Playlist",
        description=f"Imported from Spotify by {sp_playlist.owner.name if sp_playlist.owner else 'Unknown'}",
        source_prompt=f"spotify:{playlist_id_str}",
        is_auto=False
    )
    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)

    for idx, song_id in enumerate(unique_ids):
        item = PlaylistItem(playlist_id=new_playlist.id, song_id=song_id, position=idx + 1)
        db.add(item)
    db.commit()
    db.refresh(new_playlist)

    return SpotifyImportResponse(
        playlist_id=new_playlist.id,
        playlist_name=new_playlist.name,
        total_tracks=len(sp_playlist.tracks),
        imported_new=imported_new,
        linked_existing=linked_existing,
        failed=failed,
        failed_samples=failed_samples
    )