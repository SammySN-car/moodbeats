"""
Music Knowledge Base Service
Loads the pre-built knowledge base and provides:
- Mood classification for new songs
- Genre lookup and similarity
- Artist mood fingerprints
- Mood-aware recommendations
"""

import json
import os
import numpy as np
from typing import Dict, List, Optional, Tuple

# Path to knowledge base
KB_PATH = os.path.join(os.path.dirname(__file__), 'music_knowledge_base.json')


class KnowledgeService:
    """Singleton service for music knowledge base operations."""
    
    _instance = None
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._loaded:
            self.load()
    
    def load(self):
        """Load knowledge base from JSON."""
        if not os.path.exists(KB_PATH):
            print(f"Warning: Knowledge base not found at {KB_PATH}")
            self.kb = {}
            return
        
        with open(KB_PATH, 'r') as f:
            self.kb = json.load(f)
        
        self._loaded = True
        print(f"Loaded knowledge base: {self.kb['metadata']['total_tracks']:,} tracks, "
              f"{self.kb['metadata']['total_genres']} genres, "
              f"{len(self.kb['moods']['distribution'])} mood categories")
    
    @property
    def is_loaded(self):
        return self._loaded and bool(self.kb)
    
    # -- MOOD CLASSIFICATION --
    
    def classify_mood_from_features(self, features: Dict[str, float]) -> Tuple[str, float, Dict[str, float]]:
        """Classify mood using Standardized Euclidean Distance + Softmax Probability.
        Returns: (best_mood, confidence_margin, mood_probabilities)"""
        if not self.is_loaded:
            return 'unknown', 0.0, {}
        
        cluster_profiles = self.kb['moods']['cluster_profiles']
        feature_stats = self.kb.get('metadata', {}).get('feature_stats', {})
        
        mood_distances = {}
        
        for mood_label, profile in cluster_profiles.items():
            sq_diff_sum = 0.0
            n_features = 0
            
            for feature_name, centroid_val in profile.items():
                if feature_name in ['track_count', 'percentage', 'gmm_soft_distribution']:
                    continue
                if feature_name in features:
                    val = float(features[feature_name])
                    std = float(feature_stats.get(feature_name, {}).get('std', 1.0))
                    if std < 1e-5:
                        std = 1.0
                    
                    z_diff = (val - centroid_val) / std
                    sq_diff_sum += z_diff ** 2
                    n_features += 1
            
            if n_features > 0:
                mood_distances[mood_label] = np.sqrt(sq_diff_sum / n_features)
            else:
                mood_distances[mood_label] = 10.0
        
        # Canonical cluster merge map: 7 GMM clusters -> 5 frontend moods
        CLUSTER_MERGE_MAP = {
            'euphoric': 'euphoric',
            'peaceful_vocal': 'chill',
            'intense_ambient': 'energetic',
            'melancholic_acoustic': 'chill',
            'melancholic_ambient': 'sad',
            'melancholic_ambient_2': 'sad',
            'melancholic_acoustic_2': 'sad',
        }
        
        tau = 0.5
        mood_keys = list(mood_distances.keys())
        neg_dists = np.array([-mood_distances[k] / tau for k in mood_keys])
        exp_vals = np.exp(neg_dists - np.max(neg_dists))
        raw_probs = exp_vals / np.sum(exp_vals)
        
        merged_probs = {}
        for k, p in zip(mood_keys, raw_probs):
            canonical = CLUSTER_MERGE_MAP.get(k, k)
            merged_probs[canonical] = merged_probs.get(canonical, 0.0) + float(p)
        
        mood_probs = {k: round(v, 4) for k, v in merged_probs.items()}
        
        sorted_items = sorted(mood_probs.items(), key=lambda x: x[1], reverse=True)
        best_mood = sorted_items[0][0]
        
        if len(sorted_items) > 1:
            confidence = round(float(sorted_items[0][1] - sorted_items[1][1]), 4)
        else:
            confidence = round(float(sorted_items[0][1]), 4)
        
        return best_mood, confidence, mood_probs

    # -- GENRE OPERATIONS --
    
    def get_genre_profile(self, genre: str) -> Dict:
        """Get audio profile for a genre."""
        if not self.is_loaded:
            return {}
        return self.kb['genres']['profiles'].get(genre, {})
    
    def get_similar_genres(self, genre: str, top_n: int = 5) -> List[Tuple[str, float]]:
        """Get most similar genres."""
        if not self.is_loaded:
            return []
        similarity = self.kb['genres']['similarity'].get(genre, [])
        return similarity[:top_n]

    def classify_genre_from_features(self, features: Dict[str, float]) -> str:
        """Classify genre from audio features using the rule-based classifier.
        
        Dynamically imports scripts/genre_classifier.py to avoid moving the file.
        """
        import importlib.util
        gc_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'genre_classifier.py')
        spec = importlib.util.spec_from_file_location("genre_classifier", gc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.classify_genre(features)
    
    # -- ARTIST OPERATIONS --
    
    def get_artist_profile(self, artist: str) -> Dict:
        """Get mood fingerprint for an artist."""
        if not self.is_loaded:
            return {}
        # Check top_per_mood for this artist
        top_per_mood = self.kb.get('artists', {}).get('top_per_mood', {})
        for mood, artists in top_per_mood.items():
            for a in artists:
                if a['artist'] == artist:
                    return {
                        'dominant_mood': mood,
                        'track_count': a['track_count'],
                    }
        return {}
    
    # -- SONG PROFILE BUILDER --
    
    def build_song_profile(
        self,
        title: str,
        artist: str,
        genre: str,
        audio_features: Optional[Dict[str, float]] = None,
        **kwargs,
    ) -> str:
        """Build a rich text profile for a song using knowledge base context.
        
        Produces the canonical embedding-style profile:
          "Track: 'X' by Y. Mood: M. Musical Feel: ..., Genre: G. ..."
        
        Accepts either an audio_features dict (backward compat) or individual
        keyword arguments. Individual kwargs take precedence over audio_features.
        
        Supported kwargs:
            mood, tempo, energy, danceability, valence, lyrics_sentiment
        """
        af = audio_features or {}

        # -- resolve values: explicit kwarg > audio_features -----------------
        energy = kwargs.get('energy', af.get('energy', 0.5))
        valence = kwargs.get('valence', af.get('valence', 0.5))
        tempo = kwargs.get('tempo', af.get('tempo', 120.0))
        danceability = kwargs.get('danceability', af.get('danceability', 0.5))
        lyrics_sentiment = kwargs.get('lyrics_sentiment', 0.0)

        # -- mood: caller-supplied or KB-classified --------------------------
        if 'mood' in kwargs:
            mood = kwargs['mood']
        elif af:
            mood, _, _ = self.classify_mood_from_features(af)
        else:
            mood = 'unknown'

        # -- descriptive labels (embedding_service style) --------------------
        energy_desc = (
            "explosive high-energy powerful adrenaline"
            if energy >= 0.7
            else "calm acoustic gentle mellow quiet"
            if energy <= 0.35
            else "moderate steady groove"
        )
        valence_desc = (
            "euphoric joyful upbeat bright"
            if valence >= 0.65
            else "melancholic sad dark sorrowful longing"
            if valence <= 0.35
            else "balanced neutral"
        )
        tempo_desc = (
            f"fast pace {round(tempo)} BPM"
            if tempo >= 125
            else f"slow quiet {round(tempo)} BPM"
            if tempo <= 95
            else f"mid-tempo {round(tempo)} BPM"
        )

        # -- genre context ---------------------------------------------------
        genre_context = ""
        similar_genres_str = ""
        if genre:
            genre_profile = self.get_genre_profile(genre)
            if genre_profile:
                avg_energy = genre_profile.get("energy", 0.5)
                avg_valence = genre_profile.get("valence", 0.5)
                genre_context = f"Genre typical profile: energy {avg_energy:.2f}, valence {avg_valence:.2f}."

            similar = self.get_similar_genres(genre, top_n=3)
            if similar:
                similar_genres_str = "Similar genres: " + ", ".join(
                    f"{g} ({s:.2f})" for g, s in similar
                )

        # -- artist context --------------------------------------------------
        artist_context = ""
        artist_profile = self.get_artist_profile(artist)
        if artist_profile:
            artist_context = f"Artist known for {artist_profile.get('dominant_mood', 'unknown')} mood."

        # -- key detection (from audio_features) -----------------------------
        key_str = ""
        if af:
            key = af.get('key')
            if key is not None:
                key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                key_name = key_names[int(key)] if int(key) < len(key_names) else str(key)
                mode = 'major' if af.get('mode', 1) == 1 else 'minor'
                key_str = f"Key: {key_name} {mode}."

        # -- assemble --------------------------------------------------------
        parts = [
            f"Track: '{title}' by {artist}. Mood: {mood}.",
            f"Musical Feel: {energy_desc}, {valence_desc}, {tempo_desc}.",
            f"Lyrical Sentiment: {round(lyrics_sentiment, 2)}",
        ]
        if genre:
            parts.insert(2, f"Genre: {genre}. {genre_context}")
        if similar_genres_str:
            parts.append(similar_genres_str)
        if artist_context:
            parts.append(artist_context)
        if key_str:
            parts.append(key_str)

        return " ".join(p for p in parts if p)
    
    # -- KNOWLEDGE BASE STATS --
    
    def get_stats(self) -> Dict:
        """Get knowledge base statistics."""
        if not self.is_loaded:
            return {'loaded': False}
        return {
            'loaded': True,
            'total_tracks': self.kb['metadata']['total_tracks'],
            'total_genres': self.kb['metadata']['total_genres'],
            'mood_categories': len(self.kb['moods']['distribution']),
            'genre_clusters': len(self.kb['genres']['clusters']),
            'artist_profiles': self.kb.get('artists', {}).get('qualified_count', 0),
            'features': self.kb['metadata']['mood_features'],
        }


# Global instance
knowledge_service = KnowledgeService()
