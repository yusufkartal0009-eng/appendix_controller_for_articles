"""Unit tests for Repro Radar models and schemas."""

import pytest
from pydantic import ValidationError

from src.models import ClaimCreate, PaperCreate, RunCreate, ScoreBreakdown


def test_paper_create_valid():
    """Test creating a valid Paper model."""
    data = {
        "paper_id": "paper_test_01",
        "title": "A Great Benchmark for Tabular ML",
        "year": 2023,
        "venue": "NeurIPS 2023",
        "repo_url": "https://github.com/example/tabular-ml",
        "paper_url": "https://arxiv.org/abs/2301.00000",
        "license": "MIT",
        "target_script": "run.py",
        "expected_claims": {"roc_auc": 0.88, "accuracy": 0.85},
    }
    paper = PaperCreate(**data)
    assert paper.paper_id == "paper_test_01"
    assert paper.year == 2023
    assert paper.expected_claims["roc_auc"] == 0.88


def test_paper_create_invalid_url():
    """Test validation failure on invalid repo_url."""
    data = {
        "paper_id": "paper_invalid",
        "title": "Invalid URL Paper",
        "year": 2022,
        "venue": "ArXiv",
        "repo_url": "not-a-valid-url",
        "license": "MIT",
    }
    with pytest.raises(ValidationError):
        PaperCreate(**data)


def test_paper_create_invalid_year():
    """Test validation failure on out-of-range year."""
    data = {
        "paper_id": "paper_invalid_year",
        "title": "Time Traveler Paper",
        "year": 1800,
        "venue": "Historical Society",
        "repo_url": "https://github.com/example/repo",
        "license": "MIT",
    }
    with pytest.raises(ValidationError):
        PaperCreate(**data)


def test_run_create():
    """Test creating a valid Run model."""
    run_data = {
        "run_id": "run_001",
        "paper_id": "paper_test_01",
        "status": "COMPLETED",
        "execution_time": 42.5,
        "exit_code": 0,
        "stdout": "Benchmark finished successfully.",
        "stderr": "",
        "seed": 42,
    }
    run = RunCreate(**run_data)
    assert run.status == "COMPLETED"
    assert run.exit_code == 0
    assert run.execution_time == 42.5


def test_claim_create():
    """Test creating a valid Claim model."""
    claim_data = {
        "claim_id": "claim_001",
        "paper_id": "paper_test_01",
        "metric_name": "accuracy",
        "claimed_value": 0.85,
        "reproduced_value": 0.848,
        "tolerance": 0.05,
        "matches": True,
        "difference": -0.002,
    }
    claim = ClaimCreate(**claim_data)
    assert claim.metric_name == "accuracy"
    assert claim.matches is True


def test_score_breakdown():
    """Test valid ScoreBreakdown model."""
    score_data = {
        "tier1_build": 100.0,
        "tier2_metrics": 95.0,
        "tier3_stability": 90.0,
        "tier4_artifacts": 100.0,
        "total_score": 96.5,
        "status_label": "Verified",
        "summary": "Results fully verified.",
    }
    score = ScoreBreakdown(**score_data)
    assert score.total_score == 96.5
    assert score.status_label == "Verified"
