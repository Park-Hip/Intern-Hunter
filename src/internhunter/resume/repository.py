from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select

from src.internhunter.common.logging import get_logger
from src.internhunter.storage.models import UserProfileDB
from src.internhunter.storage.session import SessionLocal

logger = get_logger(__name__)


class UserProfileRepository:
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        with SessionLocal() as session:
            try:
                statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
                profile = session.execute(statement).scalar_one_or_none()
                if profile:
                    return {
                        "user_id": profile.user_id,
                        "resume_text": profile.resume_text,
                        "resume_embedding": profile.resume_embedding,
                    }
                return None
            except Exception as e:
                logger.error("Failed to get user profile", error=str(e))
                return None

    def save_user_profile(self, user_id: str, resume_text: str, embedding: List[float]) -> bool:
        with SessionLocal() as session:
            try:
                statement = select(UserProfileDB).where(UserProfileDB.user_id == user_id)
                profile = session.execute(statement).scalar_one_or_none()
                if profile:
                    profile.resume_text = resume_text
                    profile.resume_embedding = embedding
                else:
                    profile = UserProfileDB(
                        user_id=user_id,
                        resume_text=resume_text,
                        resume_embedding=embedding,
                    )
                    session.add(profile)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                logger.error("Failed to save user profile", error=str(e))
                return False


__all__ = ["UserProfileRepository"]
