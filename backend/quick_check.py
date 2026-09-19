from database import SessionLocal
from models import Playlist, PlaylistItem
from schemas import PlaylistResponse

db = SessionLocal()
pls = db.query(Playlist).filter(Playlist.user_id == 15).order_by(Playlist.created_at.desc()).limit(5).all()
for p in pls:
    items = db.query(PlaylistItem).filter(PlaylistItem.playlist_id == p.id).count()
    try:
        resp = PlaylistResponse.model_validate(p)
        print(f"#{p.id} name='{p.name}' items={items} validated OK")
    except Exception as e:
        print(f"#{p.id} name='{p.name}' items={items} VALIDATION FAILED: {e}")
db.close()
