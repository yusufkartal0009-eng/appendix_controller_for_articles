"""Versioned schema migrations for the SQLite database (#12).

`data/schema.sql` creates a database at the current schema. A database that already exists (benchmark runs, scores,
reviewed claims) cannot be recreated, so every later change to the schema is a migration here:

- Migrations are numbered and applied in order. The applied ones are recorded in the `schema_migrations` table, so
  running `upgrade` again changes nothing (idempotent).
- Each migration runs in one transaction: it is applied completely or not at all.
- Before the first change, a file database is copied to `<name>.bak-<timestamp>` (SQLite's backup API), so a bad
  upgrade can be undone by putting the copy back.
- SQLite cannot change a constraint in place. `rebuild_table` copies the rows into a new table with the new
  definition and swaps it in, so existing data is kept.

To change the schema: edit `data/schema.sql` (the schema of a new database), add a migration that does the same to an
existing database, and keep both in step. `tests/test_migrations.py` fails when a database migrated from the
original schema differs from one created by `data/schema.sql`. Do not edit or renumber a migration that has been
merged; add a new one.

Command line: `python scripts/migrate.py status | up [--dry-run] [--no-backup]`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import Engine

MIGRATIONS_TABLE = "schema_migrations"

# The schema of the first databases (Pre-M0, commit 7a7d9ac of data/schema.sql), kept as it was.
BASELINE_SQL = """
-- Repro Radar: SQLite Database Schema
-- Defines entities for papers, sandbox execution runs, empirical claims, and tiered reproducibility scores.


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
"""

# Added after the baseline: claims extracted from the papers, with their review status (W6, #197).
EXTRACTED_CLAIMS_SQL = """
-- 3b. EXTRACTED CLAIMS: claims extracted from the paper text, with provenance and human review (W6, #10).
-- verified_by: 'auto-quote-match' (quote guard matched, not an approval) or 'human' (a person decided).
-- Only review_status = 'accepted' with verified_by = 'human' reaches the scorer.
CREATE TABLE IF NOT EXISTS extracted_claims (
    extracted_claim_id TEXT PRIMARY KEY, -- "<paper_id>:<query_id>"
    paper_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    dataset TEXT,
    model_variant TEXT,
    split TEXT,
    value REAL NOT NULL,
    value_as_printed TEXT NOT NULL,
    higher_is_better BOOLEAN,
    page INTEGER NOT NULL,
    table_or_section TEXT,
    quote TEXT NOT NULL,
    source_file TEXT NOT NULL,
    pdf_sha256 TEXT,
    extractor_version TEXT NOT NULL,
    verified_by TEXT CHECK(verified_by IN ('auto-quote-match', 'human') OR verified_by IS NULL),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending', 'accepted', 'rejected')),
    reviewed_at TIMESTAMP,
    review_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (paper_id, query_id),
    CHECK(review_status = 'pending' OR verified_by = 'human'),
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_extracted_claims_paper_id ON extracted_claims(paper_id);
"""


class MigrationError(RuntimeError):
    """A migration failed (the database was rolled back) or the migration history does not fit this code."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


@dataclass
class UpgradeResult:
    applied: list[int] = field(default_factory=list)
    pending: list[int] = field(default_factory=list)  # filled for a dry run
    backup_path: Path | None = None


# --- helpers a migration can use -------------------------------------------------------------------------------

def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    return row is not None


def column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]


def add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> bool:
    """`ALTER TABLE ... ADD COLUMN` unless the column is already there. Returns True when it was added."""
    if column in column_names(conn, table):
        return False
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')
    return True


def run_script(conn: sqlite3.Connection, script: str) -> None:
    """Run the statements of an SQL script one by one (`executescript` would commit the open transaction)."""
    for statement in split_statements(script):
        conn.execute(statement)


def split_statements(script: str) -> list[str]:
    """Split a script at semicolons, leaving out `--` comments; quoted text may contain `;` and `--`."""
    statements: list[str] = []
    current: list[str] = []
    quote = ""
    i = 0
    while i < len(script):
        ch = script[i]
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
            current.append(ch)
        elif script.startswith("--", i):
            while i < len(script) and script[i] != "\n":
                i += 1
            continue
        elif ch == ";":
            statements.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    statements.append("".join(current).strip())
    return [stmt for stmt in statements if stmt]


def rebuild_table(conn: sqlite3.Connection, table: str, new_ddl: str) -> int:
    """Replace a table's definition and keep its rows. Returns the number of rows copied.

    `new_ddl` is a `CREATE TABLE {name} (...)` statement for the new definition; `{name}` is replaced by a temporary
    name. Columns that exist in both definitions are copied; indexes and triggers of the old table are created again.
    The caller runs this inside a migration, which has foreign key checks off and a transaction open.
    """
    if "{name}" not in new_ddl:
        raise ValueError("new_ddl must create the table as {name}")
    temp = f"{table}__new"
    old_columns = column_names(conn, table)
    extras = conn.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name = ? AND type IN ('index', 'trigger') AND sql IS NOT NULL",
        (table,),
    ).fetchall()
    conn.execute(f'DROP TABLE IF EXISTS "{temp}"')
    conn.execute(new_ddl.replace("{name}", f'"{temp}"'))
    shared = [c for c in column_names(conn, temp) if c in old_columns]
    columns = ", ".join(f'"{c}"' for c in shared)
    conn.execute(f'INSERT INTO "{temp}" ({columns}) SELECT {columns} FROM "{table}"')
    copied = conn.execute(f'SELECT COUNT(*) FROM "{temp}"').fetchone()[0]
    conn.execute(f'DROP TABLE "{table}"')
    conn.execute(f'ALTER TABLE "{temp}" RENAME TO "{table}"')
    for (sql,) in extras:
        conn.execute(sql)
    return int(copied)


# --- the migrations --------------------------------------------------------------------------------------------

def _v1_baseline(conn: sqlite3.Connection) -> None:
    run_script(conn, BASELINE_SQL)


def _v2_failure_category(conn: sqlite3.Connection) -> None:
    """Pilot failure categories next to the run (P4) and the index on claims.run_id."""
    if table_exists(conn, "runs"):
        add_column_if_missing(conn, "runs", "failure_category", "TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_run_id ON claims(run_id)")


def _v3_extracted_claims(conn: sqlite3.Connection) -> None:
    run_script(conn, EXTRACTED_CLAIMS_SQL)


# runs.status with the status the sandbox reports when the kernel kills a run for memory (#267).
RUNS_WITH_OOM_STATUS_SQL = """
CREATE TABLE {name} (
    run_id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT', 'OOM_KILLED')),
    execution_time REAL, -- in seconds
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    seed INTEGER DEFAULT 42,
    failure_category TEXT, -- pilot failure category (docs/PILOT_WEEK2.md section 7), NULL if not categorized
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
)
"""


def _v4_runs_oom_status(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'runs'").fetchone()
    if row is not None and "OOM_KILLED" not in row[0]:
        rebuild_table(conn, "runs", RUNS_WITH_OOM_STATUS_SQL)


MIGRATIONS: list[Migration] = [
    Migration(1, "baseline tables (papers, runs, claims, scores)", _v1_baseline),
    Migration(2, "runs.failure_category and idx_claims_run_id", _v2_failure_category),
    Migration(3, "extracted_claims table", _v3_extracted_claims),
    Migration(4, "runs.status accepts OOM_KILLED", _v4_runs_oom_status),
]


# --- running them ----------------------------------------------------------------------------------------------

def _raw_connection(engine: Engine):
    if engine.dialect.name != "sqlite":
        raise MigrationError(f"migrations support SQLite only, not {engine.dialect.name}")
    return engine.raw_connection()


def database_file(engine: Engine) -> Path | None:
    name = engine.url.database
    if not name or name == ":memory:":
        return None
    return Path(name)


def has_user_tables(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != ? LIMIT 1",
        (MIGRATIONS_TABLE,),
    ).fetchone()
    return row is not None


def applied_versions(conn: sqlite3.Connection) -> dict[int, str]:
    if not table_exists(conn, MIGRATIONS_TABLE):
        return {}
    return {int(v): str(n) for v, n in conn.execute(f"SELECT version, name FROM {MIGRATIONS_TABLE}")}


def check_history(applied: dict[int, str], migrations: list[Migration]) -> None:
    known = {m.version: m.name for m in migrations}
    for version, name in applied.items():
        if version not in known:
            raise MigrationError(f"the database has migration {version} ({name}), which this code does not know: "
                                 "the database is newer than the code")
        if known[version] != name:
            raise MigrationError(f"migration {version} was applied as {name!r} but is now {known[version]!r}: "
                                 "a merged migration must not be edited")


def backup_database(source: sqlite3.Connection, path: Path) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.bak-{stamp}")
    counter = 1
    while target.exists():
        counter += 1
        target = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
    return target


def upgrade(engine: Engine, backup: bool = True, dry_run: bool = False,
            migrations: list[Migration] | None = None) -> UpgradeResult:
    """Apply the migrations that the database has not seen. Safe to run again."""
    plan = sorted(migrations if migrations is not None else MIGRATIONS, key=lambda m: m.version)
    raw = _raw_connection(engine)
    conn: sqlite3.Connection = raw.driver_connection
    previous_isolation = conn.isolation_level
    previous_foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    result = UpgradeResult()
    try:
        applied = applied_versions(conn)
        check_history(applied, plan)
        pending = [m for m in plan if m.version not in applied]
        if dry_run:
            result.pending = [m.version for m in pending]
            return result
        if not pending:
            return result
        path = database_file(engine)
        if backup and path is not None and path.exists() and has_user_tables(conn):
            conn.commit()
            result.backup_path = backup_database(conn, path)
        conn.isolation_level = None  # explicit BEGIN / COMMIT below
        conn.execute("PRAGMA foreign_keys = OFF")  # must be set outside a transaction
        conn.execute(f"CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} "
                     "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
        for migration in pending:
            conn.execute("BEGIN IMMEDIATE")
            try:
                migration.apply(conn)
                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise MigrationError(f"foreign key violations after the migration: {violations[:3]}")
                conn.execute(f"INSERT INTO {MIGRATIONS_TABLE} (version, name, applied_at) VALUES (?, ?, ?)",
                             (migration.version, migration.name, datetime.now().astimezone().isoformat(timespec="seconds")))
                conn.execute("COMMIT")
            except Exception as exc:
                conn.execute("ROLLBACK")
                where = f" The database was copied to {result.backup_path} first." if result.backup_path else ""
                raise MigrationError(f"migration {migration.version} ({migration.name}) failed and was rolled back: "
                                     f"{exc}.{where}") from exc
            result.applied.append(migration.version)
        return result
    finally:
        try:
            conn.execute(f"PRAGMA foreign_keys = {int(previous_foreign_keys)}")
        finally:
            conn.isolation_level = previous_isolation
            raw.close()


def status(engine: Engine) -> dict[str, object]:
    """The applied and pending migrations, without changing anything."""
    raw = _raw_connection(engine)
    try:
        applied = applied_versions(raw.driver_connection)
    finally:
        raw.close()
    check_history(applied, MIGRATIONS)
    return {
        "applied": [{"version": v, "name": n} for v, n in sorted(applied.items())],
        "pending": [{"version": m.version, "name": m.name} for m in MIGRATIONS if m.version not in applied],
    }
