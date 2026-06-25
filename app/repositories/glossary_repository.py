from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import GlossaryItem

class GlossaryRepository:
    @staticmethod
    def get_by_job(db: Session, job_id: str) -> List[GlossaryItem]:
        return db.query(GlossaryItem).filter(GlossaryItem.job_id == job_id).all()

    @staticmethod
    def clear_by_job(db: Session, job_id: str, is_auto_suggested_only: bool = False) -> None:
        """
        Xóa danh sách glossary của job.
        Nếu is_auto_suggested_only=True, chỉ xóa các từ tự động quét được.
        """
        query = db.query(GlossaryItem).filter(GlossaryItem.job_id == job_id)
        if is_auto_suggested_only:
            query = query.filter(GlossaryItem.is_auto_suggested == True)
        query.delete()
        db.commit()

    @staticmethod
    def bulk_create(db: Session, job_id: str, items: List[GlossaryItem], commit: bool = True) -> List[GlossaryItem]:
        for item in items:
            item.job_id = job_id
            db.add(item)
        if commit:
            db.commit()
            for item in items:
                db.refresh(item)
        return items

    @staticmethod
    def delete(db: Session, item_id: int) -> bool:
        item = db.query(GlossaryItem).filter(GlossaryItem.id == item_id).first()
        if item:
            db.delete(item)
            db.commit()
            return True
        return False
