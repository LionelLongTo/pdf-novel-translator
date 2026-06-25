import os
import sys
from pathlib import Path

# Thêm thư mục hiện tại vào python path
sys.path.append(str(Path(__file__).resolve().parent))

from app.services.pdf_service import PDFService as PDFProcessor
from app.services.translator_service import TranslatorService as OpenRouterTranslator
from app.services.html_generator_service import HTMLGeneratorService as HTMLGenerator

def test_pdf_extraction():
    print("--- 1. Kiểm tra Module Xử lý PDF (PyMuPDF) ---")
    
    # Tạo một file PDF giả lập để test nếu không có file thực tế
    test_pdf = Path("test_novel.pdf")
    if not test_pdf.exists():
        print("Tạo file PDF mẫu 'test_novel.pdf'...")
        import fitz
        doc = fitz.open()
        
        # Trang 1: Giới thiệu
        page1 = doc.new_page()
        page1.insert_text((50, 50), "THE ADVENTURES OF SHERLOCK HOLMES")
        page1.insert_text((50, 100), "Chapter 1: A Scandal in Bohemia")
        page1.insert_text((50, 150), "To Sherlock Holmes she is always the woman. I have seldom heard him mention her under any other name. In his eyes she eclipses and predominates the whole of her sex.")
        
        # Trang 2: Tình tiết tiếp theo
        page2 = doc.new_page()
        page2.insert_text((50, 50), "He felt the strongest attraction towards Irene Adler, yet his cold, precise mind was not suited for love.")
        page2.insert_text((50, 100), "Holmes was a man who preferred observation over emotion. He remained in his rooms in Baker Street, buried among his old books.")
        
        doc.save(str(test_pdf))
        doc.close()
        print("Đã tạo file test_novel.pdf thành công.")
        
    # Thử lấy thông tin PDF
    info = PDFProcessor.get_pdf_info(str(test_pdf))
    print(f"Tổng số trang: {info['total_pages']}")
    print(f"Ước lượng từ: {info['total_words']}")
    print(f"Ước lượng chi phí: ${info['estimated_cost']}")
    print(f"Ước lượng thời gian: {info['estimated_time']} giây")
    
    # Thử trích xuất text trang 1 và 2
    text = PDFProcessor.extract_text_range(str(test_pdf), 1, 2)
    print("\nVăn bản trích xuất mẫu:")
    print(text[:300] + "...")
    print("-------------------------------------------\n")
    return test_pdf

def test_translator():
    print("--- 2. Kiểm tra Module Dịch thuật (OpenRouter / Mock) ---")
    translator = OpenRouterTranslator()
    
    # Test gợi ý glossary từ 10 trang đầu (trang 1-2 của file test)
    sample_text = "To Sherlock Holmes she is always the woman. Irene Adler was a singer from London."
    print("Đang quét thuật ngữ tự động...")
    suggestions = translator.scan_glossary_suggestions(sample_text)
    print("Gợi ý từ vựng tìm thấy:")
    for sug in suggestions:
        print(f"  - {sug.get('term_en')} -> {sug.get('term_vi')} ({sug.get('description')})")
        
    # Test dịch chunk
    print("\nĐang dịch thử một đoạn...")
    vi_text, summary_update = translator.translate_chunk(
        text="--- PAGE 1 ---\nTo Sherlock Holmes she is always the woman. Irene Adler was born in New Jersey.",
        running_summary="",
        glossary_list=[{"term_en": "Sherlock Holmes", "term_vi": "Thám tử Sherlock Holmes", "description": "Nhân vật chính"}],
        tone_style="literary",
        custom_instructions="Dịch xưng hô lịch sự."
    )
    print("Bản dịch thu được:")
    print(vi_text)
    print(f"Cập nhật tóm tắt: {summary_update}")
    print("-------------------------------------------\n")
    return vi_text

def test_pdf_generation(translated_text):
    print("--- 3. Kiểm tra Biên dịch HTML & PDF (WeasyPrint) ---")
    title = "Những Cuộc Phiêu Lưu Của Sherlock Holmes"
    author = "Arthur Conan Doyle"
    
    html_content = HTMLGenerator.generate_html(title, author, translated_text)
    
    output_pdf = "translated_test_novel.pdf"
    output_html = "translated_test_novel.html"
    
    print(f"Đang thử biên dịch sang file: {output_pdf}...")
    success = HTMLGenerator.compile_pdf(html_content, output_pdf)
    
    if success:
        print(f"Thành công! File PDF được lưu tại: {Path(output_pdf).resolve()}")
    else:
        print(f"Không thể biên dịch sang PDF bằng WeasyPrint (có thể thiếu GTK3 trên Windows).")
        print(f"Đã lưu file dự phòng HTML tại: {Path(output_html).resolve()}")
        print("Bạn có thể mở file HTML này bằng Chrome/Edge và chọn 'In sang PDF' (Print to PDF).")
    print("-------------------------------------------\n")

if __name__ == "__main__":
    print("=== BẮT ĐẦU KIỂM TRA HỆ THỐNG ===")
    try:
        pdf_path = test_pdf_extraction()
        vi_text = test_translator()
        test_pdf_generation(vi_text)
        print("=== HOÀN THÀNH KIỂM TRA ===")
    except Exception as e:
        print(f"\n❌ Gặp lỗi trong quá trình kiểm tra: {e}")
        import traceback
        traceback.print_exc()
