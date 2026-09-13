-- Repro Radar: SQLite Database Schema
-- Defines entities for papers, sandbox execution runs, empirical claims, and tiered reproducibility scores.

PRAGMA foreign_keys = ON;

-- 1. PAPERS: Stores curated research paper metadata, repository links, and execution targets
CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER NOT NULL CHECK(year >= 1990 AND year <= 2100),
    venue TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    paper_url TEXT,
    license TEXT NOT NULL,
    target_script TEXT NOT NULL DEFAULT 'run.py',
    expected_claims TEXT NOT NULL, -- JSON formatted dict of {metric_name: value}
    source_table_or_section TEXT, -- JSON formatted dict of {metric_name: table_or_section}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. RUNS: Execution logs and diagnostic outcomes from isolated sandbox environments
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT')),
    execution_time REAL, -- in seconds
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    seed INTEGER DEFAULT 42,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
);

-- 3. CLAIMS: Individual numeric claims extracted from paper vs reproduced output
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    run_id TEXT,
    metric_name TEXT NOT NULL,
    claimed_value REAL NOT NULL,
    reproduced_value REAL,
    tolerance REAL NOT NULL DEFAULT 0.05,
    matches INTEGER CHECK(matches IN (0, 1) OR matches IS NULL),
    difference REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE SET NULL
);

-- 4. SCORES: 4-Tier Reproducibility Evaluation Scores and Neutral Status Classifications
CREATE TABLE IF NOT EXISTS scores (
    score_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL UNIQUE,
    run_id TEXT,
    tier1_build REAL NOT NULL DEFAULT 0.0 CHECK(tier1_build >= 0.0 AND tier1_build <= 100.0),
    tier2_metrics REAL NOT NULL DEFAULT 0.0 CHECK(tier2_metrics >= 0.0 AND tier2_metrics <= 100.0),
    tier3_stability REAL NOT NULL DEFAULT 0.0 CHECK(tier3_stability >= 0.0 AND tier3_stability <= 100.0),
    tier4_artifacts REAL NOT NULL DEFAULT 0.0 CHECK(tier4_artifacts >= 0.0 AND tier4_artifacts <= 100.0),
    total_score REAL NOT NULL DEFAULT 0.0 CHECK(total_score >= 0.0 AND total_score <= 100.0),
    status_label TEXT NOT NULL CHECK(status_label IN ('Verified', 'Partially Verified', 'Needs Review', 'Failed')),
    summary TEXT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE SET NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_runs_paper_id ON runs(paper_id);
CREATE INDEX IF NOT EXISTS idx_claims_paper_id ON claims(paper_id);
CREATE INDEX IF NOT EXISTS idx_scores_paper_id ON scores(paper_id);
CREATE INDEX IF NOT EXISTS idx_scores_status_label ON scores(status_label);
