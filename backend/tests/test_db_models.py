from sqlmodel import select

from app.db.models import Message, Session, SessionVideo


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
        assert session.videos == []


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


class TestSessionVideoModel:
    def test_create_session_video(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = SessionVideo(
            session_id=session.id,
            video_id="abc123",
            title="Test Video",
            channel_title="Test Channel",
            transcript="This is a transcript",
            transcript_source="youtube",
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        assert video.id is not None
        assert video.video_id == "abc123"
        assert video.title == "Test Video"
        assert video.channel_title == "Test Channel"
        assert video.transcript == "This is a transcript"
        assert video.transcript_source == "youtube"
        assert video.added_at is not None

    def test_session_video_nullable_transcript(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = SessionVideo(
            session_id=session.id,
            video_id="xyz789",
            title="No Transcript Video",
            channel_title="Some Channel",
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        assert video.transcript is None
        assert video.transcript_source is None

    def test_video_belongs_to_session(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = SessionVideo(
            session_id=session.id,
            video_id="vid1",
            title="Video 1",
            channel_title="Channel",
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(session)

        assert len(session.videos) == 1
        assert session.videos[0].video_id == "vid1"


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

    def test_delete_session_deletes_videos(self, db_session):
        session = Session()
        db_session.add(session)
        db_session.commit()

        video = SessionVideo(
            session_id=session.id,
            video_id="vid1",
            title="Video",
            channel_title="Channel",
        )
        db_session.add(video)
        db_session.commit()

        result = db_session.exec(select(SessionVideo)).all()
        assert len(result) == 1

        db_session.delete(session)
        db_session.commit()

        result = db_session.exec(select(SessionVideo)).all()
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
            video = SessionVideo(
                session_id=session.id,
                video_id=f"vid{i}",
                title=f"Video {i}",
                channel_title="Channel",
            )
            db_session.add(video)
        db_session.commit()
        db_session.refresh(session)

        assert len(session.videos) == 3

    def test_multiple_sessions(self, db_session):
        sessions = [Session(title=f"Session {i}") for i in range(3)]
        db_session.add_all(sessions)
        db_session.commit()

        result = db_session.exec(select(Session)).all()
        assert len(result) == 3
