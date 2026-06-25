# Sử dụng Python 3.11 slim làm base image để đảm bảo dung lượng nhẹ
FROM python:3.11-slim

# Ngăn Python ghi file .pyc và bật chế độ xuất log không đệm (unbuffered)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho WeasyPrint, PyMuPDF, psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    shared-mime-info \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Sao chép file requirements.txt trước để tận dụng cơ chế cache lớp của Docker
COPY requirements.txt .

# Cài đặt các thư viện Python cần thiết cho Backend
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn Backend vào container
COPY . .

# Tạo các thư mục lưu trữ dữ liệu tải lên và kết quả đầu ra
RUN mkdir -p upload output

# Mở cổng chạy ứng dụng FastAPI (mặc định port 8000)
EXPOSE 8000

# Lệnh khởi chạy server uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
