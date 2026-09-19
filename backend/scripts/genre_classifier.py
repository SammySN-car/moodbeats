"""
Genre Classifier for MoodBeats
==============================
Production classifier with TWO modes:

  MODE 1 (Direct Mapping):
    When a Kaggle genre label is available, use KAGGLE_TO_OUTPUT_GENRE
    to map 114 Kaggle genres to 29 output genres. 100% accurate.

  MODE 2 (Rule-based Fallback):
    When no genre label is available, use audio features in a cascading
    decision tree. Improved thresholds based on feature analysis.

Key insights driving the rule-based logic:
  - speechiness > 0.2 → hip-hop territory
  - instrumentalness > 0.7 → classical/ambient
  - acousticness > 0.5 → folk/country/blues
  - valence + energy → mood-genre mapping
  - dark + loud (valence < 0.35, tempo > 140) → metal, NOT techno

No ML dependencies — pure threshold logic for speed and determinism.

Usage:
    From backend/:
        python ml/genre_classifier.py
"""


# -------------------------------------------------------------
# OUTPUT GENRE TAXONOMY (29 genres)
# -------------------------------------------------------------

OUTPUT_GENRES = [
    # Electronic
    'house', 'techno', 'edm', 'dnb', 'dubstep', 'trance',
    'synthwave', 'phonk', 'lofi',
    # Hip-Hop / Rap
    'hip_hop', 'rap', 'rnb',
    # Rock
    'rock', 'metal', 'punk', 'indie',
    # Pop
    'pop', 'kpop', 'latin',
    # Jazz / Blues
    'jazz', 'blues',
    # Classical / Instrumental
    'classical', 'ambient',
    # R&B / Soul
    'soul', 'funk',
    # Reggae
    'reggae',
    # Country / Folk
    'country', 'folk',
    # Fallback
    'alternative',
]

# -------------------------------------------------------------
# KAGGLE GENRE -> OUTPUT GENRE MAPPING (all 114)
# Curated mapping — 100% accurate when genre label is known.
# -------------------------------------------------------------

KAGGLE_TO_OUTPUT_GENRE = {
    # Electronic
    'house': 'house',
    'chicago-house': 'house',
    'deep-house': 'house',
    'progressive-house': 'house',
    'techno': 'techno',
    'detroit-techno': 'techno',
    'minimal-techno': 'techno',
    'edm': 'edm',
    'drum-and-bass': 'dnb',
    'dubstep': 'dubstep',
    'trance': 'trance',
    'synth-pop': 'synthwave',
    'electronic': 'edm',
    'electro': 'edm',
    'breakbeat': 'edm',
    'idm': 'synthwave',
    'industrial': 'techno',
    'hardstyle': 'edm',
    'garage': 'house',
    'disco': 'house',
    'dance': 'house',
    'club': 'house',
    'party': 'house',
    'happy': 'pop',
    # Hip-Hop / Rap
    'hip-hop': 'hip_hop',
    'rap': 'hip_hop',
    'r-n-b': 'rnb',
    'soul': 'soul',
    'funk': 'funk',
    # Rock
    'rock': 'rock',
    'alt-rock': 'rock',
    'alternative': 'alternative',
    'hard-rock': 'metal',
    'heavy-metal': 'metal',
    'metal': 'metal',
    'metalcore': 'metal',
    'death-metal': 'metal',
    'black-metal': 'metal',
    'grindcore': 'metal',
    'punk': 'punk',
    'punk-rock': 'punk',
    'grunge': 'rock',
    'emo': 'rock',
    'goth': 'rock',
    'indie': 'indie',
    'indie-pop': 'indie',
    'power-pop': 'indie',
    'psych-rock': 'indie',
    'rock-n-roll': 'rock',
    'rockabilly': 'rock',
    'ska': 'punk',
    'guitar': 'rock',
    # Pop
    'pop': 'pop',
    'pop-film': 'pop',
    'k-pop': 'kpop',
    'cantopop': 'kpop',
    'mandopop': 'kpop',
    'j-pop': 'pop',
    'j-idol': 'pop',
    'j-dance': 'pop',
    'latin': 'latin',
    'latino': 'latin',
    'reggaeton': 'latin',
    'salsa': 'latin',
    'samba': 'latin',
    'forro': 'latin',
    'pagode': 'latin',
    'sertanejo': 'latin',
    'brazil': 'latin',
    'mpb': 'latin',
    'tango': 'latin',
    'spanish': 'latin',
    'french': 'pop',
    'german': 'pop',
    'swedish': 'pop',
    'british': 'pop',
    'turkish': 'latin',
    'iranian': 'pop',
    'indian': 'pop',
    'malay': 'pop',
    'arabic': 'pop',
    # Jazz / Blues
    'jazz': 'jazz',
    'blues': 'blues',
    # Classical / Instrumental
    'classical': 'classical',
    'opera': 'classical',
    'piano': 'classical',
    'new-age': 'ambient',
    'ambient': 'ambient',
    'sleep': 'ambient',
    # Country / Folk
    'country': 'country',
    'honky-tonk': 'country',
    'bluegrass': 'country',
    'folk': 'folk',
    'singer-songwriter': 'folk',
    'songwriter': 'folk',
    # Reggae / Caribbean
    'reggae': 'reggae',
    'dub': 'reggae',
    'dancehall': 'reggae',
    # Electronic subgenres
    'afrobeat': 'funk',
    'groove': 'funk',
    'gospel': 'soul',
    # Regional / Mood (map to closest musical genre)
    'anime': 'pop',
    'children': 'pop',
    'kids': 'pop',
    'disney': 'pop',
    'comedy': 'pop',
    'show-tunes': 'pop',
    'romance': 'rnb',
    'sad': 'indie',
    'chill': 'lofi',
    'study': 'lofi',
    'world-music': 'folk',
    'j-rock': 'rock',
    'acoustic': 'folk',
}

# -------------------------------------------------------------
# THRESHOLDS — rule-based classifier tuning
# -------------------------------------------------------------

THRESHOLDS = {
    # Instrumental branch
    'instrumentalness_high': 0.7,
    'instrumentalness_mid': 0.3,

    # Speech branch
    'speechiness_high': 0.2,
    'speechiness_mid': 0.15,

    # Acoustic branch
    'acousticness_high': 0.5,

    # Energy tiers
    'energy_high': 0.7,
    'energy_mid': 0.4,

    # Tempo boundaries (BPM)
    'tempo_dnb': 160,
    'tempo_punk': 140,
    'tempo_techno': 120,
    'tempo_lofi': 85,

    # Sub-classifiers
    'danceability_high': 0.7,
    'danceability_mid': 0.65,
    'valence_high': 0.55,
    'valence_dark': 0.35,
    'valence_low': 0.3,
    'loudness_high': -5.0,
}


# -------------------------------------------------------------
# CORE CLASSIFIER — RULE-BASED
# -------------------------------------------------------------

def classify_genre(features: dict, thresholds: dict = None) -> str:
    """
    Classify a song into a genre using audio features only (rule-based).

    Cascade order:
      1. instrumentalness → classical/ambient
      2. speechiness → hip-hop/rap/rnb
      3. acousticness → folk/country/blues/jazz
      4. energy > 0.7 → electronic/rock/metal/punk
      5. energy 0.4-0.7 → pop/hip-hop/funk/indie/lofi
      6. energy < 0.4 → folk/blues/ambient/lofi

    Args:
        features: dict with keys tempo, energy, danceability, valence,
                  acousticness, instrumentalness, speechiness, liveness, loudness.
        thresholds: optional override dict (defaults to THRESHOLDS).

    Returns:
        Genre label string from OUTPUT_GENRES.
    """
    t = thresholds or THRESHOLDS

    tempo = float(features.get('tempo', 120))
    energy = float(features.get('energy', 0.5))
    danceability = float(features.get('danceability', 0.5))
    valence = float(features.get('valence', 0.5))
    acousticness = float(features.get('acousticness', 0.3))
    instrumentalness = float(features.get('instrumentalness', 0.0))
    speechiness = float(features.get('speechiness', 0.05))

    # -- Step 1: High instrumentalness → Classical / Ambient --
    if instrumentalness > t['instrumentalness_high']:
        if energy < 0.3 and tempo < 80:
            return 'ambient'
        if tempo < 90 and acousticness > 0.3:
            return 'classical'
        if valence > 0.5:
            return 'classical'
        return 'classical'

    # -- Step 2: High speechiness → Hip-Hop / Rap / R&B --
    if speechiness > t['speechiness_high']:
        if energy > t['energy_high']:
            return 'rap'
        if tempo > 115:
            return 'rap'
        if valence > t['valence_high'] and danceability > t['danceability_mid']:
            return 'hip_hop'
        if danceability > t['danceability_mid'] and tempo < 100:
            return 'rnb'
        return 'hip_hop'

    # -- Step 3: High acousticness → Folk / Country / Blues / Jazz --
    if acousticness > t['acousticness_high']:
        if energy < 0.35:
            if valence < 0.35:
                return 'blues'
            if tempo > 70 and tempo < 110:
                return 'country'
            return 'folk'
        if instrumentalness > 0.1 and energy < 0.5:
            return 'jazz'
        if tempo < 110:
            if energy < 0.4:
                return 'blues'
            return 'country'
        return 'folk'

    # -- Step 4: High energy ( > 0.7) --
    if energy > t['energy_high']:
        # Very fast → DnB
        if tempo > t['tempo_dnb']:
            return 'dnb'

        # Fast territory (tempo > 140): metal vs punk vs electronic
        if tempo > t['tempo_punk']:
            # Dark + fast + loud = metal (FIXED: was falling to punk/techno)
            if valence < t['valence_dark']:
                return 'metal'
            # High danceability + fast = punk
            if danceability > t['danceability_mid']:
                return 'punk'
            return 'punk'

        # High energy + high dance → electronic dance genres
        if danceability > t['danceability_high']:
            if valence > 0.5:
                return 'edm'
            return 'house'

        # Medium-fast electronic
        if tempo > t['tempo_techno']:
            if valence > 0.5:
                return 'trance'
            return 'techno'

        # Moderate tempo, high energy
        if valence < t['valence_low']:
            # Dark + loud + mid-tempo → metal (NOT techno)
            return 'metal'
        if instrumentalness > t['instrumentalness_mid']:
            return 'dubstep'
        if danceability > 0.55 and valence > 0.4:
            return 'edm'

        return 'rock'

    # -- Step 5: Medium energy (0.4 - 0.7) --
    if energy > t['energy_mid']:
        # Speech check in mid-energy for borderline hip-hop
        if speechiness > t['speechiness_mid']:
            if tempo < 100 and danceability > t['danceability_mid']:
                return 'hip_hop'
            return 'rap'

        # Happy + danceable = pop
        if danceability > t['danceability_mid'] and valence > t['valence_high']:
            return 'pop'

        # Danceable but not happy = funk/soul
        if danceability > t['danceability_mid']:
            if valence > 0.4:
                return 'funk'
            return 'soul'

        # Slow mid-energy → lofi
        if tempo < t['tempo_lofi']:
            return 'lofi'

        # Mid-tempo, not very danceable
        if valence > t['valence_high']:
            return 'pop'

        return 'indie'

    # -- Step 6: Low energy ( < 0.4 ) --
    if acousticness > 0.6:
        return 'folk'
    if instrumentalness > t['instrumentalness_mid']:
        return 'ambient'
    if tempo < t['tempo_lofi']:
        return 'lofi'
    if valence > t['valence_high']:
        return 'soul'
    if speechiness > t['speechiness_mid']:
        return 'hip_hop'

    return 'lofi'


# -------------------------------------------------------------
# PRODUCTION CLASSIFIER — DUAL MODE
# -------------------------------------------------------------

def classify_song(features: dict, kaggle_genre: str = None) -> str:
    """
    Production classifier with two modes.

    Mode 1 (Direct Mapping):
        If kaggle_genre is provided and exists in KAGGLE_TO_OUTPUT_GENRE,
        return the mapped genre directly. 100% accurate.

    Mode 2 (Rule-based Fallback):
        If kaggle_genre is None or not in the mapping, classify using
        audio features via classify_genre().

    Args:
        features: dict with audio feature values.
        kaggle_genre: optional Kaggle genre label string.

    Returns:
        Genre label string from OUTPUT_GENRES.
    """
    if kaggle_genre and kaggle_genre in KAGGLE_TO_OUTPUT_GENRE:
        return KAGGLE_TO_OUTPUT_GENRE[kaggle_genre]
    return classify_genre(features)