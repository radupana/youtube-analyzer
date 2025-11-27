"""Tests for embedding service."""

import numpy as np

from app.services.chunking import TranscriptChunk
from app.services.embeddings import (
    EMBEDDING_DIMENSION,
    generate_chunk_embeddings,
    generate_embeddings,
    generate_query_embedding,
)


class TestGenerateEmbeddings:
    def test_empty_list_returns_empty_array(self):
        result = generate_embeddings([])
        assert result.shape == (0, EMBEDDING_DIMENSION)
        assert result.dtype == np.float32

    def test_single_text_returns_correct_shape(self):
        result = generate_embeddings(["Hello world"])
        assert result.shape == (1, EMBEDDING_DIMENSION)
        assert result.dtype == np.float32

    def test_multiple_texts_returns_correct_shape(self):
        texts = ["First text", "Second text", "Third text"]
        result = generate_embeddings(texts)
        assert result.shape == (3, EMBEDDING_DIMENSION)
        assert result.dtype == np.float32

    def test_similar_texts_have_higher_similarity(self):
        texts = [
            "The cat sat on the mat",
            "A cat is sitting on a mat",
            "Python programming language",
        ]
        embeddings = generate_embeddings(texts)

        sim_0_1 = np.dot(embeddings[0], embeddings[1])
        sim_0_2 = np.dot(embeddings[0], embeddings[2])

        assert sim_0_1 > sim_0_2


class TestGenerateChunkEmbeddings:
    def test_empty_chunks_returns_empty_list(self):
        result = generate_chunk_embeddings([])
        assert result == []

    def test_single_chunk_returns_tuple(self):
        chunk = TranscriptChunk(
            id="v1_0",
            video_id="v1",
            text="Test chunk text",
            start_time=0.0,
            end_time=5.0,
            token_count=3,
        )
        result = generate_chunk_embeddings([chunk])

        assert len(result) == 1
        assert result[0][0] is chunk
        assert result[0][1].shape == (EMBEDDING_DIMENSION,)

    def test_multiple_chunks_preserves_order(self):
        chunks = [
            TranscriptChunk(
                id=f"v1_{i}",
                video_id="v1",
                text=f"Chunk number {i}",
                start_time=float(i * 10),
                end_time=float((i + 1) * 10),
                token_count=3,
            )
            for i in range(5)
        ]
        result = generate_chunk_embeddings(chunks)

        assert len(result) == 5
        for i, (chunk, embedding) in enumerate(result):
            assert chunk.id == f"v1_{i}"
            assert embedding.shape == (EMBEDDING_DIMENSION,)


class TestGenerateQueryEmbedding:
    def test_returns_correct_shape(self):
        result = generate_query_embedding("What is the main topic?")
        assert result.shape == (EMBEDDING_DIMENSION,)
        assert result.dtype == np.float32

    def test_query_similar_to_matching_text(self):
        query = "What is machine learning?"
        query_embedding = generate_query_embedding(query)

        texts = [
            "Machine learning is a branch of artificial intelligence",
            "The weather is nice today",
        ]
        text_embeddings = generate_embeddings(texts)

        sim_to_ml = np.dot(query_embedding, text_embeddings[0])
        sim_to_weather = np.dot(query_embedding, text_embeddings[1])

        assert sim_to_ml > sim_to_weather
