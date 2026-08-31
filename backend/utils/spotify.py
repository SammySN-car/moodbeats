import io
import re
import subprocess
import requests
import numpy as np
import scipy.io.wavfile
import librosa

# ══════════════════════════════════════════════════════════════
#  Unified iTunes Search — single source of truth
# ══════════════════════════════════════════════════════════════

def search_itunes(query: str, entity: str = "song", limit: int = 5) -> list[dict]:
    """Search iTunes by keyword. Returns raw result dicts."""
    if not query or len(query.strip()) < 2:
        return []
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": query.strip(), "entity": entity, "limit": min(limit, 50)},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except Exception:
        return []


def parse_track_id(spotify_url: str) -> str:
    """Extract Spotify track ID from URLs or URIs."""
    match = re.search(r"track[/:]([a-zA-Z0-9]{22})", spotify_url)
    if not match:
        raise ValueError("Invalid Spotify track URL. Expected format: https://open.spotify.com/track/{22-character-id}")
    return match.group(1)


def search_spotify_tracks(query: str, limit: int = 5) -> list[dict]:
    """Search tracks by keyword — returns normalized results for the API."""
    raw = search_itunes(query, entity="song", limit=limit)
    output = []
    for item in raw:
        title = item.get("trackName", "")
        artist = item.get("artistName", "")
        output.append({
            "spotify_id": f"search_{item.get('trackId')}",
            "spotify_url": f"https://open.spotify.com/search/{title} {artist}",
            "title": title,
            "artist": artist,
            "album_art_url": item.get("artworkUrl100"),
            "duration_sec": item.get("trackTimeMillis", 0) / 1000.0
        })
    return output


def search_artist_discography(name: str, limit: int = 50) -> list[dict]:
    """Fetch artist discography from iTunes — deduped, normalized."""
    raw = search_itunes(name, entity="song", limit=limit)
    output = []
    seen = set()
    for item in raw:
        title = item.get("trackName", "")
        artist = item.get("artistName", "")
        if not title:
            continue
        key = f"{title.lower()}_{artist.lower()}"
        if key in seen:
            continue
        seen.add(key)
        output.append({
            "title": title,
            "artist": artist,
            "album_name": item.get("collectionName", ""),
            "album_art_url": item.get("artworkUrl100"),
            "preview_url": item.get("previewUrl"),
            "duration_sec": item.get("trackTimeMillis", 0) / 1000.0,
            "spotify_url": f"https://open.spotify.com/search/{title} {artist}",
            "spotify_id": f"art_{item.get('trackId')}"
        })
    return output


def verify_track_on_itunes(title: str, artist: str) -> dict | None:
    """Verify a track exists on iTunes. Returns enriched metadata or None."""
    results = search_itunes(f"{title} {artist}", entity="song", limit=1)
    if not results:
        return None
    item = results[0]
    return {
        "title": item.get("trackName", title),
        "artist": item.get("artistName", artist),
        "album_art_url": item.get("artworkUrl100"),
        "preview_url": item.get("previewUrl"),
    }


# ══════════════════════════════════════════════════════════════
#  YouTube — via yt-dlp (replaces fragile HTML scraping)
# ══════════════════════════════════════════════════════════════

_yt_cache = {}

def find_youtube_video_id(artist: str, title: str) -> str | None:
    """Find official audio on YouTube using yt-dlp. Returns video ID or None."""
    cache_key = f"{artist}_{title}".lower()
    if cache_key in _yt_cache:
        return _yt_cache[cache_key]

    try:
        import yt_dlp
    except ImportError:
        return None

    queries = [
        f"{artist} - {title} Topic",
        f"{artist} {title} official audio",
        f"{artist} {title}"
    ]

    for q in queries:
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch1',
                'skip_download': True,
                'socket_timeout': 5,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(f"ytsearch1:{q}", download=False)
                if result and 'entries' in result and result['entries']:
                    vid = result['entries'][0].get('id')
                    if vid:
                        _yt_cache[cache_key] = vid
                        return vid
        except Exception:
            continue
    return None


# ══════════════════════════════════════════════════════════════
#  Audio Feature Extraction
# ══════════════════════════════════════════════════════════════

def extract_audio_features_from_preview(preview_url: str | None) -> tuple[float, float, float, float]:
    """
    Downloads 30s audio stream into RAM and extracts:
    1. Tempo (BPM)
    2. Energy (RMS Loudness 0.0 - 1.0)
    3. Danceability (Pulse Regularity 0.0 - 1.0)
    4. Valence (Harmonic Brightness & Positiveness 0.0 - 1.0)
    """
    if not preview_url:
        return 120.0, 0.5, 0.5, 0.5
    try:
        audio_data = requests.get(preview_url, timeout=6).content
        cmd = ['ffmpeg', '-i', 'pipe:0', '-f', 'wav', '-ar', '22050', '-ac', '1', 'pipe:1']
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        wav_bytes, _ = proc.communicate(input=audio_data)

        sr, y = scipy.io.wavfile.read(io.BytesIO(wav_bytes))
        y = y.astype(np.float32) / 32768.0

        # Tempo (BPM)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_val = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
        if tempo_val < 90:
            tempo_val *= 2

        # Energy (RMS Volume)
        rms = float(np.sqrt(np.mean(y**2)))
        energy_val = float(min(1.0, max(0.0, rms * 5.5)))

        # Danceability (Rhythmic Pulse)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        pulse_strength = float(np.mean(onset_env))
        danceability_val = float(min(1.0, max(0.0, pulse_strength / 2.8)))

        # Valence (Spectral Brightness & Positiveness)
        spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = float(np.mean(spec_cent) / 3500.0)
        valence_val = float(min(1.0, max(0.0, 0.4 * energy_val + 0.6 * brightness)))

        return round(tempo_val, 1), round(energy_val, 2), round(danceability_val, 2), round(valence_val, 2)
    except Exception:
        return 120.0, 0.5, 0.5, 0.5


def fetch_spotify_track_info(spotify_url: str) -> dict:
    """Fetch track metadata & all 4 audio features in-memory with zero disk storage."""
    track_id = parse_track_id(spotify_url)

    title = "Unknown Track"
    album_art = None

    # 1. Spotify Title & Cover Art via Public oEmbed
    try:
        oembed_resp = requests.get(
            f"https://open.spotify.com/oembed?url={spotify_url}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8
        )
        if oembed_resp.status_code == 200:
            oembed_data = oembed_resp.json()
            title = oembed_data.get("title", "Unknown Track")
            album_art = oembed_data.get("thumbnail_url")
    except Exception:
        pass

    # 2. Enrich Artist & 30s Preview Stream via unified search
    artist = "Unknown Artist"
    duration_sec = 180.0
    preview_url = None

    results = search_itunes(title, entity="song", limit=1)
    if results:
        item = results[0]
        artist = item.get("artistName", "Unknown Artist")
        duration_sec = item.get("trackTimeMillis", 180000) / 1000.0
        preview_url = item.get("previewUrl")
        if not album_art:
            album_art = item.get("artworkUrl100")

    # 3. Extract Real Audio Features in Memory
    tempo, energy, danceability, valence = extract_audio_features_from_preview(preview_url)

    return {
        "title": title,
        "artist": artist,
        "album_art_url": album_art,
        "preview_url": preview_url,
        "duration_sec": duration_sec,
        "spotify_id": track_id,
        "spotify_url": spotify_url,
        "tempo": tempo,
        "energy": energy,
        "danceability": danceability,
        "valence": valence
    }