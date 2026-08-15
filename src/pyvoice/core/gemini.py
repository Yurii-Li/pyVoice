import os
import time
import json
import re
import requests
from typing import List, Dict, Callable

def safe_json_response(res: requests.Response) -> dict:
    """Безпечно парсить JSON відповіді або повертає словник з помилкою"""
    try:
        return res.json()
    except Exception:
        return {"error": {"message": res.text or f"HTTP статус {res.status_code}"}}

def get_available_gemini_models(api_key: str, log_callback: Callable[[str], None]) -> List[str]:
    """Отримує список доступних моделей для даного API ключа"""
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
    available = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            available.append(m.get("name"))

    if not available:
        raise RuntimeError("Для вашого API ключа не знайдено доступних моделей.")

    # Пріоритет швидких та якісних моделей
    priority = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
        "models/gemini-2.0-flash-lite",
        "models/gemini-1.5-pro"
    ]

    sorted_models = []
    for p in priority:
        if p in available:
            sorted_models.append(p)

    for a in available:
        if a not in sorted_models and "flash" in a:
            sorted_models.append(a)

    for a in available:
        if a not in sorted_models:
            sorted_models.append(a)

    return sorted_models

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
        raise RuntimeError(f"Помилка ініціалізації завантаження в Gemini: {error_msg}")

    upload_url = init_res.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        raise RuntimeError("Не вдалося отримати посилання для завантаження від Google.")

    # Крок 2: Відправка бінарних даних файлу
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

    # 3. Знайти масив між '[' та ']'
    first_bracket = raw_text.find('[')
    last_bracket = raw_text.rfind(']')
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = raw_text[first_bracket:last_bracket+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 4. Витягти окремі об'єкти регулярним виразом
    pattern = r'\{\s*"start"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"([^"]+)"\s*\}'
    found = re.findall(pattern, raw_text)
    if found:
        return [{"start": s, "text": t} for s, t in found]

    raise ValueError(f"Відповідь ШІ не містить коректного JSON:\n{raw_text[:300]}")

def build_system_instruction(style_preset: str, include_intro: bool, explain_purpose: bool, include_outro: bool) -> str:
    """Формує детальну та гнучку системну інструкцію для якісного сценарію"""
    instruction = (
        "Ти — професійний сценарист, диктор та експерт зі створення цікавих, живих і змістовних закадрових відеороликів українською мовою.\n"
        "Твоє завдання — детально переглянути відеоряд, зрозуміти що відбувається на екрані, і скласти повний сценарій закадрової озвучки з точними таймкодами (у форматі MM:SS).\n\n"
        "ГОЛОВНІ ПРАВИЛА ОЗВУЧКИ:\n"
    )

    if include_intro:
        instruction += (
            "1. ВСТУП І ПРИВІТАННЯ (00:00): Обов'язково почни з приємного привітання глядачів та вступного пояснення "
            "(наприклад: 'Вітаємо! У цьому відео ми детально розберемо...', 'Привіт усім! Сьогодні поглянемо як працює...').\n"
        )
    else:
        instruction += "1. Починай озвучку з першої дії на екрані (00:00).\n"

    if explain_purpose:
        instruction += (
            "2. ДЕТАЛІ ТА СУТЬ ФУНКЦІОНАЛУ: Не роби сухий опис на кшталт 'натискаємо кнопку'. "
            "Пояснюй ДЛЯ ЧОГО ця дія потрібна, ЩО ЦЕ ЗА ФУНКЦІОНАЛ, як він працює і яку користь дає глядачеві/користувачеві. "
            "Давай корисні пояснення та контекст до кожної важливої дії на екрані.\n"
        )
    else:
        instruction += "2. Описуй дії лаконічно та зрозуміло.\n"

    instruction += (
        "3. МОВА ТА ПОДАЧА: Тільки природна, багата, жива українська мова без кальки. Речення мають легко вимовлятися диктором.\n"
        "4. ТАЙМКОДИ: 'start' — це точний таймкод моменту на відео (MM:SS), коли починається дія або блок пояснення.\n"
    )

    if include_outro:
        instruction += (
            "5. ПІДСУМОК У КІНЦІ: Наприкінці відео зроби гарне завершення, підсумок показаного або подякуй за увагу.\n"
        )

    instruction += (
        "\nФОРМАТ ВІДПОВІДІ:\n"
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
            raise ValueError(f"ШІ повернув текст, але в ньому не знайдено списку реплік:\n{raw_text[:200]}")

        log_callback(f"🎉 Успішно розпізнано {len(valid_items)} розгорнутих дій на екрані!")
        return valid_items

    finally:
        log_callback("🧹 Очищення тимчасового відео з хмари Google...")
        delete_gemini_file(api_key, file_resource_name)
