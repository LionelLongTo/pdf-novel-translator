import re
import logging
import os
import urllib.request
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

class HTMLGeneratorService:
    @staticmethod
    def _get_page_images_html(job_id: str, page_num: str) -> str:
        if not job_id:
            return ""
            
        # Thư mục chứa hình ảnh của Job
        image_dir = Path(__file__).resolve().parent.parent / "resources" / "images" / job_id
        if not image_dir.exists():
            return ""
            
        # Tìm tất cả file ảnh của trang này: page_{page_num}_*.ext
        images = []
        for file in image_dir.glob(f"page_{page_num}_*.*"):
            if file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
                # Đường dẫn tương đối từ workspace root, link_callback sẽ phân tích thành đường dẫn tuyệt đối
                relative_path = f"app/resources/images/{job_id}/{file.name}"
                images.append(relative_path)
                
        if not images:
            return ""
            
        # Sắp xếp các ảnh theo số thứ tự
        images.sort()
        
        images_html = []
        for img_path in images:
            images_html.append(
                f'<div class="image-wrapper" style="text-align: center; margin: 1.5em 0; page-break-inside: avoid;">'
                f'<img src="{img_path}" style="max-width: 100%; max-height: 8cm; display: block; margin: 0 auto;"/>'
                f'</div>'
            )
        return "\n".join(images_html)

    @staticmethod
    def _text_to_html_paragraphs(text: str, job_id: str = None) -> str:
        if not text:
            return ""
            
        parts = re.split(r'(?i)(-+\s*(?:page|trang)\s*\d+\s*-+)', text)
        html_output = []
        page_opened = False
        prev_page_num = None
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            page_match = re.match(r'(?i)-+\s*(?:page|trang)\s*(\d+)\s*-+', part)
            if page_match:
                page_num = page_match.group(1)
                if page_opened:
                    # Chèn hình ảnh của trang trước đó trước khi đóng trang
                    if prev_page_num and job_id:
                        images_html = HTMLGeneratorService._get_page_images_html(job_id, prev_page_num)
                        if images_html:
                            html_output.append(images_html)
                    html_output.append("</div><!-- end page -->")
                html_output.append(f'<div class="page" id="page-{page_num}">')
                html_output.append(f'<span class="page-marker">Trang {page_num}</span>')
                page_opened = True
                prev_page_num = page_num
            else:
                if not page_opened:
                    html_output.append('<div class="page" id="page-1">')
                    page_opened = True
                    prev_page_num = "1"
                
                paragraphs = re.split(r'\n\s*\n', part)
                for i, p in enumerate(paragraphs):
                    p = p.strip()
                    if not p:
                        continue
                    
                    is_chapter = False
                    if len(p) < 100 and (p.upper() == p or p.startswith("Chương") or p.startswith("Chapter") or p.startswith("CHƯƠNG")):
                        is_chapter = True
                        
                    if is_chapter:
                        html_output.append(f'<h2 class="chapter-title">{p}</h2>')
                    else:
                        p_cleaned = p.replace("\n", "<br/>")
                        class_attr = ' class="first-p"' if i == 0 else ""
                        html_output.append(f'<p{class_attr}>{p_cleaned}</p>')
                        
        if page_opened:
            # Chèn hình ảnh của trang cuối cùng trước khi đóng trang cuối
            if prev_page_num and job_id:
                images_html = HTMLGeneratorService._get_page_images_html(job_id, prev_page_num)
                if images_html:
                    html_output.append(images_html)
            html_output.append("</div><!-- end page -->")
            
        return "\n".join(html_output)

    @classmethod
    def download_font(cls, url: str, dest_path: Path) -> bool:
        """
        Tải font chữ từ URL về thư mục cục bộ nếu chưa tồn tại.
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            return True
        logger.info(f"Đang tải font {dest_path.name} từ Google Fonts...")
        try:
            # Thiết lập User-Agent giả lập trình duyệt để tránh bị GitHub block
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')]
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve(url, str(dest_path))
            logger.info(f"Tải thành công font: {dest_path.name}")
            return True
        except Exception as e:
            logger.error(f"Không thể tải font {dest_path.name} từ {url}: {e}")
            return False

    @classmethod
    def register_system_fonts(cls):
        """
        Đăng ký font chữ Unicode trực tiếp vào ReportLab.
        Ưu tiên tải font Lora (Google Fonts) cực đẹp cho tiểu thuyết.
        Nếu không có mạng, tự động fallback sang font hệ thống Windows (Times New Roman hoặc Arial).
        """
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.fonts import addMapping
        
        # Thư mục lưu trữ font cục bộ của dự án
        font_dir = Path(__file__).resolve().parent.parent / "resources" / "fonts"
        font_dir.mkdir(parents=True, exist_ok=True)
        
        font_files = {
            "reg": font_dir / "Lora-Regular.ttf",
            "bold": font_dir / "Lora-Bold.ttf",
            "italic": font_dir / "Lora-Italic.ttf",
            "bi": font_dir / "Lora-BoldItalic.ttf"
        }
        
        urls = {
            "reg": "https://github.com/google/fonts/raw/main/ofl/lora/static/Lora-Regular.ttf",
            "bold": "https://github.com/google/fonts/raw/main/ofl/lora/static/Lora-Bold.ttf",
            "italic": "https://github.com/google/fonts/raw/main/ofl/lora/static/Lora-Italic.ttf",
            "bi": "https://github.com/google/fonts/raw/main/ofl/lora/static/Lora-BoldItalic.ttf"
        }
        
        # Thử tải bộ font Lora
        download_success = True
        for key, path in font_files.items():
            if not path.exists():
                success = cls.download_font(urls[key], path)
                if not success:
                    download_success = False
                    break
                    
        # Nếu tải thất bại hoặc không có file, tự động dùng font Times New Roman của Windows làm fallback
        if not download_success or not font_files["reg"].exists():
            logger.warning("Không thể tải font Lora từ internet. Đang fallback sang font hệ thống Windows...")
            font_files = {
                "reg": Path("C:/Windows/Fonts/times.ttf"),
                "bold": Path("C:/Windows/Fonts/timesbd.ttf"),
                "italic": Path("C:/Windows/Fonts/timesi.ttf"),
                "bi": Path("C:/Windows/Fonts/timesbi.ttf")
            }
            # Nếu không tìm thấy Times New Roman, dùng Arial
            if not font_files["reg"].exists():
                font_files = {
                    "reg": Path("C:/Windows/Fonts/arial.ttf"),
                    "bold": Path("C:/Windows/Fonts/arialbd.ttf"),
                    "italic": Path("C:/Windows/Fonts/ariali.ttf"),
                    "bi": Path("C:/Windows/Fonts/arialbi.ttf")
                }
                
        try:
            # Đăng ký các tệp font này với ReportLab
            pdfmetrics.registerFont(TTFont('BookFont', str(font_files["reg"])))
            pdfmetrics.registerFont(TTFont('BookFont-Bold', str(font_files["bold"])))
            pdfmetrics.registerFont(TTFont('BookFont-Italic', str(font_files["italic"])))
            pdfmetrics.registerFont(TTFont('BookFont-BoldItalic', str(font_files["bi"])))
            
            # Ánh xạ thuộc tính bold/italic của CSS sang font tương ứng
            addMapping('BookFont', 0, 0, 'BookFont')
            addMapping('BookFont', 1, 0, 'BookFont-Bold')
            addMapping('BookFont', 0, 1, 'BookFont-Italic')
            addMapping('BookFont', 1, 1, 'BookFont-BoldItalic')
            
            logger.info(f"Đăng ký font thành công sử dụng file: {font_files['reg']}")
            return True
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi đăng ký font vào ReportLab: {e}", exc_info=True)
            return False

    @classmethod
    def get_font_paths(cls) -> Dict[str, str]:
        """
        Lấy đường dẫn tuyệt đối của các tệp font sẽ được sử dụng.
        Đảm bảo đồng bộ với logic trong register_system_fonts.
        """
        font_dir = Path(__file__).resolve().parent.parent / "resources" / "fonts"
        font_files = {
            "reg": font_dir / "Lora-Regular.ttf",
            "bold": font_dir / "Lora-Bold.ttf",
            "italic": font_dir / "Lora-Italic.ttf",
            "bi": font_dir / "Lora-BoldItalic.ttf"
        }
        
        # Nếu font cục bộ đã tồn tại hoàn chỉnh, dùng luôn
        if all(path.exists() for path in font_files.values()):
            return {k: str(v.resolve()).replace("\\", "/") for k, v in font_files.items()}
            
        # Thử tải hoặc tìm font hệ thống
        cls.register_system_fonts()
        
        if all(path.exists() for path in font_files.values()):
            return {k: str(v.resolve()).replace("\\", "/") for k, v in font_files.items()}
            
        # Fallback sang font hệ thống Windows
        sys_fonts = {
            "reg": Path("C:/Windows/Fonts/times.ttf"),
            "bold": Path("C:/Windows/Fonts/timesbd.ttf"),
            "italic": Path("C:/Windows/Fonts/timesi.ttf"),
            "bi": Path("C:/Windows/Fonts/timesbi.ttf")
        }
        if sys_fonts["reg"].exists():
            return {k: str(v.resolve()).replace("\\", "/") for k, v in sys_fonts.items()}
            
        sys_fonts_arial = {
            "reg": Path("C:/Windows/Fonts/arial.ttf"),
            "bold": Path("C:/Windows/Fonts/arialbd.ttf"),
            "italic": Path("C:/Windows/Fonts/ariali.ttf"),
            "bi": Path("C:/Windows/Fonts/arialbi.ttf")
        }
        return {k: str(v.resolve()).replace("\\", "/") for k, v in sys_fonts_arial.items()}

    @classmethod
    def generate_html(cls, title: str, author: str, translated_text: str, job_id: str = None) -> str:
        body_content = cls._text_to_html_paragraphs(translated_text, job_id)
        font_paths = cls.get_font_paths()
        
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        @font-face {{
            font-family: BookFont;
            src: url('{font_paths["reg"]}');
        }}
        @font-face {{
            font-family: BookFont;
            src: url('{font_paths["bold"]}');
            font-weight: bold;
        }}
        @font-face {{
            font-family: BookFont;
            src: url('{font_paths["italic"]}');
            font-style: italic;
        }}
        @font-face {{
            font-family: BookFont;
            src: url('{font_paths["bi"]}');
            font-weight: bold;
            font-style: italic;
        }}

        @page {{
            size: A5;
            margin: 2.2cm 1.8cm 2.2cm 1.8cm;
            @frame footer {{
                -pdf-frame-content: footer_content;
                bottom: 1cm;
                left: 1.8cm;
                width: 11.2cm;
                height: 1cm;
            }}
            @frame header {{
                -pdf-frame-content: header_content;
                top: 1cm;
                left: 1.8cm;
                width: 11.2cm;
                height: 1cm;
            }}
        }}

        body {{
            font-family: BookFont;
            font-size: 11pt;
            line-height: 1.5;
            color: #1a1a1a;
        }}

        /* Bố cục trang bìa */
        .cover-page {{
            text-align: center;
            padding-top: 4cm;
            page-break-after: always;
        }}

        .cover-title {{
            font-size: 24pt;
            font-weight: bold;
            color: #111111;
            margin-bottom: 0.5cm;
            line-height: 1.3;
        }}

        .cover-author {{
            font-size: 14pt;
            font-style: italic;
            color: #444444;
            margin-top: 0.5cm;
            margin-bottom: 3cm;
        }}

        .cover-divider {{
            width: 80px;
            height: 2px;
            background-color: #333333;
            margin: 1cm auto;
        }}

        .cover-subtitle {{
            font-size: 10pt;
            color: #777777;
            margin-top: 3cm;
            text-transform: uppercase;
        }}

        /* Bố cục trang nội dung */
        .page {{
        }}
        
        .page-marker {{
            display: none;
        }}

        h2.chapter-title {{
            page-break-before: always;
            font-size: 15pt;
            font-weight: bold;
            text-align: center;
            margin-top: 2cm;
            margin-bottom: 1.5cm;
            color: #000000;
        }}
        
        .first-p {{
            text-indent: 0 !important;
        }}

        p {{
            text-indent: 1.5em;
            margin-top: 0;
            margin-bottom: 0.4em;
            text-align: justify;
        }}
        
        blockquote {{
            margin: 1em 2em;
            font-style: italic;
            color: #333333;
        }}
    </style>
</head>
<body>
    <!-- Định nghĩa nội dung Header và Footer cho xhtml2pdf -->
    <div id="header_content" style="text-align: center; font-size: 8pt; font-family: 'BookFont'; font-style: italic; color: #888888; display: none;">
        {title}
    </div>
    
    <div id="footer_content" style="text-align: center; font-size: 9pt; font-family: 'BookFont'; color: #666666; display: none;">
        <pdf:pagenumber />
    </div>

    <!-- Trang bìa sách -->
    <div class="cover-page">
        <div class="cover-title">{title}</div>
        <div class="cover-author">{author}</div>
        <div class="cover-divider"></div>
        <div class="cover-subtitle">Bản dịch tiếng Việt bằng AI</div>
    </div>

    <!-- Nội dung bản dịch -->
    <div class="book-content">
        {body_content}
    </div>
</body>
</html>
"""
        return html_template

    @classmethod
    def compile_pdf(cls, html_content: str, output_path: str) -> bool:
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Ghi file HTML dự phòng
        html_backup_path = output_path_obj.with_suffix('.html')
        with open(html_backup_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        # Thử dùng xhtml2pdf trước (Pure Python, không phụ thuộc GTK/thư viện ngoài)
        try:
            # Đăng ký font Unicode hệ thống trực tiếp vào ReportLab trước
            cls.register_system_fonts()
            
            # Khắc phục lỗi Windows NamedTemporaryFile file-lock bằng cách monkey-patch xhtml2pdf
            import os
            from xhtml2pdf.files import pisaFileObject
            
            # Lưu gốc để fallback nếu cần
            if not hasattr(pisaFileObject, '_original_getNamedFile'):
                pisaFileObject._original_getNamedFile = pisaFileObject.getNamedFile
                
            def patched_getNamedFile(self):
                # Nếu URI là đường dẫn tệp cục bộ hợp lệ, trả về trực tiếp để tránh tạo file tạm bị khóa trên Windows
                uri = self.uri
                if uri:
                    path_str = uri
                    if path_str.startswith('file://'):
                        path_str = path_str[7:]
                        if path_str.startswith('/') and len(path_str) > 2 and path_str[2] == ':':
                            path_str = path_str[1:]
                        from urllib.parse import unquote
                        path_str = unquote(path_str)
                    
                    path_str = os.path.normpath(path_str)
                    if not os.path.isabs(path_str):
                        path_str = os.path.abspath(path_str)
                    if os.path.exists(path_str):
                        return path_str
                return pisaFileObject._original_getNamedFile(self)
                
            pisaFileObject.getNamedFile = patched_getNamedFile
            
            # Định nghĩa link_callback để giải quyết các đường dẫn tài nguyên (như font, ảnh)
            def link_callback(uri, rel):
                path_str = uri
                if path_str.startswith('file://'):
                    path_str = path_str[7:]
                    if path_str.startswith('/') and len(path_str) > 2 and path_str[2] == ':':
                        path_str = path_str[1:]
                    from urllib.parse import unquote
                    path_str = unquote(path_str)
                
                path_str = os.path.normpath(path_str)
                if not os.path.isabs(path_str):
                    path_str = os.path.abspath(path_str)
                    
                if os.path.exists(path_str):
                    return path_str
                    
                # Thử tìm trong thư mục font cục bộ của dự án
                font_dir = Path(__file__).resolve().parent.parent / "resources" / "fonts"
                filename = os.path.basename(path_str)
                local_font_path = font_dir / filename
                if local_font_path.exists():
                    return str(local_font_path.resolve())
                    
                # Trả về uri gốc nếu không tìm thấy
                return uri

            from xhtml2pdf import pisa
            logger.info("Đang biên dịch HTML sang PDF bằng xhtml2pdf...")
            
            with open(output_path, "wb") as result_file:
                pisa_status = pisa.CreatePDF(
                    html_content,
                    dest=result_file,
                    encoding='utf-8',
                    link_callback=link_callback
                )
                
            if not pisa_status.err and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                logger.info(f"Xuất PDF thành công bằng xhtml2pdf tại: {output_path}")
                return True
            else:
                logger.error(f"Lỗi khi biên dịch PDF bằng xhtml2pdf: Status Err={pisa_status.err}")
                if Path(output_path).exists():
                    os.remove(output_path)
        except ImportError:
            logger.info("Chưa cài xhtml2pdf. Thử dùng WeasyPrint làm dự phòng...")
            if Path(output_path).exists():
                os.remove(output_path)
        except Exception as e:
            logger.error(f"Lỗi hệ thống khi chạy xhtml2pdf: {e}", exc_info=True)
            if Path(output_path).exists():
                try:
                    os.remove(output_path)
                except:
                    pass

        # Thử dùng WeasyPrint làm phương án dự phòng
        try:
            from weasyprint import HTML
            logger.info("Đang biên dịch HTML sang PDF bằng WeasyPrint...")
            HTML(string=html_content).write_pdf(output_path)
            
            if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                logger.info(f"Xuất PDF thành công bằng WeasyPrint tại: {output_path}")
                return True
            else:
                if Path(output_path).exists():
                    os.remove(output_path)
                return False
        except Exception as e:
            logger.error(
                f"Cả xhtml2pdf và WeasyPrint đều thất bại: {e}. "
                f"Vui lòng in file HTML dự phòng: {html_backup_path} trực tiếp từ Chrome/Edge sang PDF."
            )
            if Path(output_path).exists():
                try:
                    os.remove(output_path)
                except:
                    pass
            return False
