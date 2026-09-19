import pytest
from unittest.mock import patch, MagicMock


def test_parse_spotify_playlist_id_valid():
    """Test URL parsing for various Spotify playlist URL formats."""
    from routers.playlists import parse_spotify_playlist_id

    # Standard URL
    assert parse_spotify_playlist_id("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M") == "37i9dQZF1DXcBWIGoYBM5M"
    # URL with query params
    assert parse_spotify_playlist_id("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc") == "37i9dQZF1DXcBWIGoYBM5M"
    # Embed URL
    assert parse_spotify_playlist_id("https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M") == "37i9dQZF1DXcBWIGoYBM5M"
    # URI format
    assert parse_spotify_playlist_id("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M") == "37i9dQZF1DXcBWIGoYBM5M"


def test_parse_spotify_playlist_id_invalid():
    """Test that invalid URLs raise ValueError."""
    from routers.playlists import parse_spotify_playlist_id

    with pytest.raises(ValueError):
        parse_spotify_playlist_id("https://google.com")
    with pytest.raises(ValueError):
        parse_spotify_playlist_id("not a url")


def test_import_endpoint_exists(test_client, test_user, auth_headers):
    """Test that the import-spotify endpoint exists and rejects invalid URLs."""
    response = test_client.post("/api/playlists/import-spotify", headers=auth_headers, json={
        "spotify_url": "not-a-valid-url"
    })
    assert response.status_code == 400


def test_import_endpoint_requires_auth(test_client):
    """Test that import-spotify requires authentication."""
    response = test_client.post("/api/playlists/import-spotify", json={
        "spotify_url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    })
    assert response.status_code in (401, 403)


def test_import_with_mocked_spotify(test_client, test_user, auth_headers):
    """Test import with mocked spotifyscraper response."""
    # Build mock track
    mock_artist = MagicMock()
    mock_artist.name = "Test Artist"

    mock_track = MagicMock()
    mock_track.name = "Test Song"
    mock_track.id = "abc123def456ghi789jkl01"
    mock_track.artists = [mock_artist]

    # Build mock playlist track (wraps track)
    mock_playlist_track = MagicMock()
    mock_playlist_track.track = mock_track

    # Build mock playlist
    mock_owner = MagicMock()
    mock_owner.name = "Test Owner"

    mock_playlist = MagicMock()
    mock_playlist.name = "Test Playlist"
    mock_playlist.owner = mock_owner
    mock_playlist.tracks = [mock_playlist_track]

    # Mock the SpotifyClient context manager
    mock_sp_client = MagicMock()
    mock_sp_client.get_playlist.return_value = mock_playlist

    mock_spotify_module = MagicMock()
    mock_spotify_module.SpotifyClient.return_value.__enter__ = MagicMock(return_value=mock_sp_client)
    mock_spotify_module.SpotifyClient.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"spotify_scraper": mock_spotify_module}):
        response = test_client.post("/api/playlists/import-spotify", headers=auth_headers, json={
            "spotify_url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["playlist_name"] == "Test Playlist"
    assert data["total_tracks"] == 1
    assert "matched_tracks" in data
    assert "unmatched_tracks" in data


def test_import_creates_playlist_in_db(test_client, test_user, auth_headers):
    """Test that a successful import creates a playlist in the database."""
    from database import get_db
    from models import Playlist

    mock_artist = MagicMock()
    mock_artist.name = "Artist A"

    mock_track = MagicMock()
    mock_track.name = "Song A"
    mock_track.id = "spotifytrackid1234567890ab"
    mock_track.artists = [mock_artist]

    mock_playlist_track = MagicMock()
    mock_playlist_track.track = mock_track

    mock_owner = MagicMock()
    mock_owner.name = "Owner"

    mock_playlist = MagicMock()
    mock_playlist.name = "My Imported Playlist"
    mock_playlist.owner = mock_owner
    mock_playlist.tracks = [mock_playlist_track]

    mock_sp_client = MagicMock()
    mock_sp_client.get_playlist.return_value = mock_playlist

    mock_spotify_module = MagicMock()
    mock_spotify_module.SpotifyClient.return_value.__enter__ = MagicMock(return_value=mock_sp_client)
    mock_spotify_module.SpotifyClient.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"spotify_scraper": mock_spotify_module}):
        response = test_client.post("/api/playlists/import-spotify", headers=auth_headers, json={
            "spotify_url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["playlist_id"] > 0

    # Verify in DB
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    playlist = db.query(Playlist).filter(Playlist.id == data["playlist_id"]).first()
    assert playlist is not None
    assert playlist.name == "My Imported Playlist"
    assert playlist.source_prompt == "spotify:37i9dQZF1DXcBWIGoYBM5M"
    assert playlist.user_id == test_user.id
    db.close()


def test_import_empty_playlist(test_client, test_user, auth_headers):
    """Test that importing an empty playlist returns 404."""
    mock_playlist = MagicMock()
    mock_playlist.name = "Empty Playlist"
    mock_playlist.owner = MagicMock()
    mock_playlist.owner.name = "Owner"
    mock_playlist.tracks = []

    mock_sp_client = MagicMock()
    mock_sp_client.get_playlist.return_value = mock_playlist

    mock_spotify_module = MagicMock()
    mock_spotify_module.SpotifyClient.return_value.__enter__ = MagicMock(return_value=mock_sp_client)
    mock_spotify_module.SpotifyClient.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"spotify_scraper": mock_spotify_module}):
        response = test_client.post("/api/playlists/import-spotify", headers=auth_headers, json={
            "spotify_url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        })

    assert response.status_code == 404


def test_import_spotify_fetch_failure(test_client, test_user, auth_headers):
    """Test that a Spotify API failure returns 502."""
    mock_sp_client = MagicMock()
    mock_sp_client.get_playlist.side_effect = Exception("Network error")

    mock_spotify_module = MagicMock()
    mock_spotify_module.SpotifyClient.return_value.__enter__ = MagicMock(return_value=mock_sp_client)
    mock_spotify_module.SpotifyClient.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"spotify_scraper": mock_spotify_module}):
        response = test_client.post("/api/playlists/import-spotify", headers=auth_headers, json={
            "spotify_url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        })

    assert response.status_code == 502


def test_import_matches_existing_songs(test_client, test_user, auth_headers, test_db):
    """Test that tracks matching existing user songs are linked."""
    from tests.conftest import create_test_song, TestSessionLocal

    db = TestSessionLocal()
    existing = create_test_song(db, test_user.id, title="Known Track", artist="Known Artist")
    db.close()

    mock_artist = MagicMock()
    mock_artist.name = "Known Artist"

    mock_track = MagicMock()
    mock_track.name = "Known Track"
    mock_track.id = "xyz987mlk654jih321fedc0"
    mock_track.artists = [mock_artist]

    mock_playlist_track = MagicMock()
    mock_playlist_track.track = mock_track

    mock_owner = MagicMock()
    mock_owner.name = "Owner"

    mock_playlist = MagicMock()
    mock_playlist.name = "Match Playlist"
    mock_playlist.owner = mock_owner
    mock_playlist.tracks = [mock_playlist_track]

    mock_sp_client = MagicMock()
    mock_sp_client.get_playlist.return_value = mock_playlist

    mock_spotify_module = MagicMock()
    mock_spotify_module.SpotifyClient.return_value.__enter__ = MagicMock(return_value=mock_sp_client)
    mock_spotify_module.SpotifyClient.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("sys.modules", {"spotify_scraper": mock_spotify_module}):
        response = test_client.post("/api/playlists/import-spotify", headers=auth_headers, json={
            "spotify_url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["matched_tracks"] == 1
    assert data["unmatched_tracks"] == 0
