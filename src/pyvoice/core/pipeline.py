import os
import json
import shutil
from typing import Union, List, Dict, Callable
from pyvoice.core.tts import generate_speech_chunks
from pyvoice.core.video import process_video_and_sync
from pyvoice.utils.paths import get_project_root

TEMP_DIR_NAME = "temp_process"

async def run_voiceover_pipeline(
    input_video: str, 
    items_or_file: Union[str, List[Dict[str, str]]], 
    output_video: str, 
    voice: str, 
    log_callback: Callable[[str], None]
) -> None:
    """Головний пайплайн: перетворює сценарій у голос, монтує відео та очищує сміття"""
    temp_dir = os.path.join(get_project_root(), TEMP_DIR_NAME)
    try:
        if isinstance(items_or_file, str):
            with open(items_or_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = items_or_file
            
        await generate_speech_chunks(data, voice, temp_dir, log_callback)
        process_video_and_sync(data, input_video, output_video, temp_dir, log_callback)
        
        log_callback("🧹 Очищення тимчасових файлів...")
        shutil.rmtree(temp_dir, ignore_errors=True)
        log_callback("✅ Процес успішно завершено!")
        
    except Exception as e:
        log_callback(f"❌ Помилка: {str(e)}")
        raise
