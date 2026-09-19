import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock ML services BEFORE importing anything that touches them
sys.modules['ml'] = MagicMock()
sys.modules['ml.embedding_service'] = MagicMock()
sys.modules['ml.sentiment'] = MagicMock()
sys.modules['ml.faiss_service'] = MagicMock()
sys.modules['ml.knowledge_service'] = MagicMock()
sys.modules['ml.rag_playlist_generator'] = MagicMock()
sys.modules['ml.query_planner'] = MagicMock()
sys.modules['ml.genre_classifier'] = MagicMock()
sys.modules['ml.lyrics_fetcher'] = MagicMock()
sys.modules['utils.spotify'] = MagicMock()

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, get_db
from models import User, Song, ListeningEvent, Playlist, PlaylistItem
from utils.auth import create_access_token, hash_password

# Create test database with StaticPool so all connections share the same in-memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_client(test_db):
    # Import app AFTER mocking
    from main import app
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(test_db):
    db = TestSessionLocal()
    user = User(
        name="Test User",
        email="test@example.com",
        password_hash=hash_password("testpass123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture(scope="function")
def auth_headers(test_user):
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


def create_test_song(db, user_id, title="Test Song", artist="Test Artist"):
    song = Song(
        user_id=user_id,
        title=title,
        artist=artist,
        spotify_id=f"spotify_{title.replace(' ', '_').lower()}",
        spotify_url=f"https://open.spotify.com/track/{title.replace(' ', '_').lower()}",
        tempo=120.0,
        energy=0.7,
        danceability=0.6,
        valence=0.5,
        mood="chill",
        genre="pop",
        duration_sec=180.0
    )
    db.add(song)
    db.commit()
    db.refresh(song)
    return song
