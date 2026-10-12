import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    course_id = Column(String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False, default="application/pdf")
    file_path = Column(String(1024), nullable=False)
    source_type = Column(String(50), nullable=False, default="pdf")
    processing_status = Column(String(50), nullable=False, default="pending")  # pending, processing, completed, failed
    video_id = Column(String(50), nullable=True)
    canonical_url = Column(String(512), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    transcript_available = Column(Boolean, nullable=True, default=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    course = relationship("Course", back_populates="sources")
    chunks = relationship("DocumentChunk", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Source(id='{self.id}', file_name='{self.file_name}', status='{self.processing_status}')>"
