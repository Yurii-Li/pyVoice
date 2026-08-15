import json
import asyncio
import os
import subprocess
import edge_tts

VOICE = "uk-UA-OstapNeural"  # або "uk-UA-PolinaNeural"
INPUT_VIDEO = "input_video.mp4"
OUTPUT_VIDEO = "output_synced_freeze.mp4"

def parse_time_to_seconds(time_str: str) -> float:
    """Конвертує 'MM:SS' у секунди"""
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    elif len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    return 0.0

def get_duration_seconds(file_path: str) -> float:
    """Отримує точну тривалість відео або аудіо"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())

async def generate_speech_chunks(items):
    os.makedirs("temp_process", exist_ok=True)
    print("🎙 1. Генерація аудіофрагментів...")
    for idx, item in enumerate(items):
        audio_path = os.path.join("temp_process", f"audio_{idx}.mp3")
        communicate = edge_tts.Communicate(item["text"], VOICE)
        await communicate.save(audio_path)
        item["audio_path"] = audio_path
        item["audio_duration"] = get_duration_seconds(audio_path)
    print("✅ Усі фрази озвучено!")

def process_video_and_sync(items, input_video, output_video):
    total_video_len = get_duration_seconds(input_video)
    concat_list_path = os.path.join("temp_process", "concat_list.txt")
    
    print("🎬 2. Нарізка відео, створення стоп-кадрів та зведення...")
    
    segment_files = []
    
    for idx, item in enumerate(items):
        start_sec = parse_time_to_seconds(item["start"])
        # Визначаємо кінець відрізка у вихідному відео
        if idx + 1 < len(items):
            end_sec = parse_time_to_seconds(items[idx + 1]["start"])
        else:
            end_sec = total_video_len
            
        video_clip_duration = max(0.1, end_sec - start_sec)
        audio_len = item["audio_duration"] + 0.3  # 0.3 сек пауза після репліки
        
        chunk_video_raw = os.path.join("temp_process", f"vchunk_{idx}.mp4")
        
        # Вирізаємо відеосегмент
        cut_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", input_video,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-an", chunk_video_raw
        ]
        subprocess.run(cut_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        chunk_final = os.path.join("temp_process", f"segment_{idx}.mp4")
        
        # Якщо озвучка довша за дію на відео — заморожуємо останній кадр (tpad)
        if audio_len > video_clip_duration:
            freeze_sec = audio_len - video_clip_duration
            filter_str = f"tpad=stop_mode=clone:stop_duration={freeze_sec:.2f}"
            
            cmd = [
                "ffmpeg", "-y",
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
            # Якщо відео довше за аудіо — залишаємо як є
            cmd = [
                "ffmpeg", "-y",
                "-i", chunk_video_raw,
                "-i", item["audio_path"],
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "libx264", "-c:a", "aac",
                chunk_final
            ]
            
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        segment_files.append(chunk_final)

    # 3. Склеюємо всі фрагменти разом
    print("🔗 3. Фінальне склеювання сегментів...")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for seg in segment_files:
            # Для FFmpeg concat потрібні прямі слеші
            normalized_path = os.path.abspath(seg).replace("\\", "/")
            f.write(f"file '{normalized_path}'\n")

    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_video
    ]
    subprocess.run(concat_cmd, check=True)
    print(f"🎉 Готово! Ідеально синхронізоване відео зі стоп-кадрами: {output_video}")

async def main():
    if not os.path.exists(INPUT_VIDEO):
        print(f"❌ Помилка: Покладіть файл '{INPUT_VIDEO}' у папку зі скриптом!")
        return

    with open("subtitles.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    await generate_speech_chunks(data)
    process_video_and_sync(data, INPUT_VIDEO, OUTPUT_VIDEO)

if __name__ == "__main__":
    asyncio.run(main())