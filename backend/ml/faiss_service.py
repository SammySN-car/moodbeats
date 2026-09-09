"""FAISS similarity search service."""

import json
import numpy as np
from pathlib import Path

INDEX_PATH = Path(__file__).parent / 'song_index.faiss'
MAPPING_PATH = Path(__file__).parent / 'song_id_mapping.json'


class FAISSService:
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
        try:
            import faiss
        except ImportError:
            self.index = None
            self.song_ids = []
            return
        if not INDEX_PATH.exists() or not MAPPING_PATH.exists():
            self.index = None
            self.song_ids = []
            return
        self.index = faiss.read_index(str(INDEX_PATH))
        with open(MAPPING_PATH, 'r') as f:
            self.song_ids = json.load(f)
        self._loaded = True
        print(f'FAISS index loaded: {self.index.ntotal} vectors')

    @property
    def is_loaded(self):
        return self._loaded and self.index is not None

    def search(self, query_embedding, top_k=20):
        if not self.is_loaded:
            return []
        import faiss
        q = np.asarray(query_embedding, dtype='float32').reshape(1, -1)
        faiss.normalize_L2(q)
        if self.index.ntotal == 0:
            return []
        scores, indices = self.index.search(q, min(top_k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self.song_ids):
                results.append((self.song_ids[idx], float(score)))
        return results

    def get_index_stats(self):
        if not self.is_loaded:
            return {'loaded': False}
        return {
            'loaded': True,
            'total_vectors': self.index.ntotal,
            'dimension': self.index.d,
            'total_songs': len(self.song_ids),
        }


faiss_service = FAISSService()