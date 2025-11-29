import os
from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine

os.environ.setdefault("YOUTUBE_API_KEY", "test-youtube-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

# Check if sentence_transformers is available (for embedding tests)
try:
    import sentence_transformers  # noqa: F401

    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_embeddings: mark test as requiring sentence_transformers",
    )


def pytest_collection_modifyitems(config, items):
    """Skip tests that require embeddings if sentence_transformers not installed."""
    if HAS_SENTENCE_TRANSFORMERS:
        return

    skip_embeddings = pytest.mark.skip(reason="sentence_transformers not installed")
    for item in items:
        if "requires_embeddings" in item.keywords:
            item.add_marker(skip_embeddings)


@pytest.fixture
def db_session() -> Generator[Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def sample_video_transcripts():
    return [
        {
            "title": "Test Video 1",
            "channel_title": "Test Channel",
            "transcript": "This is the transcript of test video 1.",
        },
        {
            "title": "Test Video 2",
            "channel_title": "Another Channel",
            "transcript": None,
        },
    ]


@pytest.fixture
def long_transcript():
    return "x" * 6000
