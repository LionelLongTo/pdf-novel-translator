import fitz  # PyMuPDF
from typing import Dict, List, Any
import re
from pathlib import Path

class PDFService:
    @staticmethod
    def get_pdf_info(pdf_path: str) -> Dict[str, Any]:
        """
        Phân tích sơ bộ file PDF: đếm số trang, số từ, và ước lượng thời gian & chi phí dịch.
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")
            
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        total_words = 0
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text("text")
            words = re.findall(r'\b\w+\b', text)
            total_words += len(words)
            
        doc.close()
        
        # Ước tính chi phí
        estimated_input_tokens = total_words * 1.35
        chunk_size_pages = 8
        num_chunks = max(1, -(-total_pages // chunk_size_pages))
        estimated_context_tokens = num_chunks * 2000 
        
        total_input_tokens = estimated_input_tokens + estimated_context_tokens
        total_output_tokens = estimated_input_tokens
        
        cost_input = (total_input_tokens / 1_000_000) * 0.1
        cost_output = (total_output_tokens / 1_000_000) * 0.4
        estimated_cost = round(cost_input + cost_output, 4)
        if estimated_cost < 0.01:
            estimated_cost = 0.01
            
        # Ước tính thời gian dịch
        estimated_time = max(15, num_chunks * 12)
        
        return {
            "total_pages": total_pages,
            "total_words": total_words,
            "estimated_cost": estimated_cost,
            "estimated_time": estimated_time
        }

    @staticmethod
    def extract_text_range(pdf_path: str, start_page: int, end_page: int) -> str:
        """
        Trích xuất văn bản từ trang start_page đến end_page (1-indexed, inclusive).
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")
            
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        start_idx = max(0, start_page - 1)
        end_idx = min(total_pages - 1, end_page - 1)
        
        extracted_text = []
        for i in range(start_idx, end_idx + 1):
            page = doc[i]
            page_text = page.get_text("text")
            extracted_text.append(f"--- PAGE {i + 1} ---\n{page_text.strip()}")
            
        doc.close()
        return "\n\n".join(extracted_text)

    @staticmethod
    def generate_chunks(pdf_path: str, chunk_size: int = 8) -> List[Dict[str, Any]]:
        """
        Chia nhỏ PDF thành các đoạn dịch (Chunks) gồm nhiều trang.
        """
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()
        
        chunks = []
        for start in range(1, total_pages + 1, chunk_size):
            end = min(start + chunk_size - 1, total_pages)
            chunks.append({
                "start_page": start,
                "end_page": end,
                "status": "pending"
            })
        return chunks

    @staticmethod
    def extract_images(pdf_path: str, job_id: str) -> int:
        """
        Trích xuất tất cả hình ảnh minh họa từ PDF gốc và lưu vào thư mục cục bộ của Job.
        Trả về số lượng hình ảnh trích xuất thành công.
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"Không tìm thấy file PDF tại: {pdf_path}")
            
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Thư mục đích lưu ảnh: app/resources/images/{job_id}/
        output_dir = Path(__file__).resolve().parent.parent / "resources" / "images" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_count = 0
        for page_num in range(total_pages):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Tên file ảnh: page_{page_num+1}_{img_idx+1}.{ext}
                    # page_num+1 để đồng bộ với số trang 1-indexed của hệ thống
                    img_filename = f"page_{page_num + 1}_{img_idx + 1}.{image_ext}"
                    img_path = output_dir / img_filename
                    
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                    image_count += 1
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Không thể trích xuất ảnh {img_idx} ở trang {page_num + 1}: {e}"
                    )
                    
        doc.close()
        return image_count
