from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import GlossaryItemBase, GlossaryItemResponse, AutoGlossaryResponse
from app.repositories import GlossaryRepository, JobRepository
from app.models import GlossaryItem
from app.services.glossary_manager import GlossaryManager

router = APIRouter(prefix="/jobs", tags=["glossary"])

@router.get("/{job_id}/glossary", response_model=List[GlossaryItemResponse])
def get_glossary(job_id: str, db: Session = Depends(get_db)):
    """
    Lấy danh sách các thuật ngữ/tên nhân vật đã cấu hình cho Job.
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job dịch thuật.")
        
    return GlossaryRepository.get_by_job(db, job_id)

@router.post("/{job_id}/glossary", response_model=List[GlossaryItemResponse])
def save_glossary(job_id: str, items: List[GlossaryItemBase], db: Session = Depends(get_db)):
    """
    Lưu danh sách thuật ngữ tùy chỉnh do người dùng tự nhập hoặc chỉnh sửa.
    Sẽ thay thế toàn bộ danh sách cũ của Job đó.
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job dịch thuật.")
        
    # Xóa glossary cũ
    GlossaryRepository.clear_by_job(db, job_id, is_auto_suggested_only=False)
    
    # Tạo danh sách glossary mới
    db_items = []
    for item in items:
        db_item = GlossaryItem(
            term_en=item.term_en.strip(),
            term_vi=item.term_vi.strip(),
            description=item.description,
            is_auto_suggested=False
        )
        db_items.append(db_item)
        
    GlossaryRepository.bulk_create(db, job_id, db_items, commit=True)
    return db_items

@router.post("/{job_id}/glossary/scan", response_model=AutoGlossaryResponse)
def scan_glossary(job_id: str, db: Session = Depends(get_db)):
    """
    Quét 10 trang đầu của sách PDF để tự động nhận diện và đề xuất bảng thuật ngữ/nhân vật.
    """
    try:
        suggestions = GlossaryManager.scan_and_suggest(db, job_id)
        
        response_suggestions = [
            GlossaryItemBase(
                term_en=item.term_en,
                term_vi=item.term_vi,
                description=item.description
            ) for item in suggestions
        ]
        
        return AutoGlossaryResponse(job_id=job_id, suggestions=response_suggestions)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi phân tích sách: {str(e)}")
