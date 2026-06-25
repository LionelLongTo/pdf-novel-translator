import json
import logging
import re
from typing import Dict, List, Tuple, Any
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

TONE_STYLES = {
    "literary": "Văn học (mượt mà, uyển chuyển, giàu tính hình tượng và cảm xúc)",
    "detective": "Trinh thám / Kịch tính (ngắn gọn, hồi hộp, câu văn sắc sảo, tập trung vào chi tiết)",
    "modern": "Hiện đại (tự nhiên, gần gũi, đời thường, ngôn ngữ trẻ trung nếu phù hợp)",
    "classic": "Cổ điển (trang trọng, cổ kính, sử dụng từ Hán-Việt phù hợp với bối cảnh lịch sử hoặc giả tưởng kiếm hiệp)",
}

class TranslatorService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self._current_key_idx = 0
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key or "mock",
            default_headers={
                "HTTP-Referer": "https://github.com/google-gemini",
                "X-Title": "PDF Novel AI Translator"
            }
        )

    def _clean_and_parse_json(self, response_text: str) -> Dict[str, Any]:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        # Thử parse toàn bộ văn bản trước
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Lỗi phân giải JSON trực tiếp (đang thử trích xuất thông minh): {e}")
            
            # Thử trích xuất bằng raw_decode bắt đầu từ dấu '{' đầu tiên
            start_idx = text.find('{')
            if start_idx != -1:
                try:
                    obj, _ = json.JSONDecoder().raw_decode(text[start_idx:])
                    return obj
                except json.JSONDecodeError:
                    pass
                    
            # Fallback cuối cùng dùng regex greedy
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
                    
            logger.error(f"Thất bại hoàn toàn khi phân giải JSON. Nội dung thô: {response_text}")
            raise e

    def _call_gemini_api(self, system_prompt: str, user_content: str, json_mode: bool = False) -> str:
        """
        Gọi trực tiếp Google Gemini API sử dụng cơ chế xoay vòng 5 API key.
        - Nếu lỗi 429: Chuyển ngay sang key kế tiếp.
        - Nếu lỗi khác: Thử lại tối đa 3 lần trên key hiện tại trước khi chuyển key.
        """
        import httpx
        keys = [k.strip() for k in settings.GEMINI_API_KEYS.split(",") if k.strip()]
        if not keys:
            raise ValueError("Không có GEMINI_API_KEYS nào được cấu hình trong file .env.")

        num_keys = len(keys)
        
        # Thử đi thử lại qua tất cả các key tối đa 2 vòng
        for key_attempt in range(num_keys * 2):
            idx = (self._current_key_idx + key_attempt) % num_keys
            api_key = keys[idx]
            
            # Thử lại 3 lần cho mỗi key nếu lỗi không phải 429
            for retry in range(3):
                try:
                    logger.info(f"Đang gọi Gemini API sử dụng Key số {idx+1}/{num_keys} (Thử lần {retry+1})...")
                    
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
                    
                    payload = {
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": user_content}]
                            }
                        ]
                    }
                    
                    if system_prompt:
                        payload["systemInstruction"] = {
                            "parts": [{"text": system_prompt}]
                        }
                        
                    generation_config = {}
                    if json_mode:
                        generation_config["responseMimeType"] = "application/json"
                    
                    if generation_config:
                        payload["generationConfig"] = generation_config

                    # Gọi request đồng bộ bằng httpx với timeout 60s
                    with httpx.Client(timeout=60.0) as client:
                        response = client.post(url, json=payload)
                        response.raise_for_status()
                        
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if not candidates:
                            raise ValueError(f"Không nhận được candidates từ Gemini API. Response: {data}")
                            
                        content_parts = candidates[0].get("content", {}).get("parts", [])
                        if not content_parts:
                            raise ValueError(f"Không nhận được parts text từ Gemini API. Response: {data}")
                            
                        self._current_key_idx = idx
                        return content_parts[0].get("text", "")
                        
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    response_text = e.response.text
                    logger.warning(f"Key {idx+1} trả về lỗi HTTP {status_code}: {response_text}")
                    
                    if status_code == 429:
                        logger.warning("Lỗi 429 Rate Limit. Đang chuyển sang key tiếp theo ngay lập tức...")
                        break
                    else:
                        if retry < 2:
                            logger.warning(f"Lỗi hệ thống. Đang thử lại sau... (Lần {retry+2}/3)")
                        else:
                            logger.warning("Thử lại hết 3 lần vẫn thất bại. Đang chuyển sang key tiếp theo...")
                except Exception as e:
                    logger.warning(f"Gặp lỗi kết nối/hệ thống với Key {idx+1}: {e}")
                    if retry < 2:
                        logger.warning(f"Đang thử lại sau... (Lần {retry+2}/3)")
                    else:
                        logger.warning("Thử lại hết 3 lần vẫn thất bại. Đang chuyển sang key tiếp theo...")
                        
        raise RuntimeError("TẤT CẢ các API Key Gemini đều gặp lỗi và không thể hoàn thành yêu cầu.")

    def scan_glossary_suggestions(self, text: str, provider: str = "openrouter") -> List[Dict[str, str]]:
        """
        Quét văn bản để tự động gợi ý nhân vật và thuật ngữ bản dịch.
        """
        prompt = f"""You are a professional literary translator and editor.
Analyze the following introductory text from an English novel. Extract key character names, unique terminology, place names, or specialized vocabulary, and suggest their optimal Vietnamese translations or representation, keeping in mind the literary tone.
Output your response as a valid JSON object matching the following structure:
{{
  "glossary": [
    {{
      "term_en": "Character name or term in English (e.g. John)",
      "term_vi": "Suggested Vietnamese translation (e.g. John or hắn/chàng nếu dịch ngữ cảnh, hoặc giữ nguyên tên riêng)",
      "description": "Brief description of who/what this is or translation notes"
    }}
  ]
}}

Introductory Text:
{text}
"""

        if provider == "google":
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Đang quét Glossary từ Google Gemini (Lượt thử {attempt+1}/{max_retries})...")
                    content = self._call_gemini_api(
                        system_prompt="",
                        user_content=prompt,
                        json_mode=True
                    )
                    parsed = self._clean_and_parse_json(content)
                    return parsed.get("glossary", [])
                except Exception as e:
                    logger.warning(f"Lỗi khi quét/phân tích Glossary từ Google Gemini API ở lượt thử {attempt+1}: {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"Đã thử quét {max_retries} lần từ Google Gemini API nhưng đều thất bại: {e}")
                        raise e

        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            return [
                {"term_en": "Example Character", "term_vi": "Nhân vật mẫu", "description": "Tên nhân vật gợi ý từ chế độ chạy thử."}
            ]

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Đang quét Glossary từ OpenRouter (Lượt thử {attempt+1}/{max_retries})...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    extra_body={
                        "provider": {
                            "allow_fallbacks": settings.OPENROUTER_ALLOW_FALLBACKS
                        }
                    }
                )
                content = response.choices[0].message.content
                parsed = self._clean_and_parse_json(content)
                return parsed.get("glossary", [])
            except Exception as e:
                logger.warning(f"Lỗi khi quét/phân tích Glossary từ OpenRouter ở lượt thử {attempt+1}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Đã thử quét {max_retries} lần từ OpenRouter nhưng đều thất bại: {e}")
                    raise e


    def translate_chunk(
        self,
        text: str,
        running_summary: str,
        glossary_list: List[Dict[str, Any]],
        tone_style: str,
        custom_instructions: str,
        translator_provider: str = "openrouter"
    ) -> Tuple[str, str]:
        """
        Dịch một chunk text bằng cách gọi API OpenRouter hoặc Google Gemini.
        """
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            pages = re.findall(r"--- PAGE (\d+) ---", text)
            page_info = f"Pages: {', '.join(pages)}" if pages else "chunk"
            mock_translation = f"--- BẢN DỊCH DEMO ({page_info}) ---\nĐây là bản dịch mẫu vì chưa có API Key OpenRouter. Văn bản gốc bắt đầu bằng: '{text[:100]}...'"
            return mock_translation, f"Tóm tắt cập nhật cho trang {', '.join(pages) if pages else ''}."

        glossary_str = ""
        if glossary_list:
            glossary_str = "\n".join([
                f"- '{g['term_en']}' dịch là '{g['term_vi']}' ({g.get('description', '')})"
                for g in glossary_list
            ])
        else:
            glossary_str = "Không có thiết lập cụ thể. Hãy tự nhận diện xưng hô phù hợp."

        style_desc = TONE_STYLES.get(tone_style, tone_style)

        system_prompt = f"""You are a master translator specializing in translating novels from English to Vietnamese.
Your translations must be smooth, natural, and respect Vietnamese grammar and idiom while keeping the original author's voice and formatting.
Avoid rigid word-for-word translation. Instead, adapt pronouns ("he", "she", "they") dynamically depending on characters' relationships and ages (e.g., "anh ấy", "cô ấy", "hắn", "nàng", "ông", "bà", "y").

Follow these guidelines strictly:
1. Target Tone/Style: {style_desc}
2. Glossary & Name Translations (You MUST use these translations):
{glossary_str}
3. Custom Instructions (if any):
{custom_instructions or "None"}
4. Novel Plot Summary So Far (use this to ensure plot continuity and logical pronoun evolution):
{running_summary or "Bắt đầu tiểu thuyết."}

Output format: You MUST respond in plain text using the following exact structure with the tag markers. Do NOT wrap in JSON. Your output must strictly look like this:

[START_TRANSLATION]
(The complete translated text of the input chunk in Vietnamese, keeping all page header markers like '--- PAGE X ---' and paragraphs exactly where they are)
[END_TRANSLATION]

[START_SUMMARY]
(A concise list of new plot points, character interactions, or details introduced in this chunk, limited to 100-150 words in Vietnamese)
[END_SUMMARY]
"""

        user_content = f"Translate this text chunk using the system instructions:\n\n{text}"

        try:
            if translator_provider == "google":
                content = self._call_gemini_api(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    json_mode=False
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.3,
                    extra_body={
                        "provider": {
                            "allow_fallbacks": settings.OPENROUTER_ALLOW_FALLBACKS
                        }
                    }
                )
                content = response.choices[0].message.content
            
            # Parse text bằng tag ranh giới
            translated_text = ""
            summary_updates = ""
            
            translation_match = re.search(r'\[START_TRANSLATION\](.*?)\[END_TRANSLATION\]', content, re.DOTALL | re.IGNORECASE)
            summary_match = re.search(r'\[START_SUMMARY\](.*?)\[END_SUMMARY\]', content, re.DOTALL | re.IGNORECASE)
            
            if translation_match:
                translated_text = translation_match.group(1).strip()
            else:
                idx = content.find("[START_TRANSLATION]")
                if idx != -1:
                    end_idx = content.find("[START_SUMMARY]")
                    if end_idx != -1:
                        translated_text = content[idx + len("[START_TRANSLATION]"):end_idx].strip()
                    else:
                        translated_text = content[idx + len("[START_TRANSLATION]"):].strip()
                        
            if summary_match:
                summary_updates = summary_match.group(1).strip()
            else:
                idx = content.find("[START_SUMMARY]")
                if idx != -1:
                    end_idx = content.find("[END_SUMMARY]")
                    if end_idx != -1:
                        summary_updates = content[idx + len("[START_SUMMARY]"):end_idx].strip()
                    else:
                        summary_updates = content[idx + len("[START_SUMMARY]"):].strip()
            
            # Fallback nếu AI hoàn toàn không dùng tag ranh giới
            if not translated_text and not summary_updates:
                logger.warning("Không tìm thấy thẻ định dạng ranh giới trong phản hồi của AI. Coi toàn bộ là bản dịch.")
                translated_text = content.strip()
                
            return translated_text, summary_updates
            
        except Exception as e:
            logger.error(f"Lỗi khi thực hiện dịch thuật: {e}")
            raise e
