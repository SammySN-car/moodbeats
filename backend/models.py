from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Taste profile: 384-dim vector stored as JSON string, recomputed periodically
    taste_vector: Mapped[str | None] = mapped_column(Text, nullable=True)
    taste_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    songs: Mapped[list["Song"]] = relationship("Song", backref="owner", cascade="all, delete-orphan")
    playlists: Mapped[list["Playlist"]] = relationship("Playlist", backref="owner", cascade="all, delete-orphan")
    listening_events: Mapped[list["ListeningEvent"]] = relationship("ListeningEvent", backref="user", cascade="all, delete-orphan")


class Song(Base):
    __tablename__ = "songs"
    __table_args__ = (
        UniqueConstraint("user_id", "spotify_id", name="uq_user_spotify_track"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    artist: Mapped[str] = mapped_column(String(200), default="Unknown Artist")

    # Spotify Metadata & Embed
    spotify_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    spotify_url: Mapped[str] = mapped_column(String(500), nullable=False)
    album_art_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)

    # 4 Real Extracted Audio Features
    tempo: Mapped[float] = mapped_column(Float, default=0.0)
    energy: Mapped[float] = mapped_column(Float, default=0.0)
    danceability: Mapped[float] = mapped_column(Float, default=0.0)
    valence: Mapped[float] = mapped_column(Float, default=0.0)

    # ML & Mood
    mood: Mapped[str | None] = mapped_column(String(20), index=True)
    mood_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    lyrics_sentiment: Mapped[float] = mapped_column(Float, default=0.0)

    # 384-dimensional dense vector stored as JSON string for instant search
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Feedback Loop: implicit signal aggregates (updated by ListeningEvent)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)
    last_played_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_listen_sec: Mapped[float] = mapped_column(Float, default=0.0)


class ListeningEvent(Base):
    """Tracks every play / skip / save interaction for implicit feedback."""
    __tablename__ = "listening_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # play, skip, save, unsave
    duration_listened: Mapped[float] = mapped_column(Float, default=0.0)  # seconds
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship to song (for history serialization)
    song: Mapped["Song"] = relationship("Song")


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # AI Prompt & DJ Liner Notes
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["PlaylistItem"]] = relationship(
        "PlaylistItem", backref="playlist", cascade="all, delete-orphan", order_by="PlaylistItem.position"
    )


class PlaylistItem(Base):
    __tablename__ = "playlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    song: Mapped["Song"] = relationship("Song")