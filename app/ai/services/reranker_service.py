import asyncio
import logging
from typing import List, Dict
from sentence_transformers import CrossEncoder
from app.config import settings

logger = logging.getLogger(__name__)

_model: CrossEncoder | None = None

def get_reranker_model() -> CrossEncoder:
    """Lazy loads and caches the CrossEncoder model in memory."""
    global _model
    if _model is None:
        model_name = settings.reranker_model
        logger.info(f"Initializing Cross-Encoder model {model_name}...")
        # This will download the model to ~/.cache/huggingface on first run
        _model = CrossEncoder(model_name)
        logger.info(f"Cross-Encoder model {model_name} loaded successfully.")
    return _model


def _predict_sync(query: str, passages: List[str]) -> List[float]:
    """Synchronous CPU/GPU bound prediction run."""
    model = get_reranker_model()
    pairs = [(query, passage) for passage in passages]
    scores = model.predict(pairs)
    # Ensure scores are standard floats
    return [float(score) for score in scores]


async def rerank_candidates(query: str, candidates: List[Dict]) -> List[Dict]:
    """
    Rerank candidate passages using BAAI/bge-reranker-base.
    Runs in a background thread to prevent blocking the async loop.
    """
    if not candidates:
        return []

    passages = [c["text"] for c in candidates]
    
    # Offload CPU/GPU execution to thread pool
    scores = await asyncio.to_thread(_predict_sync, query, passages)
    
    reranked = []
    for idx, candidate in enumerate(candidates):
        item = dict(candidate)
        item["rerank_score"] = scores[idx]
        reranked.append(item)
        
    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    return reranked
