import io
import re
import requests
import subprocess
import numpy as np
import scipy.io.wavfile
import librosa

def parse_track_id(spotify_url: str) -> str:
    """Extract Spotify track ID from URLs or URIs."""
    match = re.search(r"track[/:]([a-zA-Z0-9]{22})", spotify_url)
    if not match:
        raise ValueError("Invalid Spotify track URL. Expected format: https://open.spotify.com/track/{22-character-id}")
    return match.group(1)

def search_spotify_tracks(query: str, limit: int = 5) -> list[dict]:
    """Search tracks by keyword via public metadata API."""
    resp = requests.get(
        "https://itunes.apple.com/search",
        params={"term": query, "entity": "song", "limit": limit},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    
    output = []
    for item in results:
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

    # 2. Enrich Artist & 30s Preview Stream
    artist = "Unknown Artist"
    duration_sec = 180.0
    preview_url = None

    try:
        search_resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": title, "entity": "song", "limit": 1},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=6
        )
        if search_resp.status_code == 200 and search_resp.json().get("results"):
            item = search_resp.json()["results"][0]
            artist = item.get("artistName", "Unknown Artist")
            duration_sec = item.get("trackTimeMillis", 180000) / 1000.0
            preview_url = item.get("previewUrl")
            if not album_art:
                album_art = item.get("artworkUrl100")
    except Exception:
        pass

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