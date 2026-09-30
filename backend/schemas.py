from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth Schemas ---
class UserRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    user_email: str
    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Song Schemas ---
class SpotifyImportRequest(BaseModel):
    spotify_url: str = Field(..., min_length=10, examples=["https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b"])


class iTunesImportRequest(BaseModel):
    """Import a song by title + artist (searches iTunes)."""

    title: str = Field(..., min_length=1)
    artist: str = Field(..., min_length=1)


class SpotifySearchResult(BaseModel):
    spotify_id: str
    spotify_url: str
    title: str
    artist: str
    album_art_url: str | None = None
    duration_sec: float = 0.0


class SongResponse(BaseModel):
    id: int
    title: str
    artist: str | None = "Unknown Artist"
    spotify_id: str
    spotify_url: str
    album_art_url: str | None = None
    preview_url: str | None = None
    duration_sec: float | None = 0.0
    tempo: float | None = 0.0
    energy: float | None = 0.0
    danceability: float | None = 0.0
    valence: float | None = 0.0
    mood: str | None = None
    mood_confidence: float | None = 0.0
    genre: str | None = None
    lyrics_sentiment: float | None = 0.0
    # Feedback loop fields
    play_count: int | None = 0
    skip_count: int | None = 0
    saved: bool | None = False
    last_played_at: datetime | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Zero-Shot Discovery Schemas ---
class SuggestedSong(BaseModel):
    title: str
    artist: str
    reason: str | None = None
    album_art_url: str | None = None
    preview_url: str | None = None
    spotify_url: str | None = None
    spotify_id: str | None = None


# --- Playlist Schemas ---
class PlaylistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    song_ids: list[int] = Field(default_factory=list)


class PlaylistItemResponse(BaseModel):
    id: int
    position: int
    song: SongResponse | None = None
    model_config = ConfigDict(from_attributes=True)


class PlaylistResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    source_prompt: str | None = None
    is_auto: bool
    created_at: datetime
    items: list[PlaylistItemResponse] = Field(default_factory=list)
    new_recommendations: list[SuggestedSong] = Field(default_factory=list)
    track_explanations: dict[int, str] = Field(default_factory=dict)
    quality_score: int | None = None
    quality_notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class MoodPromptRequest(BaseModel):
    prompt: str = Field(..., min_length=2, examples=["Late night highway drive in the rain with synthwave vibes"])


# --- Listening / Feedback Schemas ---
class ListeningEventRequest(BaseModel):
    """Sent by frontend when user plays, skips, or saves a track."""

    song_id: int
    event_type: str = Field(..., pattern="^(play|skip|save|unsave)$")
    duration_listened: float = Field(default=0.0, ge=0.0, description="Seconds listened before skip/end")


class HistoryItem(BaseModel):
    """A single item in listening history."""

    id: int
    song_id: int
    event_type: str
    duration_listened: float
    created_at: datetime
    song: SongResponse
    model_config = ConfigDict(from_attributes=True)


class ListeningEventResponse(BaseModel):
    """Confirmation after recording an event."""

    status: str = "ok"
    play_count: int
    skip_count: int
    saved: bool
    message: str = ""


class TasteProfileResponse(BaseModel):
    """Returned after taste vector is recomputed."""

    has_taste: bool
    songs_used: int
    updated_at: datetime | None = None
