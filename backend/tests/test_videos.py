from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.db.models import Chunk, SessionVideo, Video, utc_now
from app.main import app


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///file:test_videos_db?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def create_session(client) -> str:
    response = client.post("/api/v1/sessions", json={"title": "Test Session"})
    return response.json()["id"]


def test_health_check(test_client):
    client, _ = test_client
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "memory" in data
    assert "rss_mb" in data["memory"]
    assert "models" in data
    assert "whisper" in data["models"]
    assert "embeddings" in data["models"]


def test_list_videos(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    data = response.json()
    assert "videos" in data
    assert "total" in data
    assert isinstance(data["videos"], list)
    assert data["total"] >= 0


def test_get_video_not_found(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_add_video(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": session_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "video_id" in data
    assert data["video_id"] == "dQw4w9WgXcQ"
    assert data["status"] == "pending"
    assert "session_video_id" in data


def test_add_video_missing_session_id(test_client):
    client, _ = test_client
    response = client.post(
        "/api/v1/videos/add",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 422


def test_add_video_invalid_session_id(test_client):
    client, _ = test_client
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": "nonexistent-session",
        },
    )
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_add_channel_url_rejected(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/@JeffNippard",
            "session_id": session_id,
        },
    )
    assert response.status_code == 400
    assert "single video URLs" in response.json()["detail"]


def test_add_playlist_url_rejected(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
            "session_id": session_id,
        },
    )
    assert response.status_code == 400
    assert "single video URLs" in response.json()["detail"]


def test_add_video_duplicate_while_processing(test_client):
    client, _ = test_client
    session_id = create_session(client)

    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": session_id,
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": session_id,
        },
    )
    assert response.status_code == 409
    assert "already being processed" in response.json()["detail"]


def test_add_video_retry_after_error(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        sv = SessionVideo(
            session_id=session_id,
            video_id="dQw4w9WgXcQ",
            status="error",
            error_message="Previous error",
        )
        db.add(sv)
        db.commit()

    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": session_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_add_video_already_ready(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        sv = SessionVideo(
            session_id=session_id,
            video_id="dQw4w9WgXcQ",
            status="ready",
        )
        db.add(sv)
        db.commit()

    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": session_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["message"] == "Video already added"


def test_session_video_has_progress_fields(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        video = Video(
            id="test123",
            title="Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test transcript",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

        sv = SessionVideo(
            session_id=session_id,
            video_id="test123",
            status="processing",
            progress=50.0,
            progress_message="Fetching transcript...",
        )
        db.add(sv)
        db.commit()

    response = client.get(f"/api/v1/videos/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["videos"]) == 1
    video = data["videos"][0]
    assert video["status"] == "processing"
    assert video["progress"] == 50.0
    assert video["progress_message"] == "Fetching transcript..."


def test_stale_processing_job_detected(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        video = Video(
            id="stale123",
            title="Stale Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
        )
        db.add(video)
        db.commit()

        old_time = utc_now() - timedelta(minutes=20)
        sv = SessionVideo(
            session_id=session_id,
            video_id="stale123",
            status="processing",
            progress=50.0,
            updated_at=old_time,
        )
        db.add(sv)
        db.commit()

    response = client.get(f"/api/v1/videos/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["videos"]) == 1
    video = data["videos"][0]
    assert video["status"] == "error"
    assert "timed out" in video["error_message"].lower()


def test_delete_video_not_found(test_client):
    client, _ = test_client
    response = client.delete("/api/v1/videos/nonexistent-video-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_get_transcript_success(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="test123",
            title="Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Hello world. This is a test transcript.",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

        chunk1 = Chunk(
            id="test123_0",
            video_id="test123",
            text="Hello world.",
            start_time=0.0,
            end_time=5.0,
            token_count=3,
            embedding=b"fake",
        )
        chunk2 = Chunk(
            id="test123_1",
            video_id="test123",
            text="This is a test transcript.",
            start_time=5.0,
            end_time=10.0,
            token_count=6,
            embedding=b"fake",
        )
        db.add(chunk1)
        db.add(chunk2)
        db.commit()

    response = client.get("/api/v1/videos/test123/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "test123"
    assert data["video_title"] == "Test Video"
    assert data["full_text"] == "Hello world. This is a test transcript."
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "Hello world."
    assert data["segments"][0]["start_time"] == 0.0
    assert data["segments"][1]["start_time"] == 5.0
    assert data["has_timestamps"] is True


def test_get_transcript_not_found(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos/nonexistent/transcript")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_get_transcript_no_transcript(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="notranscript",
            title="No Transcript Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript=None,
            transcript_source=None,
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/notranscript/transcript")
    assert response.status_code == 400
    assert "No transcript" in response.json()["detail"]


def test_get_transcript_no_timestamps(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="whisper123",
            title="Whisper Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Whisper transcribed text.",
            transcript_source="whisper",
        )
        db.add(video)
        db.commit()

        chunk = Chunk(
            id="whisper123_0",
            video_id="whisper123",
            text="Whisper transcribed text.",
            start_time=0.0,
            end_time=0.0,
            token_count=4,
            embedding=b"fake",
        )
        db.add(chunk)
        db.commit()

    response = client.get("/api/v1/videos/whisper123/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["has_timestamps"] is False


def test_session_video_without_video_record(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        sv = SessionVideo(
            session_id=session_id,
            video_id="pending123",
            status="pending",
            progress=10.0,
            progress_message="Queued...",
        )
        db.add(sv)
        db.commit()

    response = client.get(f"/api/v1/videos/session/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["videos"]) == 1
    video = data["videos"][0]
    assert video["id"] == "pending123"
    assert "Loading..." in video["title"]
    assert video["status"] == "pending"


def test_export_txt(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="export_test",
            title="Export Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="This is a test transcript for export.",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/export_test/export?format=txt")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "Export_Test_Video" in response.headers.get("content-disposition", "")


def test_export_markdown(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="export_md",
            title="Markdown Export",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test transcript content.",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/export_md/export?format=md")
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")


def test_export_srt_no_chunks(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="export_srt",
            title="SRT Export",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test transcript.",
            transcript_source="whisper",
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/export_srt/export?format=srt")
    assert response.status_code == 400
    assert "timestamp" in response.json()["detail"].lower()


def test_export_srt_with_chunks(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="export_srt2",
            title="SRT Export With Chunks",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Hello world.",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

        chunk = Chunk(
            id="export_srt2_0",
            video_id="export_srt2",
            text="Hello world.",
            start_time=0.0,
            end_time=5.0,
            token_count=3,
            embedding=b"fake",
        )
        db.add(chunk)
        db.commit()

    response = client.get("/api/v1/videos/export_srt2/export?format=srt")
    assert response.status_code == 200
    assert "text/srt" in response.headers.get("content-type", "")


def test_export_json(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="export_json",
            title="JSON Export",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test transcript.",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/export_json/export?format=json")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "export_json"
    assert data["title"] == "JSON Export"


def test_export_not_found(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos/nonexistent/export?format=txt")
    assert response.status_code == 404


def test_export_no_transcript(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="no_transcript",
            title="No Transcript",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript=None,
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/no_transcript/export?format=txt")
    assert response.status_code == 400
    assert "No transcript" in response.json()["detail"]


def test_delete_video_success(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        video = Video(
            id="delete_me",
            title="Delete Me",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test",
        )
        db.add(video)
        db.commit()

        sv = SessionVideo(
            session_id=session_id,
            video_id="delete_me",
            status="ready",
        )
        db.add(sv)
        db.commit()

    response = client.delete("/api/v1/videos/delete_me")
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify video is deleted
    response = client.get("/api/v1/videos/delete_me")
    assert response.status_code == 404


def test_remove_video_from_session(test_client):
    client, engine = test_client
    session_id = create_session(client)

    with Session(engine) as db:
        video = Video(
            id="remove_from_session",
            title="Remove From Session",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test",
        )
        db.add(video)
        db.commit()

        sv = SessionVideo(
            session_id=session_id,
            video_id="remove_from_session",
            status="ready",
        )
        db.add(sv)
        db.commit()

    response = client.delete(
        f"/api/v1/videos/session/{session_id}/video/remove_from_session"
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_remove_video_from_session_not_found(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.delete(f"/api/v1/videos/session/{session_id}/video/nonexistent")
    assert response.status_code == 404


def test_clear_cache(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="cache_video",
            title="Cache Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=utc_now(),
            transcript="Test",
        )
        db.add(video)
        db.commit()

    response = client.delete("/api/v1/videos/cache/clear")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["videos_cleared"] >= 1


def test_list_session_videos_session_not_found(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos/session/nonexistent-session")
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]
