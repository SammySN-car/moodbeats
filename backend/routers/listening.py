from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
from models import User, Song, ListeningEvent
from schemas import (
    ListeningEventRequest, ListeningEventResponse,
    HistoryItem, TasteProfileResponse, SongResponse,
)
from utils.auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/listening", tags=["Listening Feedback"])

# How often to recompute taste vector (every N events)
TASTE_RECOMPUTE_INTERVAL = 10


@router.post("/event", response_model=ListeningEventResponse)
def record_listening_event(
    payload: ListeningEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a play, skip, save, or unsave event."""
    song = db.query(Song).filter(
        Song.id == payload.song_id,
        Song.user_id == current_user.id,
    ).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song not found in your library")

    event = ListeningEvent(
        user_id=current_user.id,
        song_id=payload.song_id,
        event_type=payload.event_type,
        duration_listened=payload.duration_listened,
    )
    db.add(event)

    if payload.event_type == "play":
        song.play_count += 1
        song.last_played_at = datetime.utcnow()
    elif payload.event_type == "skip":
        song.skip_count += 1
        song.total_listen_sec += payload.duration_listened
    elif payload.event_type == "save":
        song.saved = True
    elif payload.event_type == "unsave":
        song.saved = False

    db.commit()

    event_count = db.query(ListeningEvent).filter(
        ListeningEvent.user_id == current_user.id
    ).count()

    message = ""
    if event_count % TASTE_RECOMPUTE_INTERVAL == 0:
        _recompute_taste_vector(current_user, db)
        message = f"Taste vector recomputed (after {event_count} events)"

    return ListeningEventResponse(
        play_count=song.play_count,
        skip_count=song.skip_count,
        saved=song.saved,
        message=message,
    )


@router.get("/history", response_model=list[HistoryItem])
def get_listening_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=500),
):
    """Return the user's most recent listening events with song details."""
    events = (
        db.query(ListeningEvent)
        .filter(ListeningEvent.user_id == current_user.id)
        .order_by(desc(ListeningEvent.created_at))
        .limit(limit)
        .all()
    )
    return events


@router.post("/taste", response_model=TasteProfileResponse)
def recompute_taste(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Force recompute the user's taste vector from their top-played songs."""
    result = _recompute_taste_vector(current_user, db)
    return result


def _recompute_taste_vector(user: User, db: Session) -> TasteProfileResponse:
    """Average embeddings of top-played songs into a single taste vector."""
    import json

    top_songs = (
        db.query(Song)
        .filter(Song.user_id == user.id, Song.embedding.isnot(None))
        .order_by(desc(Song.play_count))
        .limit(settings.TASTE_HISTORY_LIMIT)
        .all()
    )

    if len(top_songs) < 5:
        saved_songs = (
            db.query(Song)
            .filter(Song.user_id == user.id, Song.embedding.isnot(None), Song.saved == True)
            .all()
        )
        seen_ids = {s.id for s in top_songs}
        for s in saved_songs:
            if s.id not in seen_ids:
                top_songs.append(s)
            if len(top_songs) >= settings.TASTE_HISTORY_LIMIT:
                break

    if not top_songs:
        user.taste_vector = None
        user.taste_updated_at = None
        db.commit()
        return TasteProfileResponse(has_taste=False, songs_used=0)

    import numpy as np
    vectors = []
    for song in top_songs:
        try:
            vec = json.loads(song.embedding)
            vectors.append(np.array(vec, dtype=np.float32))
        except (json.JSONDecodeError, TypeError):
            continue

    if not vectors:
        user.taste_vector = None
        user.taste_updated_at = None
        db.commit()
        return TasteProfileResponse(has_taste=False, songs_used=0)

    taste = np.mean(vectors, axis=0).tolist()
    user.taste_vector = json.dumps(taste)
    user.taste_updated_at = datetime.utcnow()
    db.commit()

    print(f"[TasteProfile] Recomputed for user {user.id}: {len(vectors)} songs averaged")
    return TasteProfileResponse(
        has_taste=True,
        songs_used=len(vectors),
        updated_at=user.taste_updated_at,
    )
