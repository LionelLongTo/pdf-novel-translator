from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from datetime import datetime
from pathlib import Path
import logging
import os

from app.config import settings
from app.models import TranslationJob, TranslationChunk, GlossaryItem
from app.repositories import JobRepository, ChunkRepository, GlossaryRepository
from app.services.pdf_service import PDFService
from app.services.translator_service import TranslatorService
from app.services.html_generator_service import HTMLGeneratorService
from app.database import SessionLocal

logger = logging.getLogger(__name__)

class TranslationManager:
    @staticmethod
    def create_job_from_upload(db: Session, filename: str, file_path: str) -> TranslationJob:
        """
        Tạo mới một Job dịch thuật từ tệp tin PDF tải lên.
        """
        # Phân tích PDF lấy thông tin số trang, số từ, dự chi chi phí/thời gian
        info = PDFService.get_pdf_info(file_path)
        
        # Khởi tạo bản ghi Job qua Repository
        job = TranslationJob(
            filename=filename,
            file_path=file_path,
            total_pages=info["total_pages"],
            total_words=info["total_words"],
            estimated_cost=info["estimated_cost"],
            estimated_time=info["estimated_time"],
            status="pending",
            progress=0.0
        )
        JobRepository.create(db, job)
        
        # Trích xuất toàn bộ hình ảnh minh họa từ PDF gốc
        try:
            img_count = PDFService.extract_images(file_path, job.id)
            logger.info(f"Đã trích xuất {img_count} ảnh minh họa từ PDF gốc cho Job {job.id}")
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất hình ảnh minh họa từ PDF gốc: {e}")
        
        # Phân chia và tạo sẵn các Chunks dịch (mặc định mỗi chunk 8 trang)
        chunks = PDFService.generate_chunks(file_path, chunk_size=8)
        for c in chunks:
            # Trích xuất text tiếng Anh trước để lưu vào original_text (tránh lỗi NotNull và tối ưu tiến độ)
            en_text = PDFService.extract_text_range(file_path, c["start_page"], c["end_page"])
            chunk = TranslationChunk(
                job_id=job.id,
                start_page=c["start_page"],
                end_page=c["end_page"],
                original_text=en_text,
                status="pending"
            )
            ChunkRepository.create(db, chunk)
            
        return job

    @classmethod
    def start_translation_job(
        cls,
        db: Session,
        job_id: str,
        settings_update,
        background_tasks: BackgroundTasks
    ) -> TranslationJob:
        """
        Thiết lập cấu hình văn phong/xưng hô và kích hoạt tiến trình dịch nền.
        """
        job = JobRepository.get_by_id(db, job_id)
        if not job:
            raise ValueError("Không tìm thấy Job dịch thuật.")
            
        # Kiểm tra xem thực tế tất cả các chunk đã dịch xong chưa (đề phòng lỗi kẹt trạng thái làm Job bị đánh dấu completed ảo)
        from app.models import TranslationChunk
        total_chunks = db.query(TranslationChunk).filter(TranslationChunk.job_id == job_id).count()
        completed_chunks = db.query(TranslationChunk).filter(
            TranslationChunk.job_id == job_id,
            TranslationChunk.status == "completed"
        ).count()
        
        # Chỉ chặn khởi chạy khi tất cả các chunk thực sự đã được hoàn thành
        if total_chunks > 0 and total_chunks == completed_chunks:
            raise ValueError("Tài liệu đã được dịch hoàn thành.")
            
        # Áp dụng các thay đổi thiết lập nếu có
        if settings_update:
            if settings_update.tone_style:
                job.tone_style = settings_update.tone_style
            if settings_update.custom_instructions:
                job.custom_instructions = settings_update.custom_instructions
                
            # Cập nhật bảng từ vựng tùy chỉnh (nếu được truyền lên)
            if settings_update.glossary is not None:
                # Xóa glossary cũ của Job
                GlossaryRepository.clear_by_job(db, job_id, is_auto_suggested_only=False)
                
                # Thêm danh sách glossary mới
                db_items = []
                for item in settings_update.glossary:
                    db_item = GlossaryItem(
                        term_en=item.term_en.strip(),
                        term_vi=item.term_vi.strip(),
                        description=item.description,
                        is_auto_suggested=False
                    )
                    db_items.append(db_item)
                GlossaryRepository.bulk_create(db, job_id, db_items, commit=False)
                
        # Chuyển trạng thái các chunk bị kẹt ở 'translating' về 'pending' để dịch lại khi resume
        from app.models import TranslationChunk
        db.query(TranslationChunk).filter(
            TranslationChunk.job_id == job_id,
            TranslationChunk.status == "translating"
        ).update({"status": "pending"})

        # Chuyển trạng thái Job sang đang dịch và kích hoạt Background Task
        JobRepository.update_status(db, job_id, status="translating", error_message="")
        db.commit()
        
        # Đăng ký luồng dịch chạy nền
        background_tasks.add_task(cls.execute_translation_loop, job_id)
        
        return job

    @staticmethod
    def pause_translation_job(db: Session, job_id: str) -> TranslationJob:
        """
        Tạm dừng tiến trình dịch.
        """
        job = JobRepository.get_by_id(db, job_id)
        if not job:
            raise ValueError("Không tìm thấy Job dịch thuật.")
            
        if job.status == "translating":
            JobRepository.update_status(db, job_id, status="paused")
            
        return job

    @classmethod
    def execute_translation_loop(cls, job_id: str):
        """
        Vòng lặp dịch nền cuốn chiếu.
        Mở và đóng DB session độc lập cho từng chunk để tránh giữ kết nối nhàn rỗi (idle timeout) khi gọi API LLM.
        """
        translator = TranslatorService()
        
        # 1. Lấy cấu hình glossary và giải phóng các chunk bị kẹt (đóng DB ngay sau đó)
        db: Session = SessionLocal()
        try:
            job = JobRepository.get_by_id(db, job_id)
            if not job or job.status != "translating":
                logger.info(f"Không thể chạy dịch Job {job_id} do trạng thái không phải translating.")
                return
            
            # Giải phóng tất cả các chunk bị kẹt ở trạng thái translating về pending để dịch lại
            from app.models import TranslationChunk
            db.query(TranslationChunk).filter(
                TranslationChunk.job_id == job_id,
                TranslationChunk.status == "translating"
            ).update({"status": "pending"})
            db.commit()
            
            glossary_items = GlossaryRepository.get_by_job(db, job_id)
            glossary_list = [
                {"term_en": g.term_en, "term_vi": g.term_vi, "description": g.description}
                for g in glossary_items
            ]
        finally:
            db.close()
            
        while True:
            # 2. Mở DB session mới để kiểm tra trạng thái và tìm chunk cần dịch tiếp theo
            db = SessionLocal()
            try:
                job = JobRepository.get_by_id(db, job_id)
                if not job or job.status == "paused" or job.status == "failed":
                    logger.info(f"Dừng vòng lặp dịch Job {job_id} do trạng thái: {job.status if job else 'None'}")
                    break
                    
                chunk = ChunkRepository.get_next_pending_chunk(db, job_id)
                if not chunk:
                    # Đã dịch xong hết toàn bộ các chunk
                    logger.info(f"Hoàn thành dịch tất cả các chunk cho Job {job_id}. Đang xuất PDF...")
                    cls.compile_final_document(db, job)
                    break
                
                # Lưu các thông tin cần thiết vào biến cục bộ
                chunk_id = chunk.id
                start_page = chunk.start_page
                end_page = chunk.end_page
                file_path = job.file_path
                running_summary = job.running_summary
                tone_style = job.tone_style
                custom_instructions = job.custom_instructions
                
                # Đảm bảo có text tiếng Anh
                en_text = chunk.original_text or ""
                if not en_text:
                    en_text = PDFService.extract_text_range(file_path, start_page, end_page)
                    chunk.original_text = en_text
                
                # Cập nhật trạng thái chunk và job trước khi giải phóng kết nối DB
                ChunkRepository.update_status(db, chunk_id, status="translating")
                JobRepository.update_status(db, job_id, status="translating", current_page=start_page)
                db.commit()
                
            except Exception as e:
                logger.error(f"Lỗi truy cập DB ở đầu vòng lặp: {e}")
                break
            finally:
                db.close() # ĐÓNG KẾT NỐI DB TRƯỚC KHI GỌI API DỊCH để tránh hết hạn kết nối (timeout)
                
            # 3. Gọi API dịch ngoài DB session (chờ 10-30s mà không tốn kết nối DB)
            max_retries = 3
            retry_count = 0
            translation_success = False
            last_error = None
            vi_text = ""
            summary_updates = ""
            
            while retry_count < max_retries and not translation_success:
                try:
                    vi_text, summary_updates = translator.translate_chunk(
                        text=en_text,
                        running_summary=running_summary,
                        glossary_list=glossary_list,
                        tone_style=tone_style,
                        custom_instructions=custom_instructions
                    )
                    translation_success = True
                except Exception as e:
                    retry_count += 1
                    last_error = e
                    logger.warning(
                        f"Lỗi dịch chunk {start_page}-{end_page} lần {retry_count}/{max_retries}: {e}"
                    )
                    if retry_count < max_retries:
                        import time
                        wait_time = retry_count * 3  # Chờ tăng dần: 3s, 6s
                        logger.info(f"Đang đợi {wait_time} giây trước khi thử lại...")
                        time.sleep(wait_time)
            
            # 4. Mở DB session mới để lưu kết quả hoặc ghi nhận thất bại
            db = SessionLocal()
            try:
                job = JobRepository.get_by_id(db, job_id)
                chunk = ChunkRepository.get_by_id(db, chunk_id)
                
                if not job or not chunk:
                    logger.error(f"Không tìm thấy Job {job_id} hoặc Chunk {chunk_id} để lưu kết quả.")
                    break
                    
                if translation_success:
                    # Lưu kết quả dịch thành công
                    ChunkRepository.update_status(
                        db, chunk_id,
                        status="completed",
                        translated_text=vi_text,
                        summary_update=summary_updates
                    )
                    
                    # Cập nhật tóm tắt cốt truyện cuộn chiếu
                    new_summary = job.running_summary
                    if summary_updates:
                        if new_summary:
                            new_summary += f"\n- {summary_updates}"
                        else:
                            new_summary = f"- {summary_updates}"
                    JobRepository.update_summary(db, job_id, new_summary)
                    
                    # Cập nhật tiến độ % Job
                    completed = ChunkRepository.count_completed_chunks(db, job_id)
                    total = ChunkRepository.count_total_chunks(db, job_id)
                    progress = round((completed / total) * 100, 2)
                    JobRepository.update_status(db, job_id, status="translating", progress=progress)
                    
                    logger.info(f"Lưu thành công kết quả dịch trang {start_page}-{end_page} cho Job {job_id}.")
                else:
                    # Ghi nhận lỗi sau 3 lần thử thất bại
                    error_msg = f"Lỗi dịch tại trang {start_page}-{end_page} sau 3 lần thử: {str(last_error)}"
                    ChunkRepository.update_status(db, chunk_id, status="failed", error_message=str(last_error))
                    JobRepository.update_status(db, job_id, status="failed", error_message=error_msg)
                    logger.error(f"Ghi nhận thất bại dịch chunk {start_page}-{end_page}: {last_error}")
                    break
                    
            except Exception as e:
                logger.error(f"Lỗi khi lưu kết quả vào DB: {e}")
                break
            finally:
                db.close()

    @staticmethod
    def compile_final_document(db: Session, job: TranslationJob):
        """
        Tổng hợp tất cả các đoạn dịch đã lưu trong DB và xuất ra file HTML + PDF cuối cùng.
        """
        try:
            chunks = ChunkRepository.get_all_by_job(db, job.id)
            full_translation_parts = [c.translated_text for c in chunks if c.translated_text]
            full_translation = "\n\n".join(full_translation_parts)
            
            # Chuẩn hóa tên tiêu đề
            filename_no_ext = Path(job.filename).stem
            title = filename_no_ext.replace("_", " ").replace("-", " ").title()
            author = "Tác giả gốc"
            
            # Đảm bảo hình ảnh được trích xuất (tự hồi phục cho các Job cũ hoặc khi tải lại)
            image_dir = Path(__file__).resolve().parent.parent / "resources" / "images" / job.id
            if not image_dir.exists() or not any(image_dir.iterdir()):
                try:
                    logger.info(f"Đang kiểm tra và trích xuất ảnh minh họa cho Job {job.id}...")
                    PDFService.extract_images(job.file_path, job.id)
                except Exception as img_err:
                    logger.warning(f"Lỗi khi trích xuất hình ảnh bổ sung: {img_err}")
            
            # Sinh mã HTML (truyền job_id để chèn hình ảnh tương ứng với từng trang)
            html_content = HTMLGeneratorService.generate_html(title, author, full_translation, job_id=job.id)
            
            # Đường dẫn lưu file
            pdf_filename = f"translated_{job.id}.pdf"
            output_pdf_path = settings.OUTPUT_DIR / pdf_filename
            
            # Compile sang PDF
            success = HTMLGeneratorService.compile_pdf(html_content, str(output_pdf_path))
            
            # Cập nhật kết quả vào Job
            job.output_pdf_path = str(output_pdf_path)
            job.status = "completed"
            job.progress = 100.0
            
            if not success:
                job.error_message = "Dịch hoàn tất nhưng biên dịch PDF gặp lỗi (Đã lưu bản dự phòng HTML)."
                
            db.commit()
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp PDF cuối cùng cho Job {job.id}: {e}")
            JobRepository.update_status(db, job.id, status="failed", error_message=f"Lỗi biên dịch tài liệu: {str(e)}")
