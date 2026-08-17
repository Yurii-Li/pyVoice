import os
import subprocess
import sys
from typing import List, Dict, Callable
from pyvoice.utils.paths import get_bin_path
from pyvoice.utils.time_parser import parse_time_to_seconds

def get_media_duration_seconds(file_path: str) -> float:
    """Визначає тривалість аудіо або відеофайлу в секундах через ffprobe"""
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

def process_video_and_sync(
    items: List[Dict[str, any]], 
    input_video: str, 
    output_video: str, 
    temp_dir: str, 
    log_callback: Callable[[str], None]
) -> None:
    """
    Нарізає відео, додає стоп-кадри при потребі та склеює синхронізоване відео.
    Гарантує 100% збереження хронометражу та ідеальну синхронізацію звуку з відеорядом.
    """
    total_video_len = get_media_duration_seconds(input_video)
    concat_list_path = os.path.join(temp_dir, "concat_list.txt")
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
        
        # Для початкового сегмента (якщо таймкод на самому початку відео) додаємо 0.5с м'якої затримки (adelay=500|500)
        is_first_start = (idx == 0 or start_sec < 0.5)
        initial_audio_delay = 0.5 if is_first_start else 0.0
        
        raw_audio_duration = float(item["audio_duration"])
        effective_audio_duration = raw_audio_duration + initial_audio_delay
        
        # Фінальна тривалість сегмента: не менша за оригінальне відео, і достатня для повної озвучки + мікропауза 0.2с
        final_seg_duration = max(video_clip_duration, effective_audio_duration + 0.2)
        
        chunk_video_raw = os.path.join(temp_dir, f"vchunk_{idx}.mp4")
        
        # Вирізаємо чистий відеофрагмент оригінальної тривалості
        cut_cmd = [
            ffmpeg_exe, "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", input_video,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-an", chunk_video_raw
        ]
        subprocess.run(cut_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
        
        chunk_final = os.path.join(temp_dir, f"segment_{idx}.mp4")
        
        # Формуємо фільтри для точної синхронізації
        video_filters = []
        audio_filters = []
        
        if is_first_start:
            audio_filters.append("adelay=500|500")
            
        # Якщо диктор говорить довше, ніж триває сцена на відео — заморожуємо останній кадр
        if final_seg_duration > video_clip_duration + 0.05:
            freeze_sec = final_seg_duration - video_clip_duration
            video_filters.append(f"tpad=stop_mode=clone:stop_duration={freeze_sec:.3f}")
            
        # Доповнюємо аудіо тишею до повної тривалості відео (щоб потоки мали рівну тривалість)
        audio_filters.append("apad")
            
        # Збираємо сегмент із фіксованим хронометражем
        cmd = [ffmpeg_exe, "-y", "-i", chunk_video_raw, "-i", item["audio_path"]]
        filter_parts = []
        
        if video_filters:
            filter_parts.append(f"[0:v]{','.join(video_filters)}[v]")
            map_v = "[v]"
        else:
            map_v = "0:v"
            
        if audio_filters:
            filter_parts.append(f"[1:a]{','.join(audio_filters)}[a]")
            map_a = "[a]"
        else:
            map_a = "1:a"
            
        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts)])
            
        cmd.extend([
            "-map", map_v,
            "-map", map_a,
            "-c:v", "libx264", "-c:a", "aac",
            "-t", f"{final_seg_duration:.3f}",
            chunk_final
        ])
            
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
