"""Versioned schema migrations (#12): idempotent, data-preserving, atomic, and in step with data/schema.sql."""

import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from src.config import SCHEMA_PATH
from src.database import init_db
from src.migrations import (
    BASELINE_SQL,
    MIGRATIONS,
    Migration,
    MigrationError,
    rebuild_table,
    run_script,
    status,
    table_exists,
    upgrade,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import migrate


def _engine(path):
    return create_engine(f"sqlite:///{path}", future=True)


def _baseline_db(path):
    """A database as the first version made it, with one row in every table."""
    conn = sqlite3.connect(path)
    conn.executescript(BASELINE_SQL)
    conn.execute("INSERT INTO papers (paper_id, title, year, venue, repo_url, license, expected_claims) "
                 "VALUES ('paper_001', 'T', 2021, 'V', 'https://x', 'MIT', '{\"acc\": 0.9}')")
    conn.execute("INSERT INTO runs (run_id, paper_id, status, exit_code) VALUES ('r1', 'paper_001', 'COMPLETED', 0)")
    conn.execute("INSERT INTO claims (claim_id, paper_id, run_id, metric_name, claimed_value) "
                 "VALUES ('c1', 'paper_001', 'r1', 'acc', 0.9)")
    conn.execute("INSERT INTO scores (score_id, paper_id, run_id, status_label) "
                 "VALUES ('s1', 'paper_001', 'r1', 'Needs Review')")
    conn.commit()
    conn.close()


def _check_clauses(sql):
    clauses = []
    for match in re.finditer(r"check\s*\(", sql, re.IGNORECASE):
        depth, i = 1, match.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        clauses.append(re.sub(r"\s+", "", sql[match.end():i - 1].lower()))
    return sorted(clauses)


def _signature(path):
    conn = sqlite3.connect(path)
    sig = {}
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'schema_migrations'")]
    for name in tables:
        columns = {r[1]: (r[2], r[3], r[4], r[5]) for r in conn.execute(f'PRAGMA table_info("{name}")')}
        foreign_keys = sorted((r[2], r[3], r[4], r[5], r[6]) for r in conn.execute(f'PRAGMA foreign_key_list("{name}")'))
        unique = sorted(tuple(c[2] for c in conn.execute(f'PRAGMA index_info("{i[1]}")'))
                        for i in conn.execute(f'PRAGMA index_list("{name}")') if i[2])
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()[0]
        sig[name] = (columns, foreign_keys, unique, _check_clauses(sql))
    sig["indexes"] = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"))
    conn.close()
    return sig


def test_new_database_gets_every_migration_once(tmp_path):
    engine = _engine(tmp_path / "new.db")
    assert upgrade(engine).applied == [1, 2, 3, 4, 5]
    again = upgrade(engine)
    assert again.applied == [] and again.backup_path is None
    assert [m["version"] for m in status(engine)["applied"]] == [1, 2, 3, 4, 5] and status(engine)["pending"] == []


def test_migrated_schema_equals_schema_sql(tmp_path):
    migrated, created = tmp_path / "migrated.db", tmp_path / "created.db"
    upgrade(_engine(migrated))
    conn = sqlite3.connect(created)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()
    assert _signature(migrated) == _signature(created)


def test_old_database_keeps_its_rows_and_gets_the_new_schema(tmp_path):
    path = tmp_path / "old.db"
    _baseline_db(path)
    result = upgrade(_engine(path))
    assert result.applied == [1, 2, 3, 4, 5]
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT paper_id, expected_claims FROM papers").fetchall() == [("paper_001", '{"acc": 0.9}')]
    assert conn.execute("SELECT run_id, status, exit_code, failure_category FROM runs").fetchall() == [
        ("r1", "COMPLETED", 0, None)]
    assert conn.execute("SELECT claim_id FROM claims").fetchall() == [("c1",)]
    assert conn.execute("SELECT score_id FROM scores").fetchall() == [("s1",)]
    assert table_exists(conn, "extracted_claims")
    conn.close()
    assert _signature(path) == _signature_of_schema_sql(tmp_path)


def _signature_of_schema_sql(tmp_path):
    path = tmp_path / "head.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()
    return _signature(path)


def test_backup_is_made_before_changing_an_old_file_and_holds_the_old_data(tmp_path):
    path = tmp_path / "old.db"
    _baseline_db(path)
    result = upgrade(_engine(path))
    assert result.backup_path is not None and result.backup_path.exists()
    assert result.backup_path.name.startswith("old.db.bak-")
    backup = sqlite3.connect(result.backup_path)
    assert "failure_category" not in [r[1] for r in backup.execute("PRAGMA table_info(runs)")]
    assert backup.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 1
    backup.close()
    assert upgrade(_engine(path)).backup_path is None  # nothing to change, no new copy


def test_no_backup_for_a_new_database_or_when_switched_off(tmp_path):
    assert upgrade(_engine(tmp_path / "new.db")).backup_path is None
    old = tmp_path / "old.db"
    _baseline_db(old)
    assert upgrade(_engine(old), backup=False).backup_path is None
    assert [p.name for p in tmp_path.glob("*.bak-*")] == []


def test_dry_run_changes_nothing(tmp_path):
    path = tmp_path / "old.db"
    _baseline_db(path)
    result = upgrade(_engine(path), dry_run=True)
    assert result.pending == [1, 2, 3, 4, 5] and result.applied == []
    conn = sqlite3.connect(path)
    assert not table_exists(conn, "schema_migrations") and not table_exists(conn, "extracted_claims")
    conn.close()


def test_a_failing_migration_is_rolled_back_and_the_earlier_ones_stay(tmp_path):
    def broken(conn):
        conn.execute("CREATE TABLE half_done (x INTEGER)")
        conn.execute("INSERT INTO papers (paper_id) VALUES ('violates not null columns')")

    path = tmp_path / "old.db"
    _baseline_db(path)
    plan = [*MIGRATIONS, Migration(6, "broken step", broken)]
    with pytest.raises(MigrationError, match="migration 6 .* rolled back"):
        upgrade(_engine(path), migrations=plan)
    conn = sqlite3.connect(path)
    assert not table_exists(conn, "half_done")
    assert [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")] == [1, 2, 3, 4, 5]
    assert conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 1
    conn.close()
    # fixed code applies the step on the next run
    fixed = [*MIGRATIONS, Migration(6, "broken step", lambda c: c.execute("CREATE TABLE half_done (x INTEGER)"))]
    assert upgrade(_engine(path), migrations=fixed).applied == [6]


def test_foreign_key_violation_rolls_the_migration_back(tmp_path):
    def orphan(conn):
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r2', 'no_such_paper', 'FAILED')")

    engine = _engine(tmp_path / "new.db")
    upgrade(engine)
    with pytest.raises(MigrationError, match="foreign key"):
        upgrade(engine, migrations=[*MIGRATIONS, Migration(6, "orphan", orphan)])
    conn = sqlite3.connect(tmp_path / "new.db")
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
    conn.close()


def test_history_that_does_not_fit_the_code_is_refused(tmp_path):
    engine = _engine(tmp_path / "new.db")
    upgrade(engine)
    with pytest.raises(MigrationError, match="newer than the code"):
        upgrade(engine, migrations=MIGRATIONS[:2])
    renamed = [Migration(1, "another name", MIGRATIONS[0].apply), *MIGRATIONS[1:]]
    with pytest.raises(MigrationError, match="must not be edited"):
        upgrade(engine, migrations=renamed)


def test_rebuild_table_keeps_rows_indexes_and_applies_the_new_constraint():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE parent (id TEXT PRIMARY KEY);"
        "CREATE TABLE child (id TEXT PRIMARY KEY, parent_id TEXT NOT NULL REFERENCES parent(id), "
        "state TEXT CHECK(state IN ('a', 'b')), note TEXT);"
        "CREATE INDEX idx_child_parent ON child(parent_id);"
        "INSERT INTO parent VALUES ('p1'); INSERT INTO child VALUES ('c1', 'p1', 'a', 'kept');"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO child VALUES ('c2', 'p1', 'z', NULL)")
    copied = rebuild_table(conn, "child", "CREATE TABLE {name} (id TEXT PRIMARY KEY, parent_id TEXT NOT NULL "
                           "REFERENCES parent(id), state TEXT CHECK(state IN ('a', 'b', 'z')), note TEXT)")
    assert copied == 1
    assert conn.execute("SELECT * FROM child").fetchall() == [("c1", "p1", "a", "kept")]
    conn.execute("INSERT INTO child VALUES ('c2', 'p1', 'z', NULL)")
    assert conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_child_parent'").fetchone()
    assert not table_exists(conn, "child__new")
    with pytest.raises(ValueError, match="{name}"):
        rebuild_table(conn, "child", "CREATE TABLE child (id TEXT)")


def test_rebuild_table_drops_columns_the_new_definition_does_not_have():
    conn = sqlite3.connect(":memory:")
    conn.executescript("CREATE TABLE t (a TEXT, b TEXT); INSERT INTO t VALUES ('x', 'y');")
    rebuild_table(conn, "t", "CREATE TABLE {name} (a TEXT, c TEXT DEFAULT 'new')")
    assert conn.execute("SELECT a, c FROM t").fetchall() == [("x", "new")]


def test_run_script_ignores_comments_and_semicolons_inside_them():
    conn = sqlite3.connect(":memory:")
    run_script(conn, "-- a; comment\nCREATE TABLE t (a TEXT); -- trailing; comment\nINSERT INTO t VALUES ('x;y');")
    assert conn.execute("SELECT a FROM t").fetchall() == [("x;y",)]


def test_foreign_key_setting_is_restored(tmp_path):
    engine = _engine(tmp_path / "new.db")
    raw = engine.raw_connection()
    raw.driver_connection.execute("PRAGMA foreign_keys = ON")
    raw.close()
    upgrade(engine)
    raw = engine.raw_connection()
    try:
        assert raw.driver_connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        raw.close()


def test_init_db_upgrades_an_old_database_and_keeps_its_data(tmp_path):
    path = tmp_path / "old.db"
    _baseline_db(path)
    engine = _engine(path)
    init_db(engine)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT title FROM papers").fetchall() == [("T",)]
    assert "failure_category" in [r[1] for r in conn.execute("PRAGMA table_info(runs)")]
    assert [r[0] for r in conn.execute("SELECT version FROM schema_migrations")] == [1, 2, 3, 4, 5]
    conn.close()
    assert len(list(tmp_path.glob("old.db.bak-*"))) == 1
    init_db(engine)  # again: no second copy, nothing changes
    assert len(list(tmp_path.glob("old.db.bak-*"))) == 1


def test_command_line_status_and_up(tmp_path, capsys):
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    assert migrate.main(["--db-url", url, "status"]) == 0
    assert [m["version"] for m in json.loads(capsys.readouterr().out)["pending"]] == [1, 2, 3, 4, 5]
    assert migrate.main(["--db-url", url, "up", "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["pending"] == [1, 2, 3, 4, 5]
    assert migrate.main(["--db-url", url, "up"]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] == [1, 2, 3, 4, 5]
    assert migrate.main(["--db-url", url, "up"]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] == []


def test_command_line_reports_a_newer_database(tmp_path, capsys):
    path = tmp_path / "cli.db"
    upgrade(_engine(path))
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO schema_migrations VALUES (99, 'from the future', '2030-01-01')")
    conn.commit()
    conn.close()
    assert migrate.main(["--db-url", f"sqlite:///{path}", "up"]) == 1
    assert "newer than the code" in capsys.readouterr().err


def test_old_runs_table_rejects_oom_killed_until_migration_4_and_keeps_its_rows(tmp_path):
    path = tmp_path / "old.db"
    _baseline_db(path)
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r2', 'paper_001', 'OOM_KILLED')")
    conn.close()
    upgrade(_engine(path))
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r2', 'paper_001', 'OOM_KILLED')")
    assert conn.execute("SELECT run_id, status FROM runs ORDER BY run_id").fetchall() == [
        ("r1", "COMPLETED"), ("r2", "OOM_KILLED")]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO runs (run_id, paper_id, status) VALUES ('r3', 'paper_001', 'EXPLODED')")
    # the claims and scores that point at the run still do, and the run's index is back
    assert sorted(r[2] for r in conn.execute("PRAGMA foreign_key_list(claims)")) == ["papers", "runs"]
    assert sorted(r[2] for r in conn.execute("PRAGMA foreign_key_list(scores)")) == ["papers", "runs"]
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'idx_runs_paper_id'").fetchone()
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()
