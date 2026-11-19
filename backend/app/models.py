from sqlalchemy import Column, Integer, String, DateTime, JSON, Enum, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Operation(Base):
    __tablename__ = "operations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String, nullable=False)  # 'create_campaign', 'update_offers'
    status = Column(Enum("running", "succeeded", "failed", "unknown"), nullable=False, default="running")
    stage = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    campaign_id = Column(Integer, nullable=True)
    stream_id = Column(Integer, nullable=True)
    alias = Column(String, nullable=True)
    
    idempotency_key = Column(String, nullable=True, unique=True)
    request_hash = Column(String, nullable=True)
    
    error_code = Column(String, nullable=True)
    user_id = Column(String, nullable=True)

class OfferShareLock(Base):
    """Persist UI-side share locks; Keitaro remains the source of offer shares."""
    __tablename__ = "offer_share_locks"
    __table_args__ = (UniqueConstraint("campaign_id", "stream_id", "offer_id", name="uq_offer_share_lock"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    stream_id = Column(Integer, nullable=False, index=True)
    offer_id = Column(Integer, nullable=False)
    share_locked = Column(Boolean, nullable=False, default=False)

# Таблица для лога операций (согласно ТЗ)
# Данные кампаний/потоков в БД не дублируются (источник истины — Keitaro)
