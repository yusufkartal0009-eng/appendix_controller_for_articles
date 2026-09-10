"""Configuration settings for Repro Radar."""

from pathlib import Path
import os

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
SRC_DIR = PROJECT_ROOT / "src"

# Database & Schema paths
DEFAULT_DB_NAME = "repro_radar.db"
DEFAULT_DB_PATH = DATA_DIR / DEFAULT_DB_NAME
DB_URL = os.getenv("REPRO_RADAR_DB_URL", f"sqlite:///{DEFAULT_DB_PATH}")
SCHEMA_PATH = DATA_DIR / "schema.sql"
SEED_PAPERS_PATH = DATA_DIR / "seed_papers.json"

# Sandbox & Execution Paths
SANDBOX_TEMP_DIR = PROJECT_ROOT / "temp_clones"
SANDBOX_RUNS_DIR = PROJECT_ROOT / "sandbox_runs"

# Scoring Tier Weights (Must sum to 1.0)
TIER1_BUILD_WEIGHT = 0.35       # Build: clone + dependency install + exit code 0
TIER2_METRICS_WEIGHT = 0.35     # Claim vs Reproduced Metric alignment within tolerance
TIER3_STABILITY_WEIGHT = 0.15   # Multi-seed invariance & run variance
TIER4_ARTIFACTS_WEIGHT = 0.15   # Documentation, license, pinned requirements, logs

# Metric Tolerance Defaults
DEFAULT_TOLERANCE = 0.05        # Default 5% relative/absolute tolerance for claims

# Thresholds for Reproducibility Status
SCORE_VERIFIED_THRESHOLD = 85.0
SCORE_PARTIALLY_VERIFIED_THRESHOLD = 60.0

# Neutral Status Labels
STATUS_VERIFIED = "Doğrulandı"
STATUS_PARTIALLY_VERIFIED = "Kısmen Doğrulandı"
STATUS_NEEDS_REVIEW = "İncelenmeli"
STATUS_FAILED = "Tekrarlanamadı"

# Allowed Open Source Licenses for Evaluation
ALLOWED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC-BY-4.0",
    "ISC",
}

# Timeout limits (in seconds) for lightweight tabular / NLP benchmarks
DEFAULT_TIMEOUT_SECONDS = 600   # 10 minutes
