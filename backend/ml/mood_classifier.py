def classify_mood(audio_features: dict, lyrics_sentiment: float) -> tuple[str, float]:
    tempo = audio_features.get("tempo", 120.0)
    energy = audio_features.get("energy", 0.5)
    valence = audio_features.get("valence", 0.5)
    danceability = audio_features.get("danceability", 0.5)

    if tempo >= 125 and energy >= 0.6:
        if lyrics_sentiment < -0.2 or valence < 0.35:
            return "energetic", 0.91
        return "happy", 0.94
    elif tempo <= 95 and energy <= 0.4:
        if lyrics_sentiment < -0.2 or valence < 0.35:
            return "sad", 0.88
        return "chill", 0.92
    elif 95 <= tempo <= 120 and (lyrics_sentiment > 0.3 or valence > 0.6):
        return "romantic", 0.86
    elif danceability >= 0.65 or energy >= 0.55:
        return "energetic", 0.80
    else:
        return "chill", 0.78