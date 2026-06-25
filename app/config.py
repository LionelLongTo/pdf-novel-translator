import os
from pathlib import Path
from dotenv import load_dotenv

# Tải file .env từ thư mục gốc của dự án
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    OPENROUTER_ALLOW_FALLBACKS: bool = os.getenv("OPENROUTER_ALLOW_FALLBACKS", "False").lower() in ("true", "1", "yes")
    
    
    TRANSLATOR_PROVIDER: str = os.getenv("TRANSLATOR_PROVIDER", "openrouter")
    GEMINI_API_KEYS: str = os.getenv("GEMINI_API_KEYS", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./pdf_translator.db")
    
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(BASE_DIR / "outputs")))
    
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

settings = Settings()

# Đảm bảo các thư mục upload/output được tạo
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
