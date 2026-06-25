from datetime import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class TranslationJob(Base):
    __tablename__ = "translation_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    output_pdf_path = Column(String(512), nullable=True)
    
    total_pages = Column(Integer, default=0)
    total_words = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    estimated_time = Column(Integer, default=0) # tính bằng giây
    
    status = Column(String(50), default="pending") # pending, scanning, scanned, translating, paused, completed, failed
    progress = Column(Float, default=0.0)
    current_page = Column(Integer, default=0)
    
    running_summary = Column(Text, default="")
    tone_style = Column(String(100), default="literary") # literary (văn học), detective (trinh thám), modern (hiện đại), classic (cổ điển), custom
    custom_instructions = Column(Text, default="") # các lưu ý khác từ người dùng
    translator_provider = Column(String(50), default="openrouter") # openrouter, google

    
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chunks = relationship("TranslationChunk", back_populates="job", cascade="all, delete-orphan")
    glossary = relationship("GlossaryItem", back_populates="job", cascade="all, delete-orphan")

class TranslationChunk(Base):
    __tablename__ = "translation_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    
    start_page = Column(Integer, nullable=False) # 1-indexed
    end_page = Column(Integer, nullable=False)
    
    original_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    
    # Tóm tắt bổ sung rút ra được sau chunk này
    summary_update = Column(Text, nullable=True)
    
    status = Column(String(50), default="pending") # pending, translating, completed, failed
    error_message = Column(Text, nullable=True)
    
    translated_at = Column(DateTime, nullable=True)

    # Relationships
    job = relationship("TranslationJob", back_populates="chunks")

class GlossaryItem(Base):
    __tablename__ = "glossary_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("translation_jobs.id"), nullable=False)
    
    term_en = Column(String(255), nullable=False)
    term_vi = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    is_auto_suggested = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    job = relationship("TranslationJob", back_populates="glossary")
