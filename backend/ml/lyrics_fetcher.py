import re
import requests

def clean_track_title(title: str) -> str:
    """Strip feature tags, remaster tags, and live indicators for accurate lyrics matching."""
    cleaned = re.sub(r"\(feat\..*?\)", "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(with.*?\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"-.*remaster.*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(live.*?\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[.*?\]", "", cleaned)
    return cleaned.strip()

def fetch_lyrics(artist: str, title: str) -> str:
    """Fetch lyrics from public API with timeout protection and cleaned titles."""
    if not artist or artist.lower() == "unknown artist" or not title:
        return ""
    
    clean_title = clean_track_title(title)
    clean_artist = artist.split(",")[0].strip()

    try:
        url = f"https://api.lyrics.ovh/v1/{clean_artist}/{clean_title}"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            return response.json().get("lyrics", "")
    except Exception:
        pass
    return ""