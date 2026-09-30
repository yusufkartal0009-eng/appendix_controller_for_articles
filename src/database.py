"""Database setup, session management, schema initialization, and seeding for Repro Radar."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import DB_URL, DEFAULT_DB_PATH, SCHEMA_PATH, SEED_PAPERS_PATH
from src.models import Base, ClaimORM, PaperCreate, PaperORM, RunORM, ScoreORM

# Global engine and sessionmaker instances
_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def get_engine(db_url: Optional[str] = None) -> Engine:
    """Get or create SQLAlchemy engine."""
    global _engine
    if db_url is not None:
        return create_engine(db_url, echo=False, future=True)
    if _engine is None:
        # Ensure parent directory exists for default SQLite path
        if "sqlite:///" in DB_URL:
            DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(DB_URL, echo=False, future=True)
    return _engine


def get_session(engine: Optional[Engine] = None) -> Session:
    """Create a new database session."""
    global _SessionFactory
    eng = engine or get_engine()
    if _SessionFactory is None or _SessionFactory.kw.get("bind") != eng:
        _SessionFactory = sessionmaker(bind=eng, autoflush=False, autocommit=False, expire_on_commit=False)
    return _SessionFactory()


def init_db(engine: Optional[Engine] = None, schema_file: Optional[Path] = None, drop_existing: bool = False) -> None:
    """Initialize database tables using schema.sql script and/or ORM metadata."""
    eng = engine or get_engine()
    schema_path = schema_file or SCHEMA_PATH

    # If drop requested, drop all ORM tables first
    if drop_existing:
        Base.metadata.drop_all(bind=eng)

    if schema_path.exists():
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        # Execute schema.sql statements
        with eng.connect() as conn:
            # Split and execute individual statements because SQLite handles them cleanly
            statements = [s.strip() for s in sql_script.split(";") if s.strip()]
            for stmt in statements:
                conn.execute(text(stmt))
            conn.commit()
    else:
        # Fallback to ORM metadata creation if schema.sql is absent
        Base.metadata.create_all(bind=eng)

    ensure_failure_category_column(eng)


def ensure_failure_category_column(engine: Engine) -> bool:
    """Add runs.failure_category to SQLite databases created before the column existed.

    `CREATE TABLE IF NOT EXISTS` leaves existing tables unchanged, so older local databases need this
    one-column upgrade. Returns True when the column was added.
    """
    if engine.dialect.name != "sqlite":
        return False
    with engine.connect() as conn:
        columns = [row[1] for row in conn.execute(text("PRAGMA table_info(runs)"))]
        if not columns or "failure_category" in columns:
            return False
        conn.execute(text("ALTER TABLE runs ADD COLUMN failure_category TEXT"))
        conn.commit()
    return True


def seed_database(
    seed_file: Optional[Path] = None,
    session: Optional[Session] = None,
    overwrite: bool = False,
) -> int:
    """Load seed_papers.json, validate with Pydantic, and insert into the database.
    
    Returns the number of seeded/updated papers.
    """
    path = seed_file or SEED_PAPERS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_papers = json.load(f)

    db = session or get_session()
    should_close = session is None
    seeded_count = 0

    try:
        for item in raw_papers:
            # Validate with Pydantic
            validated = PaperCreate(**item)

            # Check if paper already exists
            existing = db.query(PaperORM).filter(PaperORM.paper_id == validated.paper_id).first()
            expected_json = json.dumps(validated.expected_claims, sort_keys=True)
            source_json = json.dumps(validated.source_table_or_section or {}, sort_keys=True)

            if existing:
                if overwrite:
                    existing.title = validated.title
                    existing.year = validated.year
                    existing.venue = validated.venue
                    existing.repo_url = validated.repo_url
                    existing.paper_url = validated.paper_url
                    existing.license = validated.license
                    existing.target_script = validated.target_script
                    existing.expected_claims = expected_json
                    existing.source_table_or_section = source_json
                    seeded_count += 1
            else:
                paper_orm = PaperORM(
                    paper_id=validated.paper_id,
                    title=validated.title,
                    year=validated.year,
                    venue=validated.venue,
                    repo_url=validated.repo_url,
                    paper_url=validated.paper_url,
                    license=validated.license,
                    target_script=validated.target_script,
                    expected_claims=expected_json,
                    source_table_or_section=source_json,
                )
                db.add(paper_orm)
                seeded_count += 1

        db.commit()
        return seeded_count
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


def get_all_papers(session: Optional[Session] = None) -> List[PaperORM]:
    """Retrieve all papers from the database."""
    db = session or get_session()
    should_close = session is None
    try:
        return db.query(PaperORM).order_by(PaperORM.paper_id).all()
    finally:
        if should_close:
            db.close()


def get_paper_by_id(paper_id: str, session: Optional[Session] = None) -> Optional[PaperORM]:
    """Retrieve a single paper by its ID."""
    db = session or get_session()
    should_close = session is None
    try:
        return db.query(PaperORM).filter(PaperORM.paper_id == paper_id).first()
    finally:
        if should_close:
            db.close()


def save_score(score_data: Dict[str, Any], session: Optional[Session] = None) -> ScoreORM:
    """Insert or update a reproducibility score for a paper."""
    db = session or get_session()
    should_close = session is None
    try:
        paper_id = score_data["paper_id"]
        existing = db.query(ScoreORM).filter(ScoreORM.paper_id == paper_id).first()
        if existing:
            for key, val in score_data.items():
                setattr(existing, key, val)
            target = existing
        else:
            target = ScoreORM(**score_data)
            db.add(target)
        db.commit()
        db.refresh(target)
        return target
    except Exception:
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Seeding database with target papers...")
    count = seed_database()
    print(f"Successfully initialized and seeded {count} papers into SQLite database.")
