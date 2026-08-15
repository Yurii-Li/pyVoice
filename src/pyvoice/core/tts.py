import os
import json
import time
import base64
import subprocess
import requests
import re
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
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            res = requests.post(url, json=payload, timeout=40)
            
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
                
                # 1. Якщо модель повернула 404/400 (не підтримує даний REST-метод) — ніяких повторів, миттєво переходимо
                if res.status_code in [400, 404]:
                    log_callback(f"  ⚠️ Модель {model_name} повернула помилку [HTTP {res.status_code}]: не підтримує REST generateContent.")
                    return False, last_error_desc

                # 2. Якщо це добова квота для цієї моделі — негайно перемикаємо на наступну модель
                if is_daily_quota_exhausted(raw_body):
                    log_callback(f"  🚫 У моделі {model_name} вичерпано добовий ліміт запитів (PerDay).")
                    return False, f"Вичерпано добовий ліміт моделі {model_name}:\n{raw_body}"

                # 3. Якщо це тимчасовий хвилинний ліміт (RPM) — робимо паузу з retryDelay
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
            last_error_desc = f"Таймаут з'єднання з {model_name} (понад 40 секунд)"
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
    - Якщо одна модель Gemini вичерпала ліміт, автоматично перемикається на наступну REST-сумісну модель (3.1 Flash, 2.5 Flash, 2.5 Pro).
    - Якщо ВСІ моделі Gemini вичерпали квоту, відкриває діалогове вікно вибору для користувача.
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

        for idx, item in enumerate(items):
            clean_prompt_text = item["text"].strip()
            log_callback(f"  Озвучування репліки {idx+1}/{total} (таймкод {item['start']}): \"{clean_prompt_text[:30]}...\"")
            audio_path = os.path.join(temp_dir, f"audio_{idx}.mp3")
            
            if is_gemini_voice and api_key:
                success, error_desc = generate_single_gemini_speech_with_retry(
                    text=clean_prompt_text,
                    model_name=current_gemini_model,
                    voice_name=gemini_voice_name,
                    api_key=api_key,
                    output_path=audio_path,
                    replica_num=idx+1,
                    log_callback=log_callback,
                    max_retries=8,
                    retry_pause_seconds=10
                )
                
                if not success:
                    generation_failed = True
                    failure_error_msg = error_desc
                    log_callback(f"❌ Модель {current_gemini_model} не змогла завершити репліку {idx+1}:\n{error_desc}")
                    break
            else:
                await generate_single_edge_speech(clean_prompt_text, edge_voice_code, audio_path, is_natural=is_natural_edge)
                
            item["audio_path"] = audio_path
            item["audio_duration"] = get_media_duration_seconds(audio_path)

        if not generation_failed:
            log_callback("✅ Усі репліки успішно озвучено єдиним голосом!")
            break

        # Якщо сталася помилка з поточною моделлю Gemini, перевіряємо наступну сумісну модель
        if is_gemini_voice and gemini_model_idx + 1 < len(gemini_tts_models):
            gemini_model_idx += 1
            next_model = gemini_tts_models[gemini_model_idx]
            log_callback(f"  🔄 У моделі {current_gemini_model} вичерпано ліміт. Автоматичне перемикання на наступну сумісну модель: {next_model}...")
            log_callback(f"  🎬 Повний перезапуск озвучки моделлю {next_model} для збереження єдиного голосу...")
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
