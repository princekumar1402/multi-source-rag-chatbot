import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base, SessionLocal, engine
from backend.app.models import Workspace, Document, Chunk, Conversation, Message, IngestionJob

@pytest.fixture(autouse=True)
def clean_database():
    """
    Autouse fixture to clean database tables before and after each test run,
    preventing state leakage between tests and ensuring deterministic deduplication.
    """
    with SessionLocal() as session:
        try:
            for table in reversed(Base.metadata.sorted_tables):
                session.execute(table.delete())
            session.commit()
        except Exception:
            session.rollback()

    yield

    with SessionLocal() as session:
        try:
            for table in reversed(Base.metadata.sorted_tables):
                session.execute(table.delete())
            session.commit()
        except Exception:
            session.rollback()
