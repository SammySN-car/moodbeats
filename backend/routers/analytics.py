from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Song, User
from utils.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/mood-distribution")
def get_mood_distribution(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    results = db.query(Song.mood, func.count(Song.id)).filter(
        Song.user_id == current_user.id
    ).group_by(Song.mood).all()
    return {mood: count for mood, count in results if mood}

@router.get("/stats")
def get_library_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_songs = db.query(Song).filter(Song.user_id == current_user.id).count()
    avg_tempo = db.query(func.avg(Song.tempo)).filter(Song.user_id == current_user.id).scalar() or 0.0
    avg_energy = db.query(func.avg(Song.energy)).filter(Song.user_id == current_user.id).scalar() or 0.0

    return {
        "total_songs": total_songs,
        "avg_tempo_bpm": round(float(avg_tempo), 1),
        "avg_energy_pct": round(float(avg_energy) * 100, 1)
    }