from sqlalchemy import Column, String, Integer, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    full_name = Column(String)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String)
    
    github_user_id = Column(Integer, unique=True)
    avatar_url = Column(String)
    
    current_refresh_token_hash = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))
