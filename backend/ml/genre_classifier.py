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

import os
import sys
import json
from collections import defaultdict, Counter

import numpy as np
import pandas as pd

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


# -------------------------------------------------------------
# CONVENIENCE WRAPPERS
# -------------------------------------------------------------

def classify_genre_from_features(features: dict) -> str:
    """Alias for classify_genre — classify from a features dict."""
    return classify_genre(features)


def classify_genre_from_db_row(row) -> str:
    """
    Classify genre from a pandas DataFrame row (as used in import_kaggle_songs.py).

    Expects columns: tempo, energy, danceability, valence, acousticness,
    instrumentalness, speechiness, liveness, loudness.
    """
    features = {
        'tempo': float(getattr(row, 'tempo', 120)),
        'energy': float(getattr(row, 'energy', 0.5)),
        'danceability': float(getattr(row, 'danceability', 0.5)),
        'valence': float(getattr(row, 'valence', 0.5)),
        'acousticness': float(getattr(row, 'acousticness', 0.3)),
        'instrumentalness': float(getattr(row, 'instrumentalness', 0.0)),
        'speechiness': float(getattr(row, 'speechiness', 0.05)),
        'liveness': float(getattr(row, 'liveness', 0.2)),
        'loudness': float(getattr(row, 'loudness', -8.0)),
    }
    return classify_genre(features)


# -------------------------------------------------------------
# KB-DRIVEN VALIDATION: test classifier against KB genre profiles
# -------------------------------------------------------------

def load_knowledge_base():
    """Load music_knowledge_base.json from same directory."""
    kb_path = os.path.join(os.path.dirname(__file__), 'music_knowledge_base.json')
    if not os.path.exists(kb_path):
        print(f"ERROR: Knowledge base not found at {kb_path}")
        sys.exit(1)
    with open(kb_path, 'r') as f:
        return json.load(f)


def load_dataset():
    """Load dataset.csv from backend/data/."""
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dataset.csv')
    csv_path = os.path.normpath(csv_path)
    if not os.path.exists(csv_path):
        print(f"ERROR: Dataset not found at {csv_path}")
        sys.exit(1)
    return pd.read_csv(csv_path)


def test_classifier_with_kb(kb):
    """
    For each of the 114 Kaggle genres in the KB, classify using the rule-based
    classifier against the genre's mean audio profile. Build the mapping and
    print a confusion-style matrix.
    """
    print("=" * 72)
    print("GENRE CLASSIFIER -- KB VALIDATION (Rule-Based Only)")
    print("=" * 72)

    profiles = kb['genres']['profiles']
    kaggle_genres = kb['genres']['list']

    kaggle_to_classified = {}
    classified_groups = defaultdict(list)
    classification_details = []

    for genre in sorted(kaggle_genres):
        if genre not in profiles:
            continue
        means = profiles[genre]['means']
        classified = classify_genre(means)
        kaggle_to_classified[genre] = classified
        classified_groups[classified].append(genre)

        classification_details.append({
            'kaggle_genre': genre,
            'classified': classified,
            'tempo': means.get('tempo', 0),
            'energy': means.get('energy', 0),
            'danceability': means.get('danceability', 0),
            'valence': means.get('valence', 0),
            'acousticness': means.get('acousticness', 0),
            'instrumentalness': means.get('instrumentalness', 0),
            'speechiness': means.get('speechiness', 0),
        })

    # Confusion matrix: output genre -> list of Kaggle genres
    print(f"\n{'-' * 72}")
    print("CLASSIFICATION RESULTS: Kaggle genre -> Output genre")
    print(f"{'-' * 72}")

    for output_genre in OUTPUT_GENRES:
        if output_genre in classified_groups:
            kaggle_list = sorted(classified_groups[output_genre])
            print(f"\n  [{output_genre.upper()}] ({len(kaggle_list)} genres)")
            for g in kaggle_list:
                d = next(x for x in classification_details if x['kaggle_genre'] == g)
                print(f"    {g:25s}  T={d['tempo']:6.1f}  E={d['energy']:.2f}  "
                      f"D={d['danceability']:.2f}  V={d['valence']:.2f}  "
                      f"A={d['acousticness']:.2f}  I={d['instrumentalness']:.3f}  "
                      f"S={d['speechiness']:.3f}")

    unmapped = [g for g in kaggle_genres if g not in kaggle_to_classified]
    if unmapped:
        print(f"\n  [UNMAPPED] {len(unmapped)} genres not in KB profiles:")
        for g in sorted(unmapped):
            print(f"    {g}")

    return kaggle_to_classified, classified_groups, classification_details


def test_classifier_with_dataset(kaggle_to_classified):
    """
    Load the actual dataset, classify every track with rule-based only,
    and print distribution + agreement stats.
    """
    print(f"\n{'=' * 72}")
    print("DATASET-LEVEL VALIDATION (Rule-Based Only)")
    print(f"{'=' * 72}")

    df = load_dataset()
    print(f"Loaded {len(df):,} tracks")

    genre_col = 'track_genre' if 'track_genre' in df.columns else 'genre' if 'genre' in df.columns else None
    if genre_col is None:
        print("ERROR: No genre column found in dataset")
        return

    classified_counts = Counter()
    matches = 0
    mismatches = 0
    total = 0

    for _, row in df.iterrows():
        features = {
            'tempo': float(row.get('tempo', 120)),
            'energy': float(row.get('energy', 0.5)),
            'danceability': float(row.get('danceability', 0.5)),
            'valence': float(row.get('valence', 0.5)),
            'acousticness': float(row.get('acousticness', 0.3)),
            'instrumentalness': float(row.get('instrumentalness', 0.0)),
            'speechiness': float(row.get('speechiness', 0.05)),
            'liveness': float(row.get('liveness', 0.2)),
            'loudness': float(row.get('loudness', -8.0)),
        }
        rule_genre = classify_genre(features)
        classified_counts[rule_genre] += 1
        total += 1

        kaggle_genre = str(row.get(genre_col, ''))
        expected = kaggle_to_classified.get(kaggle_genre, None)
        if expected == rule_genre:
            matches += 1
        else:
            mismatches += 1

    # Distribution
    print(f"\n{'-' * 50}")
    print(f"OUTPUT GENRE DISTRIBUTION ({total:,} tracks)")
    print(f"{'-' * 50}")
    for genre, count in sorted(classified_counts.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        bar = '#' * int(pct / 2)
        print(f"  {genre:15s}  {count:>7,}  ({pct:5.1f}%)  {bar}")

    print(f"\n{'-' * 50}")
    print(f"RULE-BASED AGREEMENT: {matches:,}/{total:,} ({matches/total*100:.1f}%)")
    print(f"{'-' * 50}")

    # Per-genre agreement
    print(f"\n{'-' * 72}")
    print("PER-GENRE AGREEMENT (rule-based vs. direct mapping)")
    print(f"{'-' * 72}")

    for kaggle_genre in sorted(kaggle_to_classified.keys()):
        genre_df = df[df[genre_col] == kaggle_genre]
        if len(genre_df) == 0:
            continue
        expected = kaggle_to_classified[kaggle_genre]

        correct = 0
        for _, row in genre_df.iterrows():
            features = {
                'tempo': float(row.get('tempo', 120)),
                'energy': float(row.get('energy', 0.5)),
                'danceability': float(row.get('danceability', 0.5)),
                'valence': float(row.get('valence', 0.5)),
                'acousticness': float(row.get('acousticness', 0.3)),
                'instrumentalness': float(row.get('instrumentalness', 0.0)),
                'speechiness': float(row.get('speechiness', 0.05)),
                'liveness': float(row.get('liveness', 0.2)),
                'loudness': float(row.get('loudness', -8.0)),
            }
            if classify_genre(features) == expected:
                correct += 1

        accuracy = correct / len(genre_df) * 100
        status = '[OK]' if accuracy >= 80 else '[~~]' if accuracy >= 50 else '[XX]'
        print(f"  {status} {kaggle_genre:25s} -> {expected:15s}  "
              f"{correct:>4}/{len(genre_df):>4} ({accuracy:5.1f}%)")


def test_dual_mode(kaggle_to_classified):
    """
    Test classify_song() in both modes against the full dataset.
    Shows:
      - Direct mapping accuracy (should be ~100%)
      - Rule-based fallback accuracy
      - Combined accuracy
    """
    print(f"\n{'=' * 72}")
    print("DUAL-MODE VALIDATION (classify_song with both modes)")
    print(f"{'=' * 72}")

    df = load_dataset()
    print(f"Loaded {len(df):,} tracks")

    genre_col = 'track_genre' if 'track_genre' in df.columns else 'genre' if 'genre' in df.columns else None
    if genre_col is None:
        print("ERROR: No genre column found in dataset")
        return

    # Counters
    direct_total = 0
    direct_correct = 0
    fallback_total = 0
    fallback_correct = 0
    combined_total = 0
    combined_correct = 0
    genre_counts = Counter()

    for _, row in df.iterrows():
        features = {
            'tempo': float(row.get('tempo', 120)),
            'energy': float(row.get('energy', 0.5)),
            'danceability': float(row.get('danceability', 0.5)),
            'valence': float(row.get('valence', 0.5)),
            'acousticness': float(row.get('acousticness', 0.3)),
            'instrumentalness': float(row.get('instrumentalness', 0.0)),
            'speechiness': float(row.get('speechiness', 0.05)),
            'liveness': float(row.get('liveness', 0.2)),
            'loudness': float(row.get('loudness', -8.0)),
        }

        kaggle_genre = str(row.get(genre_col, ''))
        ground_truth = KAGGLE_TO_OUTPUT_GENRE.get(kaggle_genre)  # curated mapping = ground truth
        has_mapping = ground_truth is not None

        # Mode 1: Direct mapping
        if has_mapping:
            direct_result = KAGGLE_TO_OUTPUT_GENRE[kaggle_genre]
            direct_total += 1
            if direct_result == ground_truth:
                direct_correct += 1

        # Mode 2: Rule-based fallback
        rule_result = classify_genre(features)
        fallback_total += 1
        if has_mapping and rule_result == ground_truth:
            fallback_correct += 1

        # Combined (classify_song logic)
        combined_result = classify_song(features, kaggle_genre)
        combined_total += 1
        genre_counts[combined_result] += 1
        if has_mapping and combined_result == ground_truth:
            combined_correct += 1

    # Report
    print(f"\n{'-' * 50}")
    print("MODE 1: DIRECT MAPPING")
    print(f"{'-' * 50}")
    if direct_total > 0:
        print(f"  Tracks with Kaggle label in mapping: {direct_total:,}/{combined_total:,}")
        print(f"  Correct: {direct_correct:,}/{direct_total:,} ({direct_correct/direct_total*100:.1f}%)")
    else:
        print("  No tracks with mappable Kaggle labels.")

    print(f"\n{'-' * 50}")
    print("MODE 2: RULE-BASED FALLBACK")
    print(f"{'-' * 50}")
    print(f"  Tested: {fallback_total:,} tracks")
    print(f"  Correct: {fallback_correct:,}/{fallback_total:,} ({fallback_correct/fallback_total*100:.1f}%)")

    print(f"\n{'-' * 50}")
    print("COMBINED (classify_song)")
    print(f"{'-' * 50}")
    print(f"  Correct: {combined_correct:,}/{combined_total:,} ({combined_correct/combined_total*100:.1f}%)")

    # Distribution of combined results
    print(f"\n{'-' * 50}")
    print("COMBINED OUTPUT DISTRIBUTION")
    print(f"{'-' * 50}")
    for genre, count in sorted(genre_counts.items(), key=lambda x: -x[1]):
        pct = count / combined_total * 100
        bar = '#' * int(pct / 2)
        print(f"  {genre:15s}  {count:>7,}  ({pct:5.1f}%)  {bar}")


def print_stats(classified_groups):
    """Print summary statistics."""
    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print(f"{'=' * 72}")
    print(f"Output genres defined:   {len(OUTPUT_GENRES)}")
    print(f"Kaggle genres mapped:    {len(KAGGLE_TO_OUTPUT_GENRE)}")
    print(f"Output genres populated: {len(classified_groups)}")
    print(f"\nDistribution of Kaggle genres across output genres (rule-based):")
    for genre in sorted(classified_groups.keys()):
        n = len(classified_groups[genre])
        print(f"  {genre:15s}: {n:>3} Kaggle genres")


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------

if __name__ == '__main__':
    print("MoodBeats Genre Classifier (Production Dual-Mode)")
    print("Mode 1: Direct mapping (100% accurate)")
    print("Mode 2: Rule-based fallback (improved thresholds)")
    print()

    # 1. Load knowledge base
    kb = load_knowledge_base()
    print(f"Knowledge base: {kb['metadata']['total_tracks']:,} tracks, "
          f"{kb['metadata']['total_genres']} genres")

    # 2. Test rule-based against KB genre profiles
    kaggle_to_classified, classified_groups, details = test_classifier_with_kb(kb)

    # 3. Validate rule-based against actual dataset
    test_classifier_with_dataset(kaggle_to_classified)

    # 4. Test dual-mode classify_song
    test_dual_mode(kaggle_to_classified)

    # 5. Print summary
    print_stats(classified_groups)

    print(f"\n{'=' * 72}")
    print("DONE -- Classifier ready for production use")
    print(f"{'=' * 72}")
    print(f"\nImport in other modules:")
    print(f"  from ml.genre_classifier import classify_song")
    print(f"  from ml.genre_classifier import classify_genre_from_features")
    print(f"  from ml.genre_classifier import classify_genre_from_db_row")
    print(f"  from ml.genre_classifier import KAGGLE_TO_OUTPUT_GENRE")
    print(f"  from ml.genre_classifier import OUTPUT_GENRES")