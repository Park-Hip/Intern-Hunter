from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

from src.internhunter.config.settings import settings
from src.internhunter.common.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    def __init__(self):
        if isinstance(settings.DB_URL, str):
            self.db_url = settings.DB_URL
        else:
            self.db_url = settings.DB_URL.get_secret_value()

        if not self.db_url:
            logger.critical("DB_URL is missing in settings!")
            raise ValueError("No db_url is specified")

        connect_args = {}
        if "sqlite" in self.db_url:
            connect_args["check_same_thread"] = False

        self.engine = create_engine(
            self.db_url,
            pool_pre_ping=True,
            connect_args=connect_args,
            json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
            pool_size=10,
            max_overflow=20,
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

    def get_db(self):
        session = self.SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


db_manager = DatabaseManager()

engine = db_manager.engine
SessionLocal = db_manager.SessionLocal


def get_db():
    return db_manager.get_db()


__all__ = ["DatabaseManager", "db_manager", "engine", "SessionLocal", "get_db"]

