from sqlalchemy import Column, Integer, Boolean, String, JSON, Float, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class RawJobDB(Base):
    __tablename__ = "raw_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)

    url = Column(String, unique=True, nullable=False)
    crawl_run_id = Column(String, index=True, nullable=True)
    source_seed_url = Column(String, index=True, nullable=True)
    title = Column(String)
    company = Column(String)
    location = Column(String)

    full_json_dump = Column(JSON)

    # New production-grade fields
    status = Column(String, default="pending")  # pending, validated, failed, completed
    extraction_method = Column(String, default="css")  # css, raw
    raw_markdown = Column(Text, nullable=True)
    html_content = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)

    clean_job = relationship(
        "CleanJobDB",
        back_populates="raw_job",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AuditJobDB(Base):
    __tablename__ = "audit_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False)
    crawl_run_id = Column(String, index=True, nullable=True)
    source_seed_url = Column(String, index=True, nullable=True)
    error_type = Column(String)  # BOT_DETECTED, SELECTOR_MISSING, LLM_INCOMPLETE, VALIDATION_FAILED
    error_message = Column(Text)
    screenshot_path = Column(String, nullable=True)
    html_content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CleanJobDB(Base):
    __tablename__ = "clean_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_job_id = Column(Integer, ForeignKey("raw_jobs.id"), unique=True)

    standardized_title = Column(String, index=True)
    company = Column(String, nullable=True)
    job_level = Column(String)
    is_internship = Column(Boolean, default=False)

    description = Column(Text)
    requirement = Column(Text)
    benefit = Column(Text)

    cities = Column(JSON)

    experience = Column(Float, nullable=True)
    min_gpa = Column(Float, nullable=True)
    english_requirement = Column(String, nullable=True)

    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    currency = Column(String, default="VND")
    is_salary_negotiable = Column(Boolean, default=False)

    tech_stack = Column(JSON)  # Tools: ["Python", "AWS"]
    technical_competencies = Column(JSON)  # Actions: ["Deploy Models", "Fine-tune LLMs"]
    domain_knowledge = Column(JSON)  # Context: ["Banking", "E-commerce, NLP, Computer Vision, LLM, RAG"]

    embedding = Column(Vector(768))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    raw_job = relationship("RawJobDB", back_populates="clean_job")


class UserProfileDB(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    resume_text = Column(Text)
    resume_embedding = Column(Vector(768))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PipelineRunDB(Base):
    __tablename__ = "pipeline_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    jobs_acquired = Column(Integer, default=0)
    jobs_processed = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    status = Column(String, default="completed")  # completed, failed


__all__ = [
    "Base",
    "RawJobDB",
    "AuditJobDB",
    "CleanJobDB",
    "UserProfileDB",
    "PipelineRunDB",
]
