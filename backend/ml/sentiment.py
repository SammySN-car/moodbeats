from typing import Any, cast
from transformers import pipeline

_sentiment_pipeline = None

def get_sentiment_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        _sentiment_pipeline = cast(Any, pipeline)(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            device=-1
        )
    return _sentiment_pipeline

def analyze_sentiment(text: str) -> float:
    if not text or len(text.strip()) < 15:
        return 0.0
    try:
        analyzer = get_sentiment_pipeline()
        truncated_text = text[:500]
        result = analyzer(truncated_text)[0]
        score = result["score"]
        return score if result["label"] == "POSITIVE" else -score
    except Exception:
        return 0.0