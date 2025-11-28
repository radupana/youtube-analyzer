from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.db.models import Chunk, Message, Session, SessionVideo, Video, VideoAnalysis


class TestSessionModel:
    def test_create_session_with_defaults(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.id is not None
        assert session.title == "Untitled Session"
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_create_session_with_custom_title(self, db_session):
        session = Session(title="My Custom Session")
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.title == "My Custom Session"

    def test_session_has_empty_relationships_by_default(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.messages == []
        assert session.session_videos == []


class TestMessageModel:
    def test_create_message(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        message = Message(
            session_id=session.id,
            role="user",
            content="Hello, world!",
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.id is not None
        assert message.session_id == session.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.created_at is not None

    def test_message_belongs_to_session(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        message = Message(session_id=session.id, role="assistant", content="Hi there!")
        db_session.add(message)
        db_session.commit()
        db_session.refresh(session)

        assert len(session.messages) == 1
        assert session.messages[0].content == "Hi there!"


class TestVideoModel:
    def test_create_video(self, db_session):
        video = Video(
            id="abc123",
            title="Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M30S",
            published_at=datetime.now(),
            transcript="This is a transcript",
            transcript_source="youtube",
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        assert video.id == "abc123"
        assert video.title == "Test Video"
        assert video.channel_title == "Test Channel"
        assert video.transcript == "This is a transcript"
        assert video.transcript_source == "youtube"
        assert video.created_at is not None

    def test_video_nullable_transcript(self, db_session):
        video = Video(
            id="xyz789",
            title="No Transcript Video",
            channel_id="ch456",
            channel_title="Some Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        assert video.transcript is None
        assert video.transcript_source is None


class TestSessionVideoModel:
    def test_create_session_video_link(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = Video(
            id="vid1",
            title="Test Video",
            channel_id="ch1",
            channel_title="Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        session_video = SessionVideo(
            session_id=session.id,
            video_id=video.id,
        )
        db_session.add(session_video)
        db_session.commit()
        db_session.refresh(session_video)

        assert session_video.id is not None
        assert session_video.session_id == session.id
        assert session_video.video_id == video.id
        assert session_video.added_at is not None

    def test_session_video_links_session_to_video(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = Video(
            id="vid1",
            title="Video 1",
            channel_id="ch1",
            channel_title="Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        session_video = SessionVideo(session_id=session.id, video_id=video.id)
        db_session.add(session_video)
        db_session.commit()
        db_session.refresh(session)

        assert len(session.session_videos) == 1
        assert session.session_videos[0].video_id == "vid1"


class TestChunkModel:
    def test_create_chunk(self, db_session):
        video = Video(
            id="vid1",
            title="Test Video",
            channel_id="ch1",
            channel_title="Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        chunk = Chunk(
            id="vid1_0",
            video_id="vid1",
            text="Test chunk content",
            start_time=0.0,
            end_time=30.0,
            token_count=5,
            embedding=b"\x00" * 384 * 4,
        )
        db_session.add(chunk)
        db_session.commit()
        db_session.refresh(chunk)

        assert chunk.id == "vid1_0"
        assert chunk.video_id == "vid1"
        assert chunk.text == "Test chunk content"
        assert chunk.start_time == 0.0
        assert chunk.end_time == 30.0

    def test_video_has_chunks_relationship(self, db_session):
        video = Video(
            id="vid1",
            title="Test Video",
            channel_id="ch1",
            channel_title="Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        for i in range(3):
            chunk = Chunk(
                id=f"vid1_{i}",
                video_id="vid1",
                text=f"Chunk {i}",
                start_time=float(i * 10),
                end_time=float((i + 1) * 10),
                token_count=5,
                embedding=b"\x00" * 384 * 4,
            )
            db_session.add(chunk)
        db_session.commit()
        db_session.refresh(video)

        assert len(video.chunks) == 3


class TestCascadeDelete:
    def test_delete_session_deletes_messages(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        msg1 = Message(session_id=session.id, role="user", content="Message 1")
        msg2 = Message(session_id=session.id, role="assistant", content="Message 2")
        db_session.add_all([msg1, msg2])
        db_session.commit()

        result = db_session.exec(select(Message)).all()
        assert len(result) == 2

        db_session.delete(session)
        db_session.commit()

        result = db_session.exec(select(Message)).all()
        assert len(result) == 0

    def test_delete_session_deletes_session_videos(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = Video(
            id="vid1",
            title="Video",
            channel_id="ch1",
            channel_title="Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        session_video = SessionVideo(session_id=session.id, video_id=video.id)
        db_session.add(session_video)
        db_session.commit()

        result = db_session.exec(select(SessionVideo)).all()
        assert len(result) == 1

        db_session.delete(session)
        db_session.commit()

        result = db_session.exec(select(SessionVideo)).all()
        assert len(result) == 0

        video_still_exists = db_session.get(Video, "vid1")
        assert video_still_exists is not None

    def test_delete_video_deletes_chunks(self, db_session):
        video = Video(
            id="vid1",
            title="Video",
            channel_id="ch1",
            channel_title="Channel",
            duration="PT5M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        chunk = Chunk(
            id="vid1_0",
            video_id="vid1",
            text="Test",
            start_time=0.0,
            end_time=10.0,
            token_count=1,
            embedding=b"\x00" * 384 * 4,
        )
        db_session.add(chunk)
        db_session.commit()

        result = db_session.exec(select(Chunk)).all()
        assert len(result) == 1

        db_session.delete(video)
        db_session.commit()

        result = db_session.exec(select(Chunk)).all()
        assert len(result) == 0


class TestMultipleRecords:
    def test_multiple_messages_in_session(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        for i in range(5):
            msg = Message(
                session_id=session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            db_session.add(msg)
        db_session.commit()
        db_session.refresh(session)

        assert len(session.messages) == 5

    def test_multiple_videos_in_session(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        for i in range(3):
            video = Video(
                id=f"vid{i}",
                title=f"Video {i}",
                channel_id=f"ch{i}",
                channel_title="Channel",
                duration="PT5M",
                published_at=datetime.now(),
            )
            db_session.add(video)
            db_session.commit()

            session_video = SessionVideo(session_id=session.id, video_id=video.id)
            db_session.add(session_video)

        db_session.commit()
        db_session.refresh(session)

        assert len(session.session_videos) == 3

    def test_multiple_sessions(self, db_session):
        sessions = [Session(title=f"Session {i}") for i in range(3)]
        db_session.add_all(sessions)
        db_session.commit()

        result = db_session.exec(select(Session)).all()
        assert len(result) == 3


class TestVideoAnalysisModel:
    def test_create_video_analysis(self, db_session):
        video = Video(
            id="test123",
            title="Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=datetime.now(),
            transcript="Test transcript",
        )
        db_session.add(video)
        db_session.commit()

        analysis = VideoAnalysis(
            video_id="test123",
            summary="This is a test summary.",
            key_takeaways='["Point 1", "Point 2"]',
            main_topics='["Topic A"]',
            notable_quotes='["Quote 1"]',
            model_used="gemini/gemini-2.5-flash",
        )
        db_session.add(analysis)
        db_session.commit()
        db_session.refresh(analysis)

        assert analysis.id is not None
        assert analysis.video_id == "test123"
        assert analysis.summary == "This is a test summary."
        assert analysis.model_used == "gemini/gemini-2.5-flash"
        assert analysis.created_at is not None

    def test_video_analysis_unique_constraint(self, db_session):
        video = Video(
            id="test456",
            title="Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=datetime.now(),
        )
        db_session.add(video)
        db_session.commit()

        analysis1 = VideoAnalysis(
            video_id="test456",
            summary="First",
            key_takeaways="[]",
            main_topics="[]",
            notable_quotes="[]",
            model_used="test",
        )
        db_session.add(analysis1)
        db_session.commit()

        analysis2 = VideoAnalysis(
            video_id="test456",
            summary="Second",
            key_takeaways="[]",
            main_topics="[]",
            notable_quotes="[]",
            model_used="test",
        )
        db_session.add(analysis2)

        with pytest.raises(IntegrityError):
            db_session.commit()
