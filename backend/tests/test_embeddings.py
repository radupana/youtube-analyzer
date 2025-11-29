"""Tests for embedding service."""

import numpy as np
import pytest

from app.services.embeddings import (
    EMBEDDING_DIMENSION,
    clear_model,
    generate_embeddings,
    generate_query_embedding,
)


class TestGenerateEmbeddings:
    def test_empty_list_returns_empty_array(self):
        result = generate_embeddings([])
        assert result.shape == (0, EMBEDDING_DIMENSION)
        assert result.dtype == np.float32

    @pytest.mark.requires_embeddings
    def test_single_text_returns_correct_shape(self):
        result = generate_embeddings(["Hello world"])
        assert result.shape == (1, EMBEDDING_DIMENSION)
        assert result.dtype == np.float32

    @pytest.mark.requires_embeddings
    def test_multiple_texts_returns_correct_shape(self):
        texts = ["First text", "Second text", "Third text"]
        result = generate_embeddings(texts)
        assert result.shape == (3, EMBEDDING_DIMENSION)
        assert result.dtype == np.float32

    @pytest.mark.requires_embeddings
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


class TestGenerateQueryEmbedding:
    @pytest.mark.requires_embeddings
    def test_returns_correct_shape(self):
        result = generate_query_embedding("What is the main topic?")
        assert result.shape == (EMBEDDING_DIMENSION,)
        assert result.dtype == np.float32

    @pytest.mark.requires_embeddings
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


class TestClearModel:
    @pytest.mark.requires_embeddings
    def test_clear_model_clears_global(self):
        generate_embeddings(["test"])
        import app.services.embeddings as emb

        assert emb._model is not None
        clear_model()
        assert emb._model is None

    def test_clear_model_when_not_loaded(self):
        import app.services.embeddings as emb

        emb._model = None
        clear_model()
        assert emb._model is None
