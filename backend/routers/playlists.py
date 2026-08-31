from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Playlist, PlaylistItem, Song, User
from schemas import PlaylistCreate, PlaylistResponse, MoodPromptRequest, SuggestedSong
from utils.auth import get_current_user
from ml.rag_playlist_generator import (
    pytorch_database_rag_search,
    enrich_discovered_songs,
    generate_ai_dj_synthesis
)

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])

@router.post("/generate", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def generate_mood_playlist(
    payload: MoodPromptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_songs = db.query(Song).filter(Song.user_id == current_user.id).all()

    # 1. Pure PyTorch Hybrid RAG Search on Actual User Database Songs
    ranked_lib_songs = pytorch_database_rag_search(payload.prompt, user_songs)

    # 2. Local Ollama AI DJ Synthesis (Sequences library songs + Zero-shot discovers new songs)
    curation = generate_ai_dj_synthesis(payload.prompt, ranked_lib_songs)

    # 3. Auto-enrich Zero-Shot Discoveries with Album Covers
    enriched_discoveries = enrich_discovered_songs(curation.get("new_song_recommendations", []))

    # 4. Save to Database
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
    ordered_ids = curation.get("ordered_library_ids", [s.id for _, s in ranked_lib_songs])

    for idx, sid in enumerate(ordered_ids):
        if sid in lib_song_map:
            item = PlaylistItem(playlist_id=new_playlist.id, song_id=sid, position=idx+1)
            db.add(item)

    db.commit()
    db.refresh(new_playlist)

    response = PlaylistResponse.model_validate(new_playlist)
    response.new_recommendations = [SuggestedSong(**d) for d in enriched_discoveries]
    return response

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
def list_playlists(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Playlist).filter(Playlist.user_id == current_user.id).order_by(Playlist.created_at.desc()).all()

@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(playlist_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.user_id == current_user.id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    db.delete(playlist)
    db.commit()