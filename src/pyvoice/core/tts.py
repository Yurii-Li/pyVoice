import os
import edge_tts
from typing import List, Dict, Callable
from pyvoice.core.video import get_media_duration_seconds

async def generate_speech_chunks(
    items: List[Dict[str, str]], 
    voice: str, 
    temp_dir: str, 
    log_callback: Callable[[str], None]
) -> None:
    """Генерує аудіофайли для кожної репліки через Edge TTS"""
    os.makedirs(temp_dir, exist_ok=True)
    log_callback("🎙 1. Генерація аудіофрагментів диктора...")
    
    total = len(items)
    for idx, item in enumerate(items):
        log_callback(f"  Озвучування репліки {idx+1}/{total} (таймкод {item['start']}): \"{item['text'][:30]}...\"")
        audio_path = os.path.join(temp_dir, f"audio_{idx}.mp3")
        communicate = edge_tts.Communicate(item["text"], voice)
        await communicate.save(audio_path)
        item["audio_path"] = audio_path
        item["audio_duration"] = get_media_duration_seconds(audio_path)
        
    log_callback("✅ Усі репліки успішно озвучено!")
