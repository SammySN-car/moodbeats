import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification
from typing import Any, Dict, Optional
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
    """Thin wrapper around knowledge_service.build_song_profile().

    Preserves the original call-site signature for backward compatibility
    while delegating to the single canonical profile builder.
    """
    return knowledge_service.build_song_profile(
        title=title,
        artist=artist,
        genre=genre,
        audio_features=audio_features,
        mood=mood,
        tempo=tempo,
        energy=energy,
        danceability=danceability,
        valence=valence,
        lyrics_sentiment=lyrics_sentiment,
    )
