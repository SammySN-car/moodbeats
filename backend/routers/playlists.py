from typing import List
import json
import traceback
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models import Playlist, PlaylistItem, Song, User
from schemas import PlaylistCreate, PlaylistResponse, MoodPromptRequest, SuggestedSong
from utils.auth import get_current_user
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
                # It's a positional index — convert to DB ID
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

@router.post("", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def create_playlist(data: PlaylistCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.song_ids:
        user_song_ids = set(s.id for s in db.query(Song.id).filter(Song.id.in_(data.song_ids), Song.user_id == current_user.id).all())
        invalid_ids = [sid for sid in data.song_ids if sid not in user_song_ids]
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"Invalid song IDs: {invalid_ids}. You can only add your own songs.")
    new_playlist = Playlist(user_id=current_user.id, name=data.name, is_auto=False)
    db.add(new_playlist)
    db.commit()
    db.refresh(new_playlist)
    for idx, song_id in enumerate(data.song_ids):
        item = PlaylistItem(playlist_id=new_playlist.id, song_id=song_id, position=idx+1)
        db.add(item)
    db.commit()
    db.refresh(new_playlist)
    return new_playlist

@router.get("", response_model=List[PlaylistResponse])
def list_playlists(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Playlist).filter(Playlist.user_id == current_user.id).order_by(Playlist.created_at.desc()).offset(offset).limit(limit).all()

@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(playlist_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.user_id == current_user.id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(playlist)
    db.commit()
