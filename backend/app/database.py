from contextlib import contextmanager

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base


@contextmanager
def open_database(url: str):
    engine = create_engine(
        url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )
    try:
        Base.metadata.create_all(bind=engine)
        yield sessionmaker(bind=engine, autoflush=False)
    finally:
        engine.dispose()


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db
