import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.ai.services.vector_service import search_relevant_chunks
from app.ai.services.reranker_service import rerank_candidates

@pytest.mark.asyncio
async def test_rerank_candidates_sorting():
    mock_candidates = [
        {"text": "passage low score", "id": 1},
        {"text": "passage high score", "id": 2},
    ]
    
    mock_scores = [0.1, 0.9]
    
    with patch("app.ai.services.reranker_service._predict_sync", return_value=mock_scores) as mock_predict:
        reranked = await rerank_candidates("query text", mock_candidates)
        
        assert len(reranked) == 2
        assert reranked[0]["id"] == 2
        assert reranked[0]["rerank_score"] == 0.9
        assert reranked[1]["id"] == 1
        assert reranked[1]["rerank_score"] == 0.1
        
        mock_predict.assert_called_once_with("query text", ["passage low score", "passage high score"])


@pytest.mark.asyncio
async def test_search_relevant_chunks_calls_reranker():
    user_id = uuid.uuid4()
    query = "explain CPU pipelining"
    
    mock_candidates = [
        ({"text": "pipelining is fast", "document_id": str(uuid.uuid4()), "chunk_index": 1, "filename": "coa.txt"}, 0.8),
    ]
    
    mock_reranked_scores = [1.5]
    
    with patch("app.ai.services.vector_service._semantic_candidates", return_value=mock_candidates), \
         patch("app.ai.services.vector_service.qdrant_client.collection_exists", return_value=True), \
         patch("app.ai.services.reranker_service._predict_sync", return_value=mock_reranked_scores) as mock_predict:
         
        results = await search_relevant_chunks(
            user_id=user_id,
            query=query,
            limit=2,
            retrieval_mode="semantic",
            use_reranker=True,
        )
        
        assert len(results) == 1
        assert results[0]["filename"] == "coa.txt"
        assert results[0]["text"] == "pipelining is fast"
        assert results[0]["score"] == 0.817574
        mock_predict.assert_called_once()


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_rerank_candidates():
    """
    Live integration test for Cross-Encoder reranking.
    Loads the actual model from disk/cache and reranks real text candidates.
    """
    query = "what is CPU pipelining"
    candidates = [
        {"text": "The recipe for chocolate chip cookies includes flour, sugar, butter, and chocolate chips.", "id": "cookies"},
        {"text": "Pipelining is an implementation technique where multiple instructions are overlapped in execution.", "id": "pipelining"},
    ]
    
    reranked = await rerank_candidates(query, candidates)
    
    assert len(reranked) == 2
    # The relevant passage must have a higher score and be ranked first
    assert reranked[0]["id"] == "pipelining"
    assert reranked[1]["id"] == "cookies"
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]
