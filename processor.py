import json
import asyncio
import os
import subprocess
import sys
import time
import re
import requests
import edge_tts
import shutil

def get_bin_path(exe_name):
    """Отримує шлях до бінарного файлу (ffmpeg, ffprobe)"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "bin", exe_name)
    else:
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", exe_name)
        if os.path.exists(local_path):
            return local_path
        return exe_name

def parse_time_to_seconds(time_str: str) -> float:
    """Конвертує 'MM:SS' або 'HH:MM:SS' у секунди"""
    try:
        parts = list(map(int, time_str.strip().split(':')))
        if len(parts) == 2:
            return float(parts[0] * 60 + parts[1])
        elif len(parts) == 3:
            return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    except Exception:
        pass
    return 0.0

def get_duration_seconds(file_path: str) -> float:
    ffprobe_exe = get_bin_path("ffprobe.exe")
    cmd = [
        ffprobe_exe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=creationflags)
    return float(result.stdout.strip())

def safe_json_response(res):
    """Безпечно парсить JSON відповіді або повертає текст помилки"""
    try:
        return res.json()
    except Exception:
        return {"error": {"message": res.text or f"HTTP статус {res.status_code}"}}

def get_available_gemini_models(api_key: str, log_callback):
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
            available.append(m.get("name")) # e.g. "models/gemini-2.0-flash"

    if not available:
        raise RuntimeError("Для вашого API ключа не знайдено доступних моделей.")

    # Пріоритетний список
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

def upload_file_to_gemini(api_key: str, file_path: str, log_callback):
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

def extract_json_data(raw_text: str):
    """Універсальний надійний парсер JSON з відповіді моделі"""
    raw_text = raw_text.strip()
    
    # 1. Спроба прямого парсингу
    try:
        return json.loads(raw_text)
    except Exception:
        pass
        
    # 2. Якщо обгорнуто в ```json ... ``` або ``` ... ```
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    for m in matches:
        try:
            return json.loads(m.strip())
        except Exception:
            pass

    # 3. Знайти масив між першим '[' та останнім ']'
    first_bracket = raw_text.find('[')
    last_bracket = raw_text.rfind(']')
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = raw_text[first_bracket:last_bracket+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 4. Знайти об'єкт між першим '{' та останнім '}'
    first_brace = raw_text.find('{')
    last_brace = raw_text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = raw_text[first_brace:last_brace+1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 5. Витягти окремі елементи за допомогою регулярного виразу
    pattern = r'\{\s*"start"\s*:\s*"([^"]+)"\s*,\s*"text"\s*:\s*"([^"]+)"\s*\}'
    found = re.findall(pattern, raw_text)
    if found:
        return [{"start": s, "text": t} for s, t in found]

    raise ValueError(f"Відповідь ШІ не містить коректного JSON:\n{raw_text[:300]}")

def build_system_instruction(style_preset: str, include_intro: bool, explain_purpose: bool, include_outro: bool):
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

def analyze_video_with_gemini(
    api_key: str, 
    video_path: str, 
    style_preset: str,
    video_topic: str = "",
    include_intro: bool = True,
    explain_purpose: bool = True,
    include_outro: bool = True,
    custom_notes: str = "",
    log_callback = print
):
    """Аналізує дії у відео через Gemini REST API з розширеними налаштуваннями стилю"""
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("Вкажіть ваш Google Gemini API Key!")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Відеофайл не знайдено: {video_path}")

    # Отримуємо список робочих моделей
    models_to_try = get_available_gemini_models(api_key, log_callback)

    # Завантажуємо відео
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

async def generate_speech_chunks(items, voice, log_callback):
    os.makedirs("temp_process", exist_ok=True)
    log_callback("🎙 1. Генерація аудіофрагментів диктора...")
    
    total = len(items)
    for idx, item in enumerate(items):
        log_callback(f"  Озвучування репліки {idx+1}/{total} (таймкод {item['start']}): \"{item['text'][:30]}...\"")
        audio_path = os.path.join("temp_process", f"audio_{idx}.mp3")
        communicate = edge_tts.Communicate(item["text"], voice)
        await communicate.save(audio_path)
        item["audio_path"] = audio_path
        item["audio_duration"] = get_duration_seconds(audio_path)
        
    log_callback("✅ Усі репліки успішно озвучено!")

def process_video_and_sync(items, input_video, output_video, log_callback):
    total_video_len = get_duration_seconds(input_video)
    concat_list_path = os.path.join("temp_process", "concat_list.txt")
    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    
    log_callback("🎬 2. Нарізка відео, створення стоп-кадрів та синхронізація...")
    
    segment_files = []
    total = len(items)
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
    for idx, item in enumerate(items):
        log_callback(f"  Монтаж сегменту {idx+1}/{total} (таймкод {item['start']})...")
        start_sec = parse_time_to_seconds(item["start"])
        if idx + 1 < len(items):
            end_sec = parse_time_to_seconds(items[idx + 1]["start"])
        else:
            end_sec = total_video_len
            
        video_clip_duration = max(0.1, end_sec - start_sec)
        audio_len = item["audio_duration"] + 0.3  # 0.3с пауза після фрази
        
        chunk_video_raw = os.path.join("temp_process", f"vchunk_{idx}.mp4")
        
        cut_cmd = [
            ffmpeg_exe, "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", input_video,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-an", chunk_video_raw
        ]
        subprocess.run(cut_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
        
        chunk_final = os.path.join("temp_process", f"segment_{idx}.mp4")
        
        # Якщо озвучка довша за дію на відео — ставимо стоп-кадр (freeze frame)
        if audio_len > video_clip_duration:
            freeze_sec = audio_len - video_clip_duration
            filter_str = f"tpad=stop_mode=clone:stop_duration={freeze_sec:.2f}"
            
            cmd = [
                ffmpeg_exe, "-y",
                "-i", chunk_video_raw,
                "-i", item["audio_path"],
                "-filter_complex", f"[0:v]{filter_str}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264", "-c:a", "aac",
                "-shortest",
                chunk_final
            ]
        else:
            cmd = [
                ffmpeg_exe, "-y",
                "-i", chunk_video_raw,
                "-i", item["audio_path"],
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264", "-c:a", "aac",
                chunk_final
            ]
            
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
        segment_files.append(chunk_final)

    log_callback("🔗 3. Фінальне склеювання всіх сегментів...")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for seg in segment_files:
            normalized_path = os.path.abspath(seg).replace("\\", "/")
            f.write(f"file '{normalized_path}'\n")

    concat_cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_video
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
    log_callback(f"🎉 Готово! Синхронізоване відео збережено:\n{output_video}")

async def run_pipeline(input_video, items_or_file, output_video, voice, log_callback):
    try:
        if isinstance(items_or_file, str):
            with open(items_or_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = items_or_file
            
        await generate_speech_chunks(data, voice, log_callback)
        process_video_and_sync(data, input_video, output_video, log_callback)
        
        log_callback("🧹 Очищення тимчасових файлів...")
        shutil.rmtree("temp_process", ignore_errors=True)
        log_callback("✅ Процес успішно завершено!")
        
    except Exception as e:
        log_callback(f"❌ Помилка: {str(e)}")
        raise
