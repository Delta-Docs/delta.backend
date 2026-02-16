from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, text, BigInteger, CheckConstraint, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class DriftEvent(Base):
    __tablename__ = "drift_events"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    
    pr_number = Column(Integer, nullable=False)
    base_branch = Column(String, nullable=False)
    head_branch = Column(String, nullable=False)
    base_sha = Column(String, nullable=False)
    head_sha = Column(String, nullable=False)
    check_run_id = Column(BigInteger)
    
    processing_phase = Column(String, default='queued')
    drift_result = Column(String, default='pending')
    
    overall_drift_score = Column(Float)
    summary = Column(String)
    agent_logs = Column(JSONB)
    error_message = Column(String)
    
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    repository = relationship("Repository")

    __table_args__ = (
        CheckConstraint("processing_phase IN ('queued', 'scouting', 'analyzing', 'generating', 'verifying', 'completed', 'failed')", name="check_processing_phase"),
        CheckConstraint("drift_result IN ('pending', 'clean', 'drift_detected', 'missing_docs', 'error')", name="check_drift_result"),
        Index('idx_drift_active_runs', 'repo_id', postgresql_where=text("processing_phase NOT IN ('completed', 'failed')")),
    )

class DriftFinding(Base):
    __tablename__ = "drift_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    drift_event_id = Column(UUID(as_uuid=True), ForeignKey("drift_events.id", ondelete="CASCADE"))
    
    code_path = Column(String, nullable=False)
    doc_file_path = Column(String)
    change_type = Column(String)
    drift_type = Column(String)
    
    drift_score = Column(Float)
    explanation = Column(String)
    confidence = Column(Float)
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    
    drift_event = relationship("DriftEvent")

    __table_args__ = (
        CheckConstraint("change_type IN ('added', 'modified', 'deleted')", name="check_finding_change_type"),
        CheckConstraint("drift_type IN ('outdated_docs', 'missing_docs', 'ambiguous_docs')", name="check_start_drift_type"),
    )

class CodeChange(Base):
    __tablename__ = "code_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    drift_event_id = Column(UUID(as_uuid=True), ForeignKey("drift_events.id", ondelete="CASCADE"))
    
    file_path = Column(String, nullable=False)
    change_type = Column(String)
    
    is_code = Column(Boolean, default=True)

    drift_event = relationship("DriftEvent")

    __table_args__ = (
        CheckConstraint("change_type IN ('added', 'modified', 'deleted')", name="check_code_change_type"),
    )
