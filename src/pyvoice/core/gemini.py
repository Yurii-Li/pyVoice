import os
import json
import time
import requests
import re
from typing import List, Dict, Callable

def safe_json_response(res: requests.Response) -> dict:
    """Безпечно парсить відповідь сервера"""
    try:
        return res.json()
    except Exception:
        return {}

def score_gemini_model(model_data: dict) -> float:
    """
    Динамічно оцінює придатність будь-якої моделі на основі її технічних метаданих
    (працює автоматично для будь-яких майбутніх версій Gemini без жорсткого хардкоду)
    """
    name = model_data.get("name", "").lower()
    methods = [m.lower() for m in model_data.get("supportedGenerationMethods", [])]
    input_tokens = model_data.get("inputTokenLimit", 0)

    # 1. Повинна бути основна генеративна модель Gemini
    if "gemini" not in name:
        return -1.0

    # 2. Обов'язкова підтримка генерації контенту
    if "generatecontent" not in methods:
        return -1.0

    # 3. Достатній ліміт контексту для відео (від 64k токенів, відсіює TTS/аудіо)
    if input_tokens < 64000:
        return -1.0

    # 4. Відсіюємо вузькоспеціалізовані або несумісні моделі
    for bad in ["tts", "audio", "eap", "robotics", "clip", "gemma", "computer-use", "nano", "aqa", "embed", "deep-research", "image"]:
        if bad in name:
            return -1.0

    score = 0.0

    # Розмір контекстного вікна (1M токенів = +100 балів)
    score += min(input_tokens / 10000.0, 100.0)

    # Flash моделі мають найвищий пріоритет для швидкого аналізу UI відео
    if "flash" in name:
        score += 150.0
    elif "pro" in name:
        score += 80.0

    # Стабільні універсальні latest аліаси від Google
    if "latest" in name:
        score += 100.0

    # Динамічний номер версії (наприклад 4.0 > 3.7 > 3.5 > 2.5 > 1.5)
    version_match = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    if version_match:
        try:
            score += float(version_match.group(1)) * 25.0
        except Exception:
            pass

    return score

def get_available_gemini_models(api_key: str, log_callback: Callable[[str], None]) -> List[str]:
    """Отримує та динамічно ранжує доступні моделі за якістю та сумісністю з відео"""
    log_callback("🔑 Перевірка API ключа та доступних моделей Gemini...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=15)
    except Exception as e:
        raise RuntimeError(f"Не вдалося з'єднатися з серверами Google: {str(e)}")

    if res.status_code != 200:
        err = safe_json_response(res).get("error", {}).get("message", res.text)
        raise RuntimeError(f"Помилка авторизації API ключа: {err}")

    data = safe_json_response(res)
    scored_models = []
    
    for m in data.get("models", []):
        score = score_gemini_model(m)
        if score > 0:
            scored_models.append((m.get("name"), score))

    if not scored_models:
        raise RuntimeError("Для вашого API ключа не знайдено доступних мультимодальних моделей (потрібно min 64k токенів).")

    # Сортуємо від найвищого балу до резервних
    scored_models.sort(key=lambda x: x[1], reverse=True)
    sorted_names = [name for name, _ in scored_models]
    return sorted_names

def upload_file_to_gemini(api_key: str, file_path: str, log_callback: Callable[[str], None]):
    """Завантажує файл у Gemini File API через протокол Resumable Upload"""
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    mime_type = "video/mp4"
    if file_path.lower().endswith(".mov"):
        mime_type = "video/quicktime"
    elif file_path.lower().endswith(".avi"):
        mime_type = "video/x-msvideo"
    elif file_path.lower().endswith(".mkv"):
        mime_type = "video/x-matroska"

    log_callback(f"📤 Завантаження {file_name} ({file_size / (1024*1024):.1f} МБ) у Google...")

    # Крок 1: Ініціалізація завантаження
    init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json"
    }
    body = {"file": {"displayName": file_name}}

    init_res = requests.post(init_url, headers=headers, json=body, timeout=30)
    if init_res.status_code != 200:
        error_msg = safe_json_response(init_res).get("error", {}).get("message", init_res.text)
        raise RuntimeError(f"Не вдалося ініціалізувати завантаження в Google: {error_msg}")

    upload_url = init_res.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        raise RuntimeError("Google API не надав URL для завантаження файлу.")

    # Крок 2: Завантаження чанків файлу
    upload_headers = {
        "Content-Length": str(file_size),
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize"
    }
    
    with open(file_path, "rb") as f:
        upload_res = requests.post(upload_url, headers=upload_headers, data=f, timeout=300)

    if upload_res.status_code != 200:
        error_msg = safe_json_response(upload_res).get("error", {}).get("message", upload_res.text)
        raise RuntimeError(f"Помилка завантаження файлу в Gemini: {error_msg}")

    file_info = safe_json_response(upload_res).get("file", {})
    file_uri = file_info.get("uri")
    file_resource_name = file_info.get("name") # e.g. "files/12345"

    log_callback("⏳ Відео завантажено. Очікування підготовки Google...")

    # Крок 3: Очікування зміни статусу на ACTIVE
    get_url = f"https://generativelanguage.googleapis.com/v1beta/{file_resource_name}?key={api_key}"
    max_wait_seconds = 180
    start_wait = time.time()
    
    while True:
        check_res = requests.get(get_url, timeout=15)
        if check_res.status_code == 200:
            status_data = safe_json_response(check_res)
            state = status_data.get("state")
            if state == "ACTIVE":
                log_callback("✅ Відео успішно підготовлено до аналізу.")
                break
            elif state == "FAILED":
                raise RuntimeError("Google не зміг обробити даний відеофайл.")
        
        if time.time() - start_wait > max_wait_seconds:
            raise TimeoutError("Час очікування обробки відео у Google Gemini вичерпано.")
            
        time.sleep(3)

    return file_resource_name, file_uri, mime_type

def delete_gemini_file(api_key: str, file_resource_name: str):
    """Видаляє тимчасовий файл з Gemini Storage"""
    try:
        del_url = f"https://generativelanguage.googleapis.com/v1beta/{file_resource_name}?key={api_key}"
        requests.delete(del_url, timeout=10)
    except Exception:
        pass

def extract_json_data(raw_text: str) -> List[Dict[str, str]]:
    """Універсальний надійний парсер JSON з відповіді моделі"""
    raw_text = raw_text.strip()
    
    # 1. Прямий парсинг
    try:
        return json.loads(raw_text)
    except Exception:
        pass
        
    # 2. Якщо обгорнуто в ```json ... ```
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    for m in matches:
        try:
            return json.loads(m.strip())
        except Exception:
            pass
            
    # 3. Пошук масиву [ ... ]
    start_idx = raw_text.find('[')
    end_idx = raw_text.rfind(']')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            return json.loads(raw_text[start_idx:end_idx+1])
        except Exception:
            pass
            
    # 4. Пошук об'єкта { ... }
    start_idx = raw_text.find('{')
    end_idx = raw_text.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        try:
            parsed = json.loads(raw_text[start_idx:end_idx+1])
            if isinstance(parsed, dict):
                for v in parsed.values():
                    if isinstance(v, list):
                        return v
        except Exception:
            pass
            
    raise ValueError(f"ШІ надав відповідь у непідтримуваному форматі:\n{raw_text[:200]}...")

def build_system_instruction(
    style_preset: str,
    include_intro: bool = True,
    explain_purpose: bool = True,
    include_outro: bool = True
) -> str:
    """Генерує детальний системний промпт відповідно до побажань користувача"""
    
    style_guidelines = ""
    if "Детальний туторіал" in style_preset:
        style_guidelines = (
            "- СТИЛЬ: Детальний, навчальний та зрозумілий туторіал.\n"
            "- ПОЯСНЕННЯ: Не просто констатуй дію ('клік мишкою'), а пояснюй НАВІЩО це робиться, яке призначення кнопки чи поля, та яка з цього користь.\n"
            "- ТОН: Дружній, професійний, спокійний темп викладу."
        )
    elif "Блогерський" in style_preset:
        style_guidelines = (
            "- СТИЛЬ: Живий, динамічний, захоплюючий блогерський стиль.\n"
            "- ПОЯСНЕННЯ: Звертайся до глядачів, підкреслюй круті фішки програми, додавай емоційного забарвлення.\n"
            "- ТОН: Енергійний, сучасний, невимушений."
        )
    elif "Офіційна презентація" in style_preset:
        style_guidelines = (
            "- СТИЛЬ: Діловий, структурований, презентаційний.\n"
            "- ПОЯСНЕННЯ: Описуй бізнес-цінність та функціональні переваги продукту.\n"
            "- ТОН: Стриманий, чіткий, експертний."
        )
    elif "Лаконічний" in style_preset:
        style_guidelines = (
            "- СТИЛЬ: Короткий і точний.\n"
            "- ПОЯСНЕННЯ: Лише сухі факти та конкретні кроки без зайвих вступів."
        )
    else:
        style_guidelines = f"- СТИЛЬ ТА ПОБАЖАННЯ: {style_preset}"

    rules = []
    if include_intro:
        rules.append("1. ОБОВ'ЯЗКОВО почни з репліки на 00:00 з привітанням глядачів та коротким анонсом того, що буде показано у відео.")
    else:
        rules.append("1. Починай коментувати безпосередньо з першої важливої дії.")

    if explain_purpose:
        rules.append("2. Для кожної дії детально розписуй її значення та суть, щоб відео було максимально інформативним для новачка.")
    else:
        rules.append("2. Коментуй лише ключові кроки.")

    if include_outro:
        rules.append("3. Наприкінці відео зроби гарний завершальний підсумок або подякуй за перегляд.")

    rules_str = "\n".join(rules)

    instruction = (
        "Ти професійний український диктор та автор навчальних відео. Твоє завдання — проаналізувати відеозапис інтерфейсу або дій користувача на екрані та скласти детальний, зв'язний сценарій озвучки.\n\n"
        f"{style_guidelines}\n\n"
        "ПРАВИЛА ОЗВУЧКИ:\n"
        f"{rules_str}\n"
        "4. Пиши розгорнуті, красиві, природні речення українською мовою без граматичних помилок.\n"
        "5. Зазначай точний таймкод початку дії (у форматі MM:SS, наприклад '00:00', '00:15', '01:05').\n\n"
        "ФОРМАТ ВІДПОВІДІ:\n"
        "Відповідай ВИКЛЮЧНО JSON-масивом об'єктів з полями 'start' (рядок MM:SS) та 'text' (текст репліки диктора):\n"
        "[\n"
        "  {\"start\": \"00:00\", \"text\": \"Вітаємо у цьому відео! Сьогодні ми розберемо...\"},\n"
        "  {\"start\": \"00:06\", \"text\": \"Далі відкриваємо розділ налаштувань, щоб налаштувати параметри під себе...\"}\n"
        "]"
    )
    return instruction

def analyze_video(
    api_key: str, 
    video_path: str, 
    style_preset: str,
    video_topic: str = "",
    include_intro: bool = True,
    explain_purpose: bool = True,
    include_outro: bool = True,
    custom_notes: str = "",
    log_callback: Callable[[str], None] = print
) -> List[Dict[str, str]]:
    """Аналізує дії у відео через Gemini REST API з розширеними налаштуваннями стилю"""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("Вкажіть ваш Google Gemini API Key!")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Відеофайл не знайдено: {video_path}")

    models_to_try = get_available_gemini_models(api_key, log_callback)
    file_resource_name, file_uri, mime_type = upload_file_to_gemini(api_key, video_path, log_callback)

    try:
        log_callback("👁️ ШІ аналізує відеоряд, формує змістовні коментарі та таймкоди...")

        system_instruction = build_system_instruction(
            style_preset=style_preset,
            include_intro=include_intro,
            explain_purpose=explain_purpose,
            include_outro=include_outro
        )

        user_prompt_text = "Проаналізуй це відео та склади повний, розгорнутий сценарій озвучки з таймкодами."
        if video_topic and video_topic.strip():
            user_prompt_text += f"\nКонтекст / Про що це відео: {video_topic.strip()}"
        if style_preset and style_preset.strip():
            user_prompt_text += f"\nОбраний стиль: {style_preset.strip()}"
        if custom_notes and custom_notes.strip():
            user_prompt_text += f"\nДодаткові побажання: {custom_notes.strip()}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "fileData": {
                                "mimeType": mime_type,
                                "fileUri": file_uri
                            }
                        },
                        {
                            "text": user_prompt_text
                        }
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [
                    {"text": system_instruction}
                ]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.3
            }
        }

        last_error = None
        raw_text = None

        for model_name in models_to_try:
            display_name = model_name.replace("models/", "")
            log_callback(f"  Запит до моделі {display_name}...")
            api_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
            try:
                gen_res = requests.post(api_url, json=payload, timeout=120)
                if gen_res.status_code == 200:
                    res_data = safe_json_response(gen_res)
                    candidates = res_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            if raw_text:
                                log_callback(f"✅ Відповідь успішно згенеровано ({display_name})!")
                                break
                else:
                    err_info = safe_json_response(gen_res).get("error", {}).get("message", gen_res.text)
                    last_error = f"Модель {display_name}: {err_info}"
            except Exception as e:
                last_error = str(e)

        if not raw_text:
            raise RuntimeError(f"Не вдалося згенерувати відповідь від Gemini. {last_error or ''}")

        log_callback("📝 Обробка отриманого сценарію...")
        data = extract_json_data(raw_text)

        if not isinstance(data, list):
            if isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, list):
                        data = val
                        break

        valid_items = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "start" in item and "text" in item:
                    valid_items.append({
                        "start": str(item["start"]),
                        "text": str(item["text"]).strip()
                    })

        if not valid_items:
            raise ValueError(f"Отримано некоректну структуру сценарію:\n{raw_text[:200]}...")

        log_callback(f"🎉 Сценарій готовий: сформовано {len(valid_items)} розгорнутих реплік.")
        return valid_items

    finally:
        # Автоматичне видалення тимчасового файлу з хмари Google
        log_callback("🧹 Очищення тимчасового відеофайлу з серверів Google...")
        delete_gemini_file(api_key, file_resource_name)
