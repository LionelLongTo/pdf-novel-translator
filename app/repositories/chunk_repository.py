from sqlalchemy.orm import Session
from typing import Optional, List
from app.models import TranslationChunk

class ChunkRepository:
    @staticmethod
    def get_by_id(db: Session, chunk_id: int) -> Optional[TranslationChunk]:
        return db.query(TranslationChunk).filter(TranslationChunk.id == chunk_id).first()

    @staticmethod
    def get_all_by_job(db: Session, job_id: str) -> List[TranslationChunk]:
        return db.query(TranslationChunk).filter(
            TranslationChunk.job_id == job_id
        ).order_by(TranslationChunk.start_page.asc()).all()

    @staticmethod
    def get_next_pending_chunk(db: Session, job_id: str) -> Optional[TranslationChunk]:
        """
        Tìm chunk chưa dịch (pending hoặc failed) đầu tiên của một Job.
        """
        return db.query(TranslationChunk).filter(
            TranslationChunk.job_id == job_id,
            TranslationChunk.status.in_(["pending", "failed"])
        ).order_by(TranslationChunk.start_page.asc()).first()

    @staticmethod
    def create(db: Session, chunk: TranslationChunk) -> TranslationChunk:
        db.add(chunk)
        db.commit()
        db.refresh(chunk)
        return chunk

    @staticmethod
    def update_status(
        db: Session,
        chunk_id: int,
        status: str,
        original_text: Optional[str] = None,
        translated_text: Optional[str] = None,
        summary_update: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[TranslationChunk]:
        chunk = db.query(TranslationChunk).filter(TranslationChunk.id == chunk_id).first()
        if chunk:
            chunk.status = status
            if original_text is not None:
                chunk.original_text = original_text
            if translated_text is not None:
                chunk.translated_text = translated_text
            if summary_update is not None:
                chunk.summary_update = summary_update
            if error_message is not None:
                chunk.error_message = error_message
            db.commit()
            db.refresh(chunk)
        return chunk

    @staticmethod
    def count_completed_chunks(db: Session, job_id: str) -> int:
        return db.query(TranslationChunk).filter(
            TranslationChunk.job_id == job_id,
            TranslationChunk.status == "completed"
        ).count()

    @staticmethod
    def count_total_chunks(db: Session, job_id: str) -> int:
        return db.query(TranslationChunk).filter(
            TranslationChunk.job_id == job_id
        ).count()
