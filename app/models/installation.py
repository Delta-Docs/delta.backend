from sqlalchemy import Column, String, ForeignKey, DateTime, text, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Installation(Base):
    __tablename__ = "installations"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    installation_id = Column(BigInteger, unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    
    account_name = Column(String)
    account_type = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    
    user = relationship("User")

    __table_args__ = (
        Index('idx_installations_user', 'user_id'),
    )
