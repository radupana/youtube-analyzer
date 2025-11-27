from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

DATABASE_DIR = Path(".data")
DATABASE_PATH = DATABASE_DIR / "youtube-analyzer.db"

_engine = None


def get_database_url() -> str:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATABASE_PATH}"


def init_db() -> None:
    global _engine
    _engine = create_engine(
        get_database_url(), connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(_engine)


def get_engine():
    if _engine is None:
        init_db()
    return _engine


def get_session() -> Generator[Session]:
    engine = get_engine()
    with Session(engine) as session:
        yield session
