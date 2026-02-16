from sqlalchemy import Column, String, Boolean, Float, DateTime, ForeignKey, text, BigInteger, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    installation_id = Column(BigInteger, ForeignKey("installations.installation_id", ondelete="CASCADE"))
    repo_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)
    avatar_url = Column(String)
    
    docs_root_path = Column(String, default='/docs')
    target_branch = Column(String, default='main')
    drift_sensitivity = Column(Float, default=0.5)
    style_preference = Column(String, default='professional')
    file_ignore_patterns = Column(ARRAY(String))
    
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    
    installation = relationship("Installation", primaryjoin="Repository.installation_id==Installation.installation_id", foreign_keys=[installation_id])

    __table_args__ = (
        UniqueConstraint('installation_id', 'repo_name'),
    )

class DocCoverageMap(Base):
    __tablename__ = "doc_coverage_map"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    repo_id = Column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    
    code_path = Column(String, nullable=False)
    doc_file_path = Column(String)
    
    last_verified_at = Column(DateTime(timezone=True), server_default=text("now()"))
    
    repository = relationship("Repository")

    __table_args__ = (
        UniqueConstraint('repo_id', 'code_path', 'doc_file_path'),
        Index('idx_coverage_repo', 'repo_id'),
    )
