from sqlalchemy.orm import Session
from app.repositories import JobRepository, GlossaryRepository
from app.services.pdf_service import PDFService
from app.services.translator_service import TranslatorService
from app.models import GlossaryItem
from typing import List

class GlossaryManager:
    @staticmethod
    def scan_and_suggest(db: Session, job_id: str) -> List[GlossaryItem]:
        """
        Quét tối đa 10 trang đầu của cuốn sách để phân tích cốt truyện sơ bộ và trả về danh sách nhân vật/từ khóa gợi ý.
        """
        job = JobRepository.get_by_id(db, job_id)
        if not job:
            raise ValueError("Không tìm thấy Job dịch thuật.")
            
        # Xác định số trang quét
        scan_end_page = min(10, job.total_pages)
        if scan_end_page == 0:
            raise ValueError("Tài liệu không có nội dung trang.")
            
        # Cập nhật trạng thái sang đang quét
        JobRepository.update_status(db, job_id, status="scanning")
        
        try:
            # 1. Trích xuất văn bản đầu sách
            text = PDFService.extract_text_range(job.file_path, 1, scan_end_page)
            
            # 2. Gọi API để lấy gợi ý thuật ngữ dưới dạng JSON
            translator = TranslatorService()
            suggestions_raw = translator.scan_glossary_suggestions(text)
            
            # 3. Dọn dẹp các gợi ý tự động cũ nếu có
            GlossaryRepository.clear_by_job(db, job_id, is_auto_suggested_only=True)
            
            # 4. Thêm các bản ghi gợi ý mới vào Database
            db_items = []
            for sug in suggestions_raw:
                db_item = GlossaryItem(
                    term_en=sug.get("term_en", "").strip(),
                    term_vi=sug.get("term_vi", "").strip(),
                    description=sug.get("description", ""),
                    is_auto_suggested=True
                )
                if db_item.term_en and db_item.term_vi:
                    db_items.append(db_item)
                    
            GlossaryRepository.bulk_create(db, job_id, db_items, commit=True)
            
            # Cập nhật trạng thái hoàn thành quét
            JobRepository.update_status(db, job_id, status="scanned")
            
            return db_items
            
        except Exception as e:
            JobRepository.update_status(db, job_id, status="failed", error_message=f"Lỗi quét thuật ngữ: {str(e)}")
            raise e
