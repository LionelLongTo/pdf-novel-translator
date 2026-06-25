-- 1. Tạo bảng translation_jobs (Quản lý các Job dịch thuật)
CREATE TABLE IF NOT EXISTS translation_jobs (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    output_pdf_path VARCHAR(512),
    total_pages INTEGER DEFAULT 0,
    total_words INTEGER DEFAULT 0,
    estimated_cost DOUBLE PRECISION DEFAULT 0.0,
    estimated_time INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    progress DOUBLE PRECISION DEFAULT 0.0,
    current_page INTEGER DEFAULT 0,
    running_summary TEXT DEFAULT '',
    tone_style VARCHAR(100) DEFAULT 'literary',
    custom_instructions TEXT DEFAULT '',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tạo bảng translation_chunks (Quản lý các đoạn dịch 8 trang của sách)
CREATE TABLE IF NOT EXISTS translation_chunks (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES translation_jobs(id) ON DELETE CASCADE,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    original_text TEXT,
    translated_text TEXT,
    summary_update TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    translated_at TIMESTAMP
);

-- 3. Tạo bảng glossary_items (Quản lý bảng thuật ngữ và cách xưng hô nhân vật)
CREATE TABLE IF NOT EXISTS glossary_items (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES translation_jobs(id) ON DELETE CASCADE,
    term_en VARCHAR(255) NOT NULL,
    term_vi VARCHAR(255) NOT NULL,
    description TEXT,
    is_auto_suggested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Thêm các Index để tối ưu hiệu năng tìm kiếm
CREATE INDEX IF NOT EXISTS idx_chunks_job_id ON translation_chunks(job_id);
CREATE INDEX IF NOT EXISTS idx_glossary_job_id ON glossary_items(job_id);
