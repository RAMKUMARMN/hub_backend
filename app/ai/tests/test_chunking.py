import pytest
from app.ai.services.vector_service import chunk_text

def test_chunk_text_small_paragraphs():
    """
    Verifies that multiple small paragraphs are grouped together into chunks
    until the chunk size limit is reached.
    """
    text = (
        "Paragraph one is here.\n\n"
        "Paragraph two is here.\n\n"
        "Paragraph three is here."
    )
    # chunk_size of 55 allows Paragraph 1 & 2 to merge (~46 chars), while Paragraph 3 is separate
    chunks = chunk_text(text, chunk_size=55, overlap=10)
    assert len(chunks) == 2
    assert chunks[0] == "Paragraph one is here.\n\nParagraph two is here."
    assert "Paragraph three is here." in chunks[1]

def test_chunk_text_large_paragraph_sentence_split():
    """
    Verifies that an individual paragraph exceeding chunk_size is split
    on sentence boundaries.
    """
    text = (
        "This is sentence one. "
        "This is sentence two. "
        "This is sentence three. "
        "This is sentence four."
    )
    # chunk_size=50 restricts each chunk to ~2 sentences, splitting on punctuation
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50
    # Sentences should be complete
    assert chunks[0].strip() == "This is sentence one. This is sentence two."
    
def test_chunk_text_very_long_sentence_word_split():
    """
    Verifies that a single sentence exceeding chunk_size is split
    at word boundaries rather than characters.
    """
    # A single sentence with 10 words, each word 10 letters -> 110 characters
    long_sentence = " ".join(["wordtenlet"] * 10)
    assert len(long_sentence) == 109
    
    # chunk_size=40 means it must split by words
    chunks = chunk_text(long_sentence, chunk_size=40, overlap=5)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40
        # Ensure it didn't cut inside a word
        words = chunk.split()
        for w in words:
            assert w == "wordtenlet"

def test_chunk_text_respects_overlap():
    """
    Verifies that consecutive chunks carry overlap forward correctly.
    """
    text = (
        "This is first part of the long text. "
        "This is second part of the long text."
    )
    chunks = chunk_text(text, chunk_size=45, overlap=15)
    assert len(chunks) == 2
    
    # Chunk 1 should start with the aligned overlap segment: "the long text."
    assert chunks[1].startswith("the long text.")
