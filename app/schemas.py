from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class GlossaryItemBase(BaseModel):
    term_en: str = Field(..., description="Từ/tên riêng tiếng Anh")
    term_vi: str = Field(..., description="Bản dịch tiếng Việt đề xuất")
    description: Optional[str] = Field(None, description="Mô tả hoặc lưu ý xưng hô")

class GlossaryItemCreate(GlossaryItemBase):
    pass

class GlossaryItemResponse(GlossaryItemBase):
    id: int
    job_id: str
    is_auto_suggested: bool
    
    class Config:
        from_attributes = True

class JobSettingsUpdate(BaseModel):
    tone_style: Optional[str] = Field("literary", description="Văn phong dịch: literary, detective, modern, classic")
    custom_instructions: Optional[str] = Field("", description="Hướng dẫn xưng hô bổ sung từ người dùng")
    translator_provider: Optional[str] = Field("openrouter", description="Nhà cung cấp dịch: openrouter, google")
    glossary: Optional[List[GlossaryItemBase]] = Field(None, description="Danh sách từ vựng tùy chỉnh")

class JobCreateResponse(BaseModel):
    job_id: str
    filename: str
    total_pages: int
    total_words: int
    estimated_cost: float
    estimated_time: int
    status: str

class JobStatusResponse(BaseModel):
    id: str
    filename: str
    status: str
    progress: float
    current_page: int
    total_pages: int
    total_words: int
    estimated_cost: float
    estimated_time: int
    tone_style: str
    custom_instructions: str
    translator_provider: str
    running_summary: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    has_pdf: bool = False
    has_html: bool = False

    class Config:
        from_attributes = True

class AutoGlossaryResponse(BaseModel):
    job_id: str
    suggestions: List[GlossaryItemBase]
