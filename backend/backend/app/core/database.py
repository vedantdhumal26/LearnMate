from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator
import os
from app.core.config import settings
from app.core.logging_config import logger

Base = declarative_base()

def get_engine():
    db_url = settings.DATABASE_URL
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif db_url and db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    try:
        if db_url.startswith("sqlite"):
            return create_engine(db_url, connect_args={"check_same_thread": False})
        
        # Test connecting to PostgreSQL
        eng = create_engine(db_url, pool_pre_ping=True)
        with eng.connect() as conn:
            pass
        return eng
    except Exception as e:
        logger.warning(
            f"Could not connect to database at {db_url}: {e}. "
            f"Falling back to local SQLite database (sqlite:///./learnsphere.db) for local execution."
        )
        sqlite_url = "sqlite:///./learnsphere.db"
        return create_engine(sqlite_url, connect_args={"check_same_thread": False})

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency for providing database sessions per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """Create all tables in the database and ensure new columns are added if upgrading schema."""
    import app.models  # noqa: F401 - ensure all models are registered on Base.metadata
    Base.metadata.create_all(bind=engine)

    # Lightweight column migration for existing tables when Alembic is not present
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(engine)
        if "document_chunks" in inspector.get_table_names():
            if engine.dialect.name == "sqlite":
                cols_info = inspector.get_columns("document_chunks")
                col_names = {c["name"] for c in cols_info}
                page_col = next((c for c in cols_info if c["name"] == "page_number"), None)
                possible_cols = [
                    "id", "source_id", "course_id", "content", "page_number",
                    "slide_number", "start_time_seconds", "end_time_seconds",
                    "modality", "visual_description", "chunk_index", "content_hash", "created_at"
                ]
                common_cols = ", ".join(c for c in possible_cols if c in col_names)
                if page_col and not page_col.get("nullable", True):
                    logger.info("Migrating SQLite document_chunks table to make page_number nullable...")
                    with engine.connect() as conn:
                        conn.execute(text("PRAGMA foreign_keys=off;"))
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS document_chunks_migrated (
                                id VARCHAR(36) NOT NULL PRIMARY KEY,
                                source_id VARCHAR(36) NOT NULL,
                                course_id VARCHAR(36) NOT NULL,
                                content TEXT NOT NULL,
                                page_number INTEGER,
                                slide_number INTEGER,
                                start_time_seconds FLOAT,
                                end_time_seconds FLOAT,
                                modality VARCHAR(50) DEFAULT 'pdf',
                                visual_description TEXT,
                                video_id VARCHAR(50),
                                canonical_url VARCHAR(512),
                                chunk_index INTEGER NOT NULL,
                                content_hash VARCHAR(64) NOT NULL,
                                created_at DATETIME NOT NULL,
                                FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE CASCADE,
                                FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE CASCADE
                            );
                        """))
                        conn.execute(text(f"""
                            INSERT INTO document_chunks_migrated ({common_cols})
                            SELECT {common_cols} FROM document_chunks;
                        """))
                        conn.execute(text("DROP TABLE document_chunks;"))
                        conn.execute(text("ALTER TABLE document_chunks_migrated RENAME TO document_chunks;"))
                        conn.execute(text("PRAGMA foreign_keys=on;"))
                        conn.commit()
                        logger.info("SQLite document_chunks migration complete: page_number is now nullable.")

            inspector = inspect(engine)
            existing_cols = {c["name"] for c in inspector.get_columns("document_chunks")}
            new_columns = [
                ("slide_number", "INTEGER"),
                ("start_time_seconds", "FLOAT"),
                ("end_time_seconds", "FLOAT"),
                ("modality", "VARCHAR(50) DEFAULT 'pdf'"),
                ("visual_description", "TEXT"),
                ("video_id", "VARCHAR(50)"),
                ("canonical_url", "VARCHAR(512)"),
            ]
            with engine.connect() as conn:
                for col_name, col_type in new_columns:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE document_chunks ADD COLUMN {col_name} {col_type}"))
                        logger.info(f"Added column '{col_name}' to 'document_chunks' table.")
                conn.commit()

        if "sources" in inspector.get_table_names():
            source_cols = {c["name"] for c in inspector.get_columns("sources")}
            new_source_cols = [
                ("video_id", "VARCHAR(50)"),
                ("canonical_url", "VARCHAR(512)"),
                ("duration_seconds", "FLOAT"),
                ("transcript_available", "BOOLEAN DEFAULT 1"),
                ("title", "VARCHAR(255)"),
            ]
            with engine.connect() as conn:
                for col_name, col_type in new_source_cols:
                    if col_name not in source_cols:
                        conn.execute(text(f"ALTER TABLE sources ADD COLUMN {col_name} {col_type}"))
                        logger.info(f"Added column '{col_name}' to 'sources' table.")
                conn.commit()

        # Phase 6A: Migration for courses.owner_id and evaluation_runs.user_id
        if "courses" in inspector.get_table_names():
            course_cols = {c["name"] for c in inspector.get_columns("courses")}
            if "owner_id" not in course_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN owner_id VARCHAR(36)"))
                    conn.commit()
                    logger.info("Added column 'owner_id' to 'courses' table.")

        if "evaluation_runs" in inspector.get_table_names():
            eval_cols = {c["name"] for c in inspector.get_columns("evaluation_runs")}
            if "user_id" not in eval_cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE evaluation_runs ADD COLUMN user_id VARCHAR(36)"))
                    conn.commit()
                    logger.info("Added column 'user_id' to 'evaluation_runs' table.")

        # Phase 6A: Documented Demo User Migration for backward compatibility
        from datetime import datetime, timezone
        from app.models.course import DEMO_USER_ID, DEMO_USER_EMAIL
        from app.utils.password import hash_password

        with engine.connect() as conn:
            existing_demo = conn.execute(
                text("SELECT id FROM users WHERE id = :id OR email = :email"),
                {"id": DEMO_USER_ID, "email": DEMO_USER_EMAIL}
            ).fetchone()

            now_utc = datetime.now(timezone.utc)
            if not existing_demo:
                conn.execute(text("""
                    INSERT INTO users (id, email, password_hash, display_name, created_at, updated_at)
                    VALUES (:id, :email, :password_hash, :display_name, :created_at, :updated_at)
                """), {
                    "id": DEMO_USER_ID,
                    "email": DEMO_USER_EMAIL,
                    "password_hash": hash_password("DemoPassword123!"),
                    "display_name": "Demo Learner",
                    "created_at": now_utc,
                    "updated_at": now_utc
                })
                logger.info(f"Created documented demo user for backward compatibility (ID: {DEMO_USER_ID}, Email: {DEMO_USER_EMAIL}).")

            # Assign orphan courses to the demo user so existing data is preserved
            result = conn.execute(
                text("UPDATE courses SET owner_id = :demo_id WHERE owner_id IS NULL"),
                {"demo_id": DEMO_USER_ID}
            )
            if result.rowcount and result.rowcount > 0:
                logger.info(f"Migrated {result.rowcount} orphan courses to default demo user ({DEMO_USER_ID}).")

            # Assign orphan evaluation runs to demo user
            eval_result = conn.execute(
                text("UPDATE evaluation_runs SET user_id = :demo_id WHERE user_id IS NULL"),
                {"demo_id": DEMO_USER_ID}
            )
            if eval_result.rowcount and eval_result.rowcount > 0:
                logger.info(f"Migrated {eval_result.rowcount} orphan evaluation runs to demo user ({DEMO_USER_ID}).")

            conn.commit()
    except Exception as e:
        logger.warning(f"Note on schema migration: {e}")

    logger.info("Database initialized successfully.")
