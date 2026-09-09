import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification
from typing import Any, Dict, Optional, Tuple
from .knowledge_service import knowledge_service

_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_bi_tokenizer: Any = None
_bi_model: Any = None
_cross_tokenizer: Any = None
_cross_model: Any = None

def get_device():
    return _device

def _mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

def get_bi_encoder():
    global _bi_tokenizer, _bi_model
    if _bi_model is None:
        model_id = "sentence-transformers/all-MiniLM-L6-v2"
        _bi_tokenizer = AutoTokenizer.from_pretrained(model_id)
        _bi_model = AutoModel.from_pretrained(model_id).to(_device)
        _bi_model.eval()
    return _bi_tokenizer, _bi_model

def get_cross_encoder():
    global _cross_tokenizer, _cross_model
    if _cross_model is None:
        model_id = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        _cross_tokenizer = AutoTokenizer.from_pretrained(model_id)
        _cross_model = AutoModelForSequenceClassification.from_pretrained(model_id).to(_device)
        _cross_model.eval()
    return _cross_tokenizer, _cross_model

def get_text_embedding_tensor(text: str) -> list[float]:
    tokenizer, model = get_bi_encoder()
    with torch.inference_mode():
        encoded = tokenizer([text], padding=True, truncation=True, max_length=256, return_tensors="pt").to(_device)
        output = model(**encoded)
        pooled = _mean_pooling(output, encoded["attention_mask"])
        normalized = F.normalize(pooled, p=2, dim=1)
    return normalized.squeeze(0).cpu().tolist()

def get_batch_embeddings_tensor(texts: list[str]) -> torch.Tensor:
    tokenizer, model = get_bi_encoder()
    with torch.inference_mode():
        encoded = tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors="pt").to(_device)
        output = model(**encoded)
        pooled = _mean_pooling(output, encoded["attention_mask"])
        normalized = F.normalize(pooled, p=2, dim=1)
    return normalized

def neural_cross_rerank(query: str, doc_texts: list[str]) -> list[float]:
    if not doc_texts:
        return []
    tokenizer, model = get_cross_encoder()
    pairs = [[query, doc] for doc in doc_texts]
    encoded = tokenizer([p[0] for p in pairs], [p[1] for p in pairs], padding=True, truncation=True, max_length=256, return_tensors="pt").to(_device)
    with torch.inference_mode():
        logits = model(**encoded).logits.squeeze(-1)
    return logits.cpu().tolist()

def classify_mood_from_audio(features: Dict[str, float]) -> Tuple[str, float, Dict[str, float]]:
    """
    Classify mood from audio features using the knowledge base.

    Args:
        features: Dict of feature_name -> value (energy, valence, tempo, etc.)

    Returns:
        (mood_label, confidence, mood_probabilities)
    """
    mood, confidence, probs = knowledge_service.classify_mood_from_features(features)
    return mood, confidence, probs

def build_song_profile_text(
    title: str,
    artist: str,
    mood: str,
    tempo: float,
    energy: float,
    danceability: float = 0.5,
    valence: float = 0.5,
    lyrics_sentiment: float = 0.0,
    genre: str = "",
    audio_features: Optional[Dict[str, float]] = None,
) -> str:
    """Build a rich text profile for a song used for embedding and BM25 search.

    When audio_features are provided the knowledge base is consulted for mood
    classification, genre context, and similar-genre information. This produces
    a significantly richer profile than the original rule-based approach.
    """
    # --- knowledge-base enrichment (when available) ----------------------
    kb_mood = mood
    genre_context = ""
    similar_genres_str = ""
    artist_context = ""

    if audio_features and knowledge_service.is_loaded:
        kb_mood, kb_conf, _ = knowledge_service.classify_mood_from_features(audio_features)
        if kb_conf > 0.6:
            mood = kb_mood

        if genre:
            genre_profile = knowledge_service.get_genre_profile(genre)
            if genre_profile:
                avg_energy = genre_profile.get("energy", 0.5)
                avg_valence = genre_profile.get("valence", 0.5)
                genre_context = f"Genre typical profile: energy {avg_energy:.2f}, valence {avg_valence:.2f}."

            similar = knowledge_service.get_similar_genres(genre, top_n=3)
            if similar:
                similar_genres_str = "Similar genres: " + ", ".join(
                    f"{g} ({s:.2f})" for g, s in similar
                )

        artist_profile = knowledge_service.get_artist_profile(artist)
        if artist_profile:
            artist_context = f"Artist known for {artist_profile.get('dominant_mood', 'unknown')} mood."

    # --- descriptive labels ------------------------------------------------
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

    return " ".join(p for p in parts if p)
