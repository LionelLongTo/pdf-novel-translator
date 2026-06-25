from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import os
import uuid
import logging
from typing import Optional

from app.database import get_db
from app.config import settings
from app.schemas import JobCreateResponse, JobStatusResponse, JobSettingsUpdate
from app.repositories import JobRepository
from app.services.translation_manager import TranslationManager

router = APIRouter(prefix="/translate", tags=["translate"])
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=JobCreateResponse)
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload file PDF tiếng Anh. 
    Hệ thống phân tích đếm số trang/từ, ước lượng chi phí/thời gian và khởi tạo Job ở trạng thái 'pending'.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ tải lên tệp tin định dạng PDF.")
        
    job_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix
    saved_filename = f"{job_id}{file_ext}"
    saved_path = settings.UPLOAD_DIR / saved_filename
    
    with open(saved_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    try:
        # Gọi TranslationManager để thiết lập Job & Chunks
        job = TranslationManager.create_job_from_upload(db, file.filename, str(saved_path))
        
        return JobCreateResponse(
            job_id=job.id,
            filename=job.filename,
            total_pages=job.total_pages,
            total_words=job.total_words,
            estimated_cost=job.estimated_cost,
            estimated_time=job.estimated_time,
            status=job.status
        )
    except Exception as e:
        if saved_path.exists():
            os.remove(saved_path)
        logger.error(f"Lỗi khi upload và khởi tạo Job: {e}")
        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo Job dịch: {str(e)}")


@router.post("/{job_id}/start", response_model=JobStatusResponse)
def start_translation(
    job_id: str,
    settings_update: Optional[JobSettingsUpdate] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Bắt đầu dịch hoặc tiếp tục dịch (Resume).
    """
    try:
        job = TranslationManager.start_translation_job(db, job_id, settings_update, background_tasks)
        
        has_pdf = False
        has_html = False
        if job.output_pdf_path:
            has_pdf = Path(job.output_pdf_path).exists()
            has_html = Path(job.output_pdf_path).with_suffix('.html').exists()
            
        response = JobStatusResponse.from_orm(job)
        response.has_pdf = has_pdf
        response.has_html = has_html
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Lỗi khởi động tiến trình dịch: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")


@router.post("/{job_id}/pause", response_model=JobStatusResponse)
def pause_translation(job_id: str, db: Session = Depends(get_db)):
    """
    Tạm dừng tiến trình dịch đang chạy.
    """
    try:
        job = TranslationManager.pause_translation_job(db, job_id)
        
        has_pdf = False
        has_html = False
        if job.output_pdf_path:
            has_pdf = Path(job.output_pdf_path).exists()
            has_html = Path(job.output_pdf_path).with_suffix('.html').exists()
            
        response = JobStatusResponse.from_orm(job)
        response.has_pdf = has_pdf
        response.has_html = has_html
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Lấy thông tin tiến độ và trạng thái hiện tại của Job.
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job.")
        
    has_pdf = False
    has_html = False
    if job.output_pdf_path:
        has_pdf = Path(job.output_pdf_path).exists()
        has_html = Path(job.output_pdf_path).with_suffix('.html').exists()
        
    response = JobStatusResponse.from_orm(job)
    response.has_pdf = has_pdf
    response.has_html = has_html
    return response


@router.get("/{job_id}/download/pdf")
def download_pdf(job_id: str, force: bool = False, db: Session = Depends(get_db)):
    """
    Tải file PDF kết quả sau khi dịch hoàn tất.
    Tự động biên dịch lại nếu file PDF vật lý chưa tồn tại (ví dụ do lỗi thư viện ở lần chạy trước) hoặc truyền force=True.
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job.")
        
    # Kiểm tra sự tồn tại của file PDF và đảm bảo dung lượng file lớn hơn 0 bytes (không bị lỗi 0kb)
    pdf_path_obj = Path(job.output_pdf_path) if job.output_pdf_path else None
    pdf_exists = pdf_path_obj and pdf_path_obj.exists() and pdf_path_obj.stat().st_size > 0
    
    # Cơ chế tự động hồi phục: Nếu dịch xong 100% nhưng file PDF bị thiếu, rỗng (0kb), hoặc nhận cờ force=True
    if (force or not pdf_exists or (pdf_path_obj and pdf_path_obj.exists() and pdf_path_obj.stat().st_size == 0)) and job.status == "completed":
        logger.info(f"Phát hiện file PDF bị thiếu, lỗi 0kb hoặc yêu cầu biên dịch lại (force={force}) cho Job {job_id}. Đang tiến hành biên dịch tự động lại...")
        try:
            # Xóa file cũ nếu có để tránh xung đột ghi đè
            if pdf_path_obj and pdf_path_obj.exists():
                try:
                    os.remove(pdf_path_obj)
                except:
                    pass
            # Biên dịch lại (sử dụng xhtml2pdf mới được cải đặt)
            TranslationManager.compile_final_document(db, job)
            db.commit()
            
            # Cập nhật lại trạng thái file
            pdf_path_obj = Path(job.output_pdf_path) if job.output_pdf_path else None
            pdf_exists = pdf_path_obj and pdf_path_obj.exists() and pdf_path_obj.stat().st_size > 0
        except Exception as e:
            logger.error(f"Lỗi tự động biên dịch lại PDF: {e}")
            
    if not pdf_exists:
        raise HTTPException(
            status_code=400, 
            detail="File PDF bản dịch chưa sẵn sàng hoặc gặp lỗi trong quá trình biên dịch."
        )
        
    return FileResponse(
        path=job.output_pdf_path,
        media_type="application/pdf",
        filename=f"dich_{job.filename}"
    )


@router.get("/{job_id}/download/html")
def download_html(job_id: str, db: Session = Depends(get_db)):
    """
    Tải file HTML kết quả dịch làm phương án dự phòng.
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job.")
        
    html_path = None
    if job.output_pdf_path:
        html_path = Path(job.output_pdf_path).with_suffix('.html')
    else:
        html_path = settings.OUTPUT_DIR / f"translated_{job.id}.html"
        
    if not html_path.exists():
        raise HTTPException(status_code=400, detail="File HTML bản dịch chưa được tạo.")
        
    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename=f"dich_{Path(job.filename).stem}.html"
    )


@router.post("/{job_id}/reset", response_model=JobStatusResponse)
def reset_job_translation(
    job_id: str,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Reset trạng thái của Job và các Chunk để dịch lại.
    - Nếu truyền start_page và end_page: Chỉ reset các chunk chứa các trang nằm trong khoảng đó.
    - Nếu không truyền: Reset toàn bộ các chunk của Job.
    Sau khi reset, bạn có thể thay đổi glossary/xưng hô mới rồi gọi API start để dịch lại.
    """
    job = JobRepository.get_by_id(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy Job.")
        
    from app.models import TranslationChunk
    query = db.query(TranslationChunk).filter(TranslationChunk.job_id == job_id)
    
    if start_page is not None and end_page is not None:
        # Reset các chunk giao nhau hoặc nằm trong khoảng trang yêu cầu
        # Chúc mừng: bất kỳ chunk nào có start_page nằm trong [start_page, end_page] hoặc end_page nằm trong [start_page, end_page]
        query = query.filter(
            (TranslationChunk.start_page >= start_page) & (TranslationChunk.start_page <= end_page) |
            (TranslationChunk.end_page >= start_page) & (TranslationChunk.end_page <= end_page)
        )
        
    # Reset status và bản dịch của các chunk được chọn
    query.update({
        "status": "pending",
        "translated_text": None,
        "summary_update": None,
        "error_message": None,
        "translated_at": None
    }, synchronize_session=False)
    
    # Tính toán lại tiến độ Job dựa trên số lượng chunk hoàn thành còn lại
    completed_chunks = db.query(TranslationChunk).filter(
        TranslationChunk.job_id == job_id,
        TranslationChunk.status == "completed"
    ).count()
    total_chunks = db.query(TranslationChunk).filter(TranslationChunk.job_id == job_id).count()
    
    progress = round((completed_chunks / total_chunks) * 100, 2) if total_chunks > 0 else 0.0
    
    job.status = "paused"
    job.progress = progress
    job.error_message = None
    db.commit()
    db.refresh(job)
    
    has_pdf = False
    has_html = False
    if job.output_pdf_path:
        has_pdf = Path(job.output_pdf_path).exists()
        has_html = Path(job.output_pdf_path).with_suffix('.html').exists()
        
    response = JobStatusResponse.from_orm(job)
    response.has_pdf = has_pdf
    response.has_html = has_html
    return response
