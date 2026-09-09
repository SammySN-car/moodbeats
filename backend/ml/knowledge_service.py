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
    
    # ── MOOD CLASSIFICATION ──────────────────────────────
    
    def classify_mood_from_features(self, features: Dict[str, float]) -> Tuple[str, float, Dict[str, float]]:
        """
        Classify mood using Standardized Euclidean Distance + Softmax Probability.
        Returns: (best_mood, confidence_margin, mood_probabilities)
        """
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
    
    def get_mood_distribution(self) -> Dict[str, Dict]:
        """Get mood distribution from knowledge base."""
        if not self.is_loaded:
            return {}
        return self.kb['moods']['distribution']
    
    def get_mood_for_genre(self, genre: str) -> Dict[str, float]:
        """Get mood probability distribution for a genre."""
        if not self.is_loaded:
            return {}
        return self.kb.get('mood_genre_matrix', {}).get(genre, {})
    
    # ── GENRE OPERATIONS ─────────────────────────────────
    
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
    
    def get_genre_cluster(self, genre: str) -> Optional[int]:
        """Get cluster ID for a genre."""
        if not self.is_loaded:
            return None
        clusters = self.kb['genres']['clusters']
        for cluster_id, genres in clusters.items():
            if genre in genres:
                return int(cluster_id)
        return None
    
    def get_cluster_genres(self, cluster_id: int) -> List[str]:
        """Get all genres in a cluster."""
        if not self.is_loaded:
            return []
        return self.kb['genres']['clusters'].get(str(cluster_id), [])
    
    # ── ARTIST OPERATIONS ────────────────────────────────
    
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
    
    def get_top_artists_for_mood(self, mood: str, top_n: int = 10) -> List[Dict]:
        """Get top artists for a mood."""
        if not self.is_loaded:
            return []
        return self.kb.get('artists', {}).get('top_per_mood', {}).get(mood, [])[:top_n]
    
    # ── MOOD TRANSITIONS ─────────────────────────────────
    
    def get_next_mood(self, current_mood: str) -> Optional[str]:
        """Get most likely next mood in a sequence."""
        if not self.is_loaded:
            return None
        transitions = self.kb.get('transitions', {}).get('matrix', {})
        if current_mood in transitions:
            probs = transitions[current_mood]
            if probs:
                return max(probs, key=probs.get)
        return None
    
    def get_mood_transitions(self, mood: str) -> Dict[str, float]:
        """Get transition probabilities from a mood."""
        if not self.is_loaded:
            return {}
        return self.kb.get('transitions', {}).get('matrix', {}).get(mood, {})
    
    # ── SONG PROFILE BUILDER ─────────────────────────────
    
    def build_song_profile(self, title: str, artist: str, genre: str,
                          audio_features: Dict[str, float]) -> str:
        """
        Build a rich text profile for a song using knowledge base context.
        This is used for RAG embeddings.
        """
        # Classify mood
        mood, confidence, mood_probs = self.classify_mood_from_features(audio_features)
        
        # Get genre context
        genre_profile = self.get_genre_profile(genre)
        similar_genres = self.get_similar_genres(genre, top_n=3)
        
        # Get tempo zone
        tempo = audio_features.get('tempo', 120)
        if tempo < 80:
            tempo_zone = 'slow'
        elif tempo < 120:
            tempo_zone = 'moderate'
        elif tempo < 160:
            tempo_zone = 'fast'
        else:
            tempo_zone = 'very fast'
        
        # Get energy/valence levels
        energy = audio_features.get('energy', 0.5)
        valence = audio_features.get('valence', 0.5)
        
        energy_level = 'high' if energy > 0.7 else 'medium' if energy > 0.4 else 'low'
        valence_level = 'high' if valence > 0.7 else 'medium' if valence > 0.4 else 'low'
        
        # Build profile string
        profile_parts = [
            f"Title: {title}",
            f"Artist: {artist}",
            f"Genre: {genre}",
            f"Mood: {mood} (confidence: {confidence:.2f})",
            f"Tempo: {tempo_zone} ({tempo:.0f} BPM)",
            f"Energy: {energy_level} ({energy:.2f})",
            f"Valence: {valence_level} ({valence:.2f})",
        ]
        
        # Add key if available
        key = audio_features.get('key')
        if key is not None:
            key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            key_name = key_names[int(key)] if int(key) < len(key_names) else str(key)
            mode = 'major' if audio_features.get('mode', 1) == 1 else 'minor'
            profile_parts.append(f"Key: {key_name} {mode}")
        
        # Add similar genres
        if similar_genres:
            sim_str = ', '.join([f"{g}({s:.2f})" for g, s in similar_genres])
            profile_parts.append(f"Similar genres: {sim_str}")
        
        return ', '.join(profile_parts)
    
    # ── KNOWLEDGE BASE STATS ─────────────────────────────
    
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
