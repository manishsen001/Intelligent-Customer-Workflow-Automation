"""Database service layer for Customer Workflow Automation System."""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings
from src.db.models import Base


class DatabaseService:
    """Database service with connection management."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            echo=False,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )
    
    def init_db(self) -> None:
        """Initialize database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_db(self) -> None:
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get database session context manager."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """Get a new database session (caller must close)."""
        return self.SessionLocal()
    
    def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            with self.session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


# Global database service instance
db_service = DatabaseService()


def get_db() -> Generator[Session, None, None]:
    """FastAPI-style dependency for database session."""
    with db_service.session() as session:
        yield session


def init_database() -> None:
    """Initialize database on application startup."""
    db_service.init_db()


def reset_database() -> None:
    """Reset database (for testing)."""
    db_service.drop_db()
    db_service.init_db()