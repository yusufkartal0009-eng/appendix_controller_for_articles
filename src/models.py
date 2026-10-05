"""Data models and schemas for Repro Radar.

Includes:
- Pydantic models for data validation, serialization, and ingestion
- SQLAlchemy ORM models for relational persistence in SQLite
"""

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ==========================================
# SQLAlchemy ORM Models
# ==========================================

class PaperORM(Base):
    """Represents a research paper and its target reproduction repository."""
    __tablename__ = "papers"

    paper_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    venue = Column(String, nullable=False)
    repo_url = Column(String, nullable=False)
    paper_url = Column(String, nullable=True)
    license = Column(String, nullable=False)
    target_script = Column(String, nullable=False, default="run.py")
    expected_claims = Column(Text, nullable=False)  # Stored as JSON string
    source_table_or_section = Column(Text, nullable=True)  # Stored as JSON string
    created_at = Column(DateTime, default=func.now())

    # Relationships
    runs = relationship("RunORM", back_populates="paper", cascade="all, delete-orphan")
    claims = relationship("ClaimORM", back_populates="paper", cascade="all, delete-orphan")
    extracted_claims = relationship("ExtractedClaimORM", back_populates="paper", cascade="all, delete-orphan")
    scores = relationship("ScoreORM", back_populates="paper", uselist=False, cascade="all, delete-orphan")

    def get_expected_claims_dict(self) -> dict[str, float]:
        """Parse expected_claims JSON string into a Python dict."""
        try:
            return json.loads(self.expected_claims)
        except (ValueError, TypeError):
            return {}

    def get_source_table_or_section_dict(self) -> dict[str, str]:
        """Parse source_table_or_section JSON string into a Python dict."""
        try:
            return json.loads(self.source_table_or_section or "{}")
        except (ValueError, TypeError):
            return {}


class RunORM(Base):
    """Represents a sandbox execution run of a paper's code."""
    __tablename__ = "runs"

    run_id = Column(String, primary_key=True)
    paper_id = Column(String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False)  # PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT, OOM_KILLED
    execution_time = Column(Float, nullable=True)
    exit_code = Column(Integer, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    seed = Column(Integer, default=42)
    # Pilot failure category (docs/PILOT_WEEK2.md section 7); NULL for runs that were not categorized
    failure_category = Column(String, nullable=True)
    timestamp = Column(DateTime, default=func.now())

    # Relationships
    paper = relationship("PaperORM", back_populates="runs")
    claims = relationship("ClaimORM", back_populates="run")
    scores = relationship("ScoreORM", back_populates="run")


class ClaimORM(Base):
    """Represents an empirical claim extracted from paper vs reproduced metric."""
    __tablename__ = "claims"

    claim_id = Column(String, primary_key=True)
    paper_id = Column(String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String, ForeignKey("runs.run_id", ondelete="SET NULL"), nullable=True)
    metric_name = Column(String, nullable=False)
    claimed_value = Column(Float, nullable=False)
    reproduced_value = Column(Float, nullable=True)
    tolerance = Column(Float, nullable=False, default=0.05)
    matches = Column(Integer, nullable=True)  # 1 = True, 0 = False, None = Not evaluated
    difference = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    paper = relationship("PaperORM", back_populates="claims")
    run = relationship("RunORM", back_populates="claims")


class ExtractedClaimORM(Base):
    """A claim extracted from a paper, with its provenance and its human review (W6, #10).

    `verified_by`: 'auto-quote-match' (the quote guard found quote and value in the paper text; not an approval)
    or 'human' (a person accepted or rejected it). Only `review_status == 'accepted'` with `verified_by == 'human'`
    reaches the scorer (src/claim_store.py).
    """
    __tablename__ = "extracted_claims"

    extracted_claim_id = Column(String, primary_key=True)  # "<paper_id>:<query_id>"
    paper_id = Column(String, ForeignKey("papers.paper_id", ondelete="CASCADE"), nullable=False)
    query_id = Column(String, nullable=False)  # question in data/claim_queries/<paper_id>.json
    metric_name = Column(String, nullable=False)
    dataset = Column(String, nullable=True)
    model_variant = Column(String, nullable=True)
    split = Column(String, nullable=True)
    value = Column(Float, nullable=False)  # normalized value
    value_as_printed = Column(String, nullable=False)
    higher_is_better = Column(Boolean, nullable=True)
    page = Column(Integer, nullable=False)  # PDF page number
    table_or_section = Column(String, nullable=True)
    quote = Column(Text, nullable=False)
    source_file = Column(String, nullable=False)  # extraction file, e.g. data/claims/paper_003.json
    pdf_sha256 = Column(String, nullable=True)
    extractor_version = Column(String, nullable=False)
    verified_by = Column(String, nullable=True)  # 'auto-quote-match' | 'human' | NULL (quote not matched)
    review_status = Column(String, nullable=False, default="pending")  # 'pending' | 'accepted' | 'rejected'
    reviewed_at = Column(DateTime, nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("paper_id", "query_id"),
        CheckConstraint("verified_by IN ('auto-quote-match', 'human') OR verified_by IS NULL"),
        CheckConstraint("review_status IN ('pending', 'accepted', 'rejected')"),
        CheckConstraint("review_status = 'pending' OR verified_by = 'human'"),
    )

    paper = relationship("PaperORM", back_populates="extracted_claims")


class ScoreORM(Base):
    """Represents the 4-tier reproducibility evaluation score for a paper."""
    __tablename__ = "scores"

    score_id = Column(String, primary_key=True)
    paper_id = Column(String, ForeignKey("papers.paper_id", ondelete="CASCADE"), unique=True, nullable=False)
    run_id = Column(String, ForeignKey("runs.run_id", ondelete="SET NULL"), nullable=True)
    tier1_build = Column(Float, nullable=False, default=0.0)
    tier2_metrics = Column(Float, nullable=False, default=0.0)
    tier3_stability = Column(Float, nullable=False, default=0.0)
    tier4_artifacts = Column(Float, nullable=False, default=0.0)
    total_score = Column(Float, nullable=False, default=0.0)
    status_label = Column(String, nullable=False)  # 'Verified', 'Partially Verified', 'Needs Review', 'Failed'
    summary = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=func.now())

    # Relationships
    paper = relationship("PaperORM", back_populates="scores")
    run = relationship("RunORM", back_populates="scores")


# ==========================================
# Pydantic Schemas (Validation & Serialization)
# ==========================================

class PaperBase(BaseModel):
    paper_id: str = Field(..., description="Unique paper identifier, e.g. paper_001")
    title: str = Field(..., min_length=3, description="Paper title")
    year: int = Field(..., ge=1990, le=2100, description="Publication year")
    venue: str = Field(..., description="Publication venue or archive")
    repo_url: str = Field(..., description="Target repository URL")
    paper_url: str | None = Field(None, description="Direct paper URL (e.g. arXiv)")
    license: str = Field(..., description="Open source license")
    target_script: str = Field("run.py", description="Target execution script")
    expected_claims: dict[str, float] = Field(default_factory=dict, description="Key numerical claims")
    source_table_or_section: dict[str, str] | None = Field(default_factory=dict, description="Source table or section reference for each claim")

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("repo_url must be a valid URL starting with http:// or https://")
        return v


class PaperCreate(PaperBase):
    pass


class PaperRead(PaperBase):
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class RunBase(BaseModel):
    run_id: str
    paper_id: str
    status: str
    execution_time: float | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    seed: int = 42


class RunCreate(RunBase):
    pass


class RunRead(RunBase):
    timestamp: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ClaimBase(BaseModel):
    claim_id: str
    paper_id: str
    run_id: str | None = None
    metric_name: str
    claimed_value: float
    reproduced_value: float | None = None
    tolerance: float = 0.05
    matches: bool | None = None
    difference: float | None = None


class ClaimCreate(ClaimBase):
    pass


class ClaimRead(ClaimBase):
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class ScoreBreakdown(BaseModel):
    tier1_build: float = Field(..., ge=0.0, le=100.0, description="Score for build and clean execution (0-100)")
    tier2_metrics: float = Field(..., ge=0.0, le=100.0, description="Score for metric claims match (0-100)")
    tier3_stability: float = Field(..., ge=0.0, le=100.0, description="Score for seed stability & variance (0-100)")
    tier4_artifacts: float = Field(..., ge=0.0, le=100.0, description="Score for documentation, license & artifacts (0-100)")
    total_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score (0-100)")
    status_label: str = Field(..., description="Neutral reproducibility classification")
    summary: str | None = None


class ScoreCreate(ScoreBreakdown):
    score_id: str
    paper_id: str
    run_id: str | None = None


class ScoreRead(ScoreCreate):
    evaluated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
