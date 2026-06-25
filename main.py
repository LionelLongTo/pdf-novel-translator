import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.database import engine, Base
from app.config import settings
from app.handlers import translate_router, glossary_router

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Tạo bảng cơ sở dữ liệu SQLite nếu chưa tồn tại
try:
    logger.info("Đang khởi tạo các bảng cơ sở dữ liệu...")
    Base.metadata.create_all(bind=engine)
    
    # Tự động nâng cấp schema cho các cơ sở dữ liệu cũ (SQLite / PostgreSQL)
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("translation_jobs")]
        if "translator_provider" not in columns:
            logger.info("Đang thực hiện nâng cấp database: thêm cột translator_provider vào bảng translation_jobs...")
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE translation_jobs ADD COLUMN translator_provider VARCHAR(50) DEFAULT 'openrouter';"))
                conn.commit()
            logger.info("Nâng cấp database thành công.")
    except Exception as e:
        logger.warning(f"Lỗi khi kiểm tra/nâng cấp schema database: {e}")

    logger.info("Khởi tạo cơ sở dữ liệu thành công.")
except Exception as e:
    logger.error(f"Lỗi khi khởi tạo cơ sở dữ liệu: {e}")

app = FastAPI(
    title="AI Book Translator API",
    description="Backend FastAPI dịch thuật sách PDF tiếng Anh sang tiếng Việt sử dụng AI (Gemini qua OpenRouter) với ngữ cảnh cuộn chiếu.",
    version="1.0.0"
)

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong thực tế nên giới hạn domain FE
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router
app.include_router(translate_router, prefix="/api")
app.include_router(glossary_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "message": "AI Book Translator API is running smoothly.",
        "docs": "/docs",
        "supported_formats": ["PDF"]
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
