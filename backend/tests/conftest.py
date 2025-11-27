import os

import pytest

os.environ.setdefault("YOUTUBE_API_KEY", "test-youtube-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")


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
