import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from app.core.database import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    source_id = Column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    slide_number = Column(Integer, nullable=True, index=True)
    start_time_seconds = Column(Float, nullable=True)
    end_time_seconds = Column(Float, nullable=True)
    modality = Column(String(50), nullable=True, default="pdf")
    video_id = Column(String(50), nullable=True)
    canonical_url = Column(String(512), nullable=True)
    visual_description = Column(Text, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    source = relationship("Source", back_populates="chunks")
    course = relationship("Course", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_course_page", "course_id", "page_number"),
        Index("ix_chunks_course_slide", "course_id", "slide_number"),
        Index("ix_chunks_source_index", "source_id", "chunk_index"),
    )

    def __repr__(self) -> str:
        loc = f"slide={self.slide_number}" if self.slide_number is not None else f"page={self.page_number}"
        return f"<DocumentChunk(id='{self.id}', {loc}, chunk_index={self.chunk_index}, modality='{self.modality}')>"
