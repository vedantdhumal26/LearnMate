import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    dataset_size = Column(Integer, nullable=False, default=0)
    summary_metrics = Column(Text, nullable=True)  # JSON-encoded EvaluationMetricsSummary
    learner_simulation_results = Column(Text, nullable=True)  # JSON-encoded learner simulations
    error_message = Column(Text, nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="evaluations")
    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<EvaluationRun(id='{self.id}', name='{self.name}', status='{self.status}')>"


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    evaluation_run_id = Column(String(36), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id = Column(String(100), nullable=False)
    question = Column(Text, nullable=False)
    expected_grounded = Column(Boolean, nullable=False)
    actual_grounded = Column(Boolean, nullable=False)
    answer = Column(Text, nullable=False)
    retrieved_sources = Column(Text, nullable=True)  # JSON-encoded list of retrieved sources/citations
    citation_correct = Column(Boolean, nullable=False, default=False)
    faithfulness_score = Column(Float, nullable=True)
    relevance_score = Column(Float, nullable=True)
    context_precision = Column(Float, nullable=True)
    context_recall = Column(Float, nullable=True)
    passed = Column(Boolean, nullable=False, default=False)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    run = relationship("EvaluationRun", back_populates="results")

    def __repr__(self) -> str:
        return f"<EvaluationResult(id='{self.id}', test_case_id='{self.test_case_id}', passed={self.passed})>"
