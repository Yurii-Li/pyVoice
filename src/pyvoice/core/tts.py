import os
import json
import time
import base64
import subprocess
import requests
import re
import sys
import edge_tts
from typing import List, Dict, Callable, Optional, Tuple
from pyvoice.core.video import get_media_duration_seconds
from pyvoice.core.gemini import get_available_gemini_tts_models
from pyvoice.utils.paths import get_bin_path

def convert_pcm_to_mp3(pcm_data: bytes, output_mp3_path: str, rate: int = 24000) -> None:
    """Конвертує сирі PCM байти від Google Gemini у високоякісний MP3 через FFmpeg"""
    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "s16le",
        "-ar", str(rate),
        "-ac", "1",
        "-i", "pipe:0",
        "-b:a", "192k",
        output_mp3_path
    ]
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creationflags)
    p.communicate(input=pcm_data)

def format_natural_text_for_edge(text: str) -> str:
    """Додає природне інтонаційне членування для розмовного звучання Edge TTS"""
    text = text.replace("...", "... ")
    text = text.replace("!", "! ")
    text = text.replace("?", "? ")
    return text.strip()

async def generate_single_edge_speech(text: str, voice_code: str, output_path: str, is_natural: bool = False) -> None:
    """Генерує аудіо через Edge TTS"""
    clean_text = format_natural_text_for_edge(text)
    
    if is_natural:
        communicate = edge_tts.Communicate(clean_text, voice_code, rate="+5%", pitch="+1Hz")
    else:
        communicate = edge_tts.Communicate(clean_text, voice_code)
        
    await communicate.save(output_path)

def is_daily_quota_exhausted(raw_body: str) -> bool:
    """Визначає, чи вичерпано саме добову квоту (PerDay) для конкретної моделі"""
    lower = raw_body.lower()
    return "perday" in lower or "quotavalue\": \"10\"" in lower or "generaterequestsperday" in lower

def align_and_split_with_whisper(
    big_mp3_path: str, 
    items: List[Dict[str, any]], 
    output_dir: str, 
    log_callback: Callable[[str], None],
    start_phrase_num: int = 1
) -> bool:
    """
    Використовує автономний whisper-cli для точного розпізнавання таймкодів слів
    всередині згенерованого аудіофайлу та нарізає їх на окремі audio_X.mp3.
    """
    whisper_exe = get_bin_path("whisper-cli.exe")
    model_path = get_bin_path("ggml-tiny.bin")
    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    
    bin_dir = os.path.dirname(whisper_exe)
    os.makedirs(bin_dir, exist_ok=True)
    
    # 1. Якщо модель відсутня — автоматично завантажуємо її
    if not os.path.exists(model_path) or os.path.getsize(model_path) < 10000000:
        try:
            log_callback("  📥 Одноразове завантаження моделі Whisper (~75 МБ)...")
            import urllib.request
            urllib.request.urlretrieve("https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin", model_path)
            log_callback("  ✅ Модель Whisper успішно завантажена!")
        except Exception as e:
            log_callback(f"  ⚠️ Не вдалося завантажити модель Whisper: {str(e)}")
            return False

    # 2. Якщо бінарник whisper-cli відсутній — автоматично завантажуємо рушій
    if not os.path.exists(whisper_exe) or os.path.getsize(whisper_exe) < 100000:
        try:
            log_callback("  📥 Одноразове встановлення рушія Whisper (~2 МБ)...")
            import urllib.request, zipfile, io
            zip_url = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip"
            req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                with zipfile.ZipFile(io.BytesIO(resp.read())) as z:
                    for info in z.infolist():
                        base = os.path.basename(info.filename)
                        if base and not info.is_dir():
                            out_p = os.path.join(bin_dir, base)
                            with open(out_p, "wb") as f:
                                f.write(z.read(info.filename))
            log_callback("  ✅ Рушій Whisper успішно встановлено!")
        except Exception as e:
            log_callback(f"  ⚠️ Не вдалося встановити рушій Whisper: {str(e)}")
            return False
            
    if not os.path.exists(whisper_exe) or not os.path.exists(model_path):
        log_callback("  ⚠️ Whisper-cli або модель відсутні.")
        return False
        
    wav_path = os.path.join(output_dir, "whisper_temp.wav")
    try:
        # 1. Конвертуємо великий MP3 у 16kHz mono WAV для Whisper
        subprocess.run([
            ffmpeg_exe, "-y",
            "-i", big_mp3_path,
            "-ar", "16000",
            "-ac", "1",
            wav_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
        
        # 2. Запускаємо автономний Whisper CLI для розпізнавання таймкодів
        cmd = [
            whisper_exe,
            "-m", model_path,
            "-f", wav_path,
            "-l", "uk",
            "-oj"
        ]
        res = subprocess.run(cmd, cwd=bin_dir, capture_output=True, text=True, creationflags=creationflags)
        
        json_path = wav_path + ".json"
        if not os.path.exists(json_path):
            log_callback(f"  ⚠️ Не вдалося згенерувати JSON розпізнавання Whisper: {res.stderr[:200] if res.stderr else res.stdout[:200]}")
            return False
            
        with open(json_path, "r", encoding="utf-8") as f:
            w_data = json.load(f)
            
        transcriptions = w_data.get("transcription", [])
        if not transcriptions:
            return False
            
        total_audio_len = get_media_duration_seconds(big_mp3_path)
        total_items = len(items)
        
        # 3. Знаходимо точки початку кожної репліки за маркерами та словами
        item_starts = []
        current_whisper_idx = 0
        
        for idx in range(total_items):
            global_phrase_idx = start_phrase_num + idx
            target_text = items[idx]["text"].lower().strip()
            first_words = [w for w in re.findall(r'\w+', target_text)[:3] if len(w) > 2]
            
            found_start = None
            for w_idx in range(current_whisper_idx, len(transcriptions)):
                seg_text = transcriptions[w_idx].get("text", "").lower()
                offsets = transcriptions[w_idx].get("offsets", {})
                cand_start = max(0.0, offsets.get("from", 0) / 1000.0)
                
                has_match = (
                    f"фраза {global_phrase_idx}" in seg_text or 
                    f"[{global_phrase_idx}]" in seg_text or 
                    (first_words and any(w in seg_text for w in first_words))
                )
                if has_match:
                    if not item_starts or cand_start > item_starts[-1] + 0.3:
                        found_start = cand_start
                        current_whisper_idx = w_idx + 1
                        break
                    
            if found_start is None:
                prev_start = item_starts[-1] if item_starts else 0.0
                remaining_time = max(1.0, total_audio_len - prev_start)
                remaining_items = max(1, total_items - idx)
                found_start = prev_start + (remaining_time / remaining_items) if item_starts else (idx / total_items) * total_audio_len
                
            item_starts.append(found_start)
            
        # 4. Нарізаємо кожен фрагмент з точними таймкодами та захистом від 0-тривалості
        for idx in range(total_items):
            global_file_idx = start_phrase_num - 1 + idx
            s_start = item_starts[idx]
            if idx + 1 < total_items:
                s_end = item_starts[idx + 1]
            else:
                s_end = total_audio_len
                
            if s_end <= s_start + 0.1:
                s_end = min(total_audio_len, s_start + 1.0)
                
            duration = max(0.2, s_end - s_start)
            fade_out_st = max(0.0, duration - 0.02)
            
            out_p = os.path.join(output_dir, f"audio_{global_file_idx}.mp3")
            cut_cmd = [
                ffmpeg_exe, "-y",
                "-ss", f"{s_start:.3f}",
                "-to", f"{s_end:.3f}",
                "-i", big_mp3_path,
                "-af", f"afade=t=in:ss=0:d=0.02,afade=t=out:st={fade_out_st:.3f}:d=0.02,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-b:a", "192k",
                out_p
            ]
            subprocess.run(cut_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
            
            items[idx]["audio_path"] = out_p
            items[idx]["audio_duration"] = get_media_duration_seconds(out_p)
            
        return True
        
    except Exception as e:
        log_callback(f"  ⚠️ Помилка вирівнювання Whisper: {str(e)}")
        return False
    finally:
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
            json_file = wav_path + ".json"
            if os.path.exists(json_file):
                os.remove(json_file)
        except Exception:
            pass

def generate_single_gemini_speech_with_retry(
    text: str, 
    model_name: str,
    voice_name: str, 
    api_key: str, 
    output_path: str,
    replica_num: int,
    log_callback: Callable[[str], None],
    max_retries: int = 8,
    retry_pause_seconds: int = 10
) -> Tuple[bool, str]:
    """
    Генерує аудіо через вказану модель Google Gemini з детальним логуванням,
    миттєвим переходом при 404/400 або добовому ліміті, та паузами при хвилинних лімітах.
    """
    if not api_key:
        return False, "Відсутній Gemini API Key"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": text}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name
                    }
                }
            }
        }
    }

    last_error_desc = ""

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(url, json=payload, timeout=300)
            
            if res.status_code == 200:
                res_data = res.json()
                candidates = res_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        inline = parts[0].get("inlineData", {})
                        raw_b64 = inline.get("data", "")
                        if raw_b64:
                            pcm_bytes = base64.b64decode(raw_b64)
                            convert_pcm_to_mp3(pcm_bytes, output_path, rate=24000)
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                                return True, ""
                last_error_desc = "Порожня відповідь аудіо від сервера Google"

            else:
                raw_body = res.text.strip()
                last_error_desc = f"[HTTP {res.status_code}] {raw_body}"
                
                if res.status_code in [400, 404]:
                    log_callback(f"  ⚠️ Модель {model_name} повернула помилку [HTTP {res.status_code}]: не підтримує REST generateContent.")
                    return False, last_error_desc

                if is_daily_quota_exhausted(raw_body):
                    log_callback(f"  🚫 У моделі {model_name} вичерпано добовий ліміт запитів (PerDay).")
                    return False, f"Вичерпано добовий ліміт моделі {model_name}:\n{raw_body}"

                log_callback(f"  ⚠️ Відповідь сервера Google ({model_name}) [HTTP {res.status_code}]:\n{raw_body}")
                delay_sec = retry_pause_seconds
                match = re.search(r'"retryDelay":\s*"(\d+)s"', raw_body)
                if match:
                    delay_sec = min(int(match.group(1)) + 1, 35)

                if attempt < max_retries:
                    log_callback(f"  ⏳ Хвилинний ліміт {model_name}: пауза {delay_sec}с перед спробою {attempt+1}/{max_retries}...")
                    time.sleep(delay_sec)
                    continue

        except requests.exceptions.Timeout:
            last_error_desc = f"Таймаут з'єднання з {model_name} (понад 5 хвилин)"
            if attempt < max_retries:
                log_callback(f"  ⚠️ Таймаут відповіді. Пауза {retry_pause_seconds}с перед спробою {attempt+1}/{max_retries}...")
                time.sleep(retry_pause_seconds)
                continue
        except Exception as e:
            last_error_desc = f"Мережевий збій: {str(e)}"
            if attempt < max_retries:
                log_callback(f"  ⚠️ Помилка мережі: {str(e)}. Пауза {retry_pause_seconds}с перед спробою {attempt+1}/{max_retries}...")
                time.sleep(retry_pause_seconds)
                continue

    return False, last_error_desc

async def generate_speech_chunks(
    items: List[Dict[str, str]], 
    voice_key: str, 
    temp_dir: str, 
    log_callback: Callable[[str], None],
    api_key: str = "",
    fallback_callback: Optional[Callable[[str, str], Optional[str]]] = None
) -> None:
    """
    Універсальний диспетчер синтезу мови:
    - РОЗУМНЕ ПАКЕТУВАННЯ (Smart Batching): до 30 реплік на 1 запит Gemini.
    - WHISPER FORCED ALIGNMENT: локальний Whisper автономно розпізнає послівні таймкоди та нарізає audio_X.mp3 зі 100% точністю!
    """
    os.makedirs(temp_dir, exist_ok=True)
    
    current_voice = voice_key
    total = len(items)
    
    gemini_tts_models = get_available_gemini_tts_models(api_key) if api_key else []
    gemini_model_idx = 0

    while True:
        is_gemini_voice = "gemini" in current_voice.lower()
        is_natural_edge = "живий" in current_voice.lower() or "жива" in current_voice.lower()
        
        current_gemini_model = gemini_tts_models[gemini_model_idx] if gemini_tts_models and gemini_model_idx < len(gemini_tts_models) else "gemini-2.5-flash-preview-tts"
        
        log_voice_title = f"{current_voice} [{current_gemini_model}]" if is_gemini_voice else current_voice
        log_callback(f"🎙 1. Генерація аудіофрагментів диктора ({log_voice_title})...")
        
        gemini_voice_name = "Puck"
        for v_name in ["Puck", "Aoede", "Charon", "Kore", "Fenrir"]:
            if v_name.lower() in current_voice.lower():
                gemini_voice_name = v_name
                break

        edge_voice_code = "uk-UA-OstapNeural"
        if "polina" in current_voice.lower() or "поліна" in current_voice.lower():
            edge_voice_code = "uk-UA-PolinaNeural"

        generation_failed = False
        failure_error_msg = ""

        # -------------------------------------------------------------
        # РОЗУМНЕ ПАКЕТУВАННЯ GEMINI (до 30 реплік на 1 запит) + WHISPER
        # -------------------------------------------------------------
        if is_gemini_voice and api_key:
            BATCH_SIZE = 25
            if total <= 30:
                batches = [(0, items)]
            else:
                batches = [(i, items[i:i + BATCH_SIZE]) for i in range(0, total, BATCH_SIZE)]
                
            num_batches = len(batches)
            if num_batches == 1:
                log_callback(f"  ⚡ Генерація всього сценарію ({total} реплік) за 1 єдиний запит до {current_gemini_model}...")
            else:
                log_callback(f"  ⚡ Оптимальний поділ сценарію ({total} реплік) на {num_batches} пакети по ~{BATCH_SIZE} реплік...")
            
            all_batches_ok = True
            
            for b_idx, (offset, batch_items) in enumerate(batches):
                b_count = len(batch_items)
                start_num = offset + 1
                end_num = offset + b_count
                
                if num_batches > 1:
                    log_callback(f"  🎙 Озвучення пакета {b_idx+1}/{num_batches} (репліки {start_num}..{end_num}) через {current_gemini_model}...")
                
                prompt_parts = []
                for idx, item in enumerate(batch_items):
                    clean_text = item["text"].strip()
                    prompt_parts.append(f"[Фраза {start_num + idx}]: {clean_text}")

                full_script_text = "\n\n".join(prompt_parts)
                big_audio_file = os.path.join(temp_dir, f"gemini_batch_{b_idx}.mp3")

                success, error_desc = generate_single_gemini_speech_with_retry(
                    text=full_script_text,
                    model_name=current_gemini_model,
                    voice_name=gemini_voice_name,
                    api_key=api_key,
                    output_path=big_audio_file,
                    replica_num=b_idx + 1,
                    log_callback=log_callback,
                    max_retries=8,
                    retry_pause_seconds=10
                )

                if success and os.path.exists(big_audio_file):
                    log_callback(f"  🔍 Розпізнавання таймкодів {'пакета ' + str(b_idx+1) if num_batches > 1 else 'реплік'} через Whisper AI...")
                    align_ok = align_and_split_with_whisper(
                        big_audio_file, batch_items, temp_dir, log_callback, start_phrase_num=start_num
                    )
                    if not align_ok:
                        all_batches_ok = False
                        failure_error_msg = f"Помилка розпізнавання Whisper у пакеті {b_idx+1}"
                        break
                else:
                    all_batches_ok = False
                    failure_error_msg = error_desc
                    log_callback(f"❌ Модель {current_gemini_model} не змогла згенерувати пакет {b_idx+1}:\n{error_desc}")
                    break

            if all_batches_ok:
                generation_failed = False
                log_callback("✅ Усі репліки успішно озвучено та вирівняно!")
                break
            else:
                generation_failed = True
                # Якщо помилка сталася після отримання аудіо (на боці Whisper), не витрачаємо запити на інші моделі
                if "Whisper" in failure_error_msg:
                    log_callback("  ⚠️ Помилка вирівнювання Whisper. Оберіть інший голос або повторіть спробу.")
                    if fallback_callback is not None:
                        chosen_voice = fallback_callback(failure_error_msg, current_voice)
                        if chosen_voice:
                            current_voice = chosen_voice
                            continue
                        else:
                            raise RuntimeError("Озвучення скасовано користувачем.")
                    break

        # -------------------------------------------------------------
        # ЗВИЧАЙНА ГЕНЕРАЦІЯ ДЛЯ EDGE-TTS (безлімітна)
        # -------------------------------------------------------------
        else:
            for idx in range(total):
                item = items[idx]
                clean_prompt_text = item["text"].strip()
                audio_path = os.path.join(temp_dir, f"audio_{idx}.mp3")
                log_callback(f"  Озвучування репліки {idx+1}/{total} (таймкод {item['start']}): \"{clean_prompt_text[:30]}...\"")
                await generate_single_edge_speech(clean_prompt_text, edge_voice_code, audio_path, is_natural=is_natural_edge)
                item["audio_path"] = audio_path
                item["audio_duration"] = get_media_duration_seconds(audio_path)

        if not generation_failed:
            log_callback("✅ Усі репліки успішно озвучено та вирівняно!")
            break

        # Якщо сталася помилка мережі або ліміту саме з Gemini API — перемикаємо на наступну модель
        if is_gemini_voice and gemini_model_idx + 1 < len(gemini_tts_models):
            gemini_model_idx += 1
            next_model = gemini_tts_models[gemini_model_idx]
            log_callback(f"  🔄 Перемикання на наступну модель {next_model}...")
            continue

        # Якщо всі сумісні моделі Gemini вичерпано, відкриваємо діалог вибору альтернативного голосу
        if fallback_callback is not None:
            log_callback("⏳ Усі доступні моделі Gemini вичерпали денні ліміти. Очікування рішення користувача в діалоговому вікні...")
            chosen_voice = fallback_callback(failure_error_msg, current_voice)
            if chosen_voice:
                log_callback(f"🔄 Користувач обрав '{chosen_voice}'. Перезапуск озвучки новим голосом...")
                current_voice = chosen_voice
                continue
            else:
                log_callback("🛑 Озвучення скасовано користувачем.")
                raise RuntimeError("Озвучення скасовано користувачем.")
        else:
            log_callback(f"⚠️ Аварійний перехід на Edge TTS через помилку: {failure_error_msg}")
            current_voice = "Edge-TTS: Остап (🔥 Живий / Динамічний)"
            continue
