from sqlalchemy.orm import Session
from typing import Optional, List
from app.models import TranslationJob

class JobRepository:
    @staticmethod
    def get_by_id(db: Session, job_id: str) -> Optional[TranslationJob]:
        return db.query(TranslationJob).filter(TranslationJob.id == job_id).first()

    @staticmethod
    def create(db: Session, job: TranslationJob) -> TranslationJob:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def update(db: Session, job: TranslationJob) -> TranslationJob:
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def update_status(
        db: Session,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        current_page: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Optional[TranslationJob]:
        job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
        if job:
            job.status = status
            if progress is not None:
                job.progress = progress
            if current_page is not None:
                job.current_page = current_page
            if error_message is not None:
                job.error_message = error_message
            db.commit()
            db.refresh(job)
        return job

    @staticmethod
    def update_summary(db: Session, job_id: str, running_summary: str) -> Optional[TranslationJob]:
        job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
        if job:
            job.running_summary = running_summary
            db.commit()
            db.refresh(job)
        return job
