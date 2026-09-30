"""Data models and schemas for Repro Radar.

Includes:
- Pydantic models for data validation, serialization, and ingestion
- SQLAlchemy ORM models for relational persistence in SQLite
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
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
    scores = relationship("ScoreORM", back_populates="paper", uselist=False, cascade="all, delete-orphan")

    def get_expected_claims_dict(self) -> Dict[str, float]:
        """Parse expected_claims JSON string into a Python dict."""
        try:
            return json.loads(self.expected_claims)
        except (ValueError, TypeError):
            return {}

    def get_source_table_or_section_dict(self) -> Dict[str, str]:
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
    paper_url: Optional[str] = Field(None, description="Direct paper URL (e.g. arXiv)")
    license: str = Field(..., description="Open source license")
    target_script: str = Field("run.py", description="Target execution script")
    expected_claims: Dict[str, float] = Field(default_factory=dict, description="Key numerical claims")
    source_table_or_section: Optional[Dict[str, str]] = Field(default_factory=dict, description="Source table or section reference for each claim")

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError("repo_url must be a valid URL starting with http:// or https://")
        return v


class PaperCreate(PaperBase):
    pass


class PaperRead(PaperBase):
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RunBase(BaseModel):
    run_id: str
    paper_id: str
    status: str
    execution_time: Optional[float] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    seed: int = 42


class RunCreate(RunBase):
    pass


class RunRead(RunBase):
    timestamp: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ClaimBase(BaseModel):
    claim_id: str
    paper_id: str
    run_id: Optional[str] = None
    metric_name: str
    claimed_value: float
    reproduced_value: Optional[float] = None
    tolerance: float = 0.05
    matches: Optional[bool] = None
    difference: Optional[float] = None


class ClaimCreate(ClaimBase):
    pass


class ClaimRead(ClaimBase):
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ScoreBreakdown(BaseModel):
    tier1_build: float = Field(..., ge=0.0, le=100.0, description="Score for build and clean execution (0-100)")
    tier2_metrics: float = Field(..., ge=0.0, le=100.0, description="Score for metric claims match (0-100)")
    tier3_stability: float = Field(..., ge=0.0, le=100.0, description="Score for seed stability & variance (0-100)")
    tier4_artifacts: float = Field(..., ge=0.0, le=100.0, description="Score for documentation, license & artifacts (0-100)")
    total_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score (0-100)")
    status_label: str = Field(..., description="Neutral reproducibility classification")
    summary: Optional[str] = None


class ScoreCreate(ScoreBreakdown):
    score_id: str
    paper_id: str
    run_id: Optional[str] = None


class ScoreRead(ScoreCreate):
    evaluated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
