import os
import subprocess
import sys
import tempfile
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from pyvoice.utils.paths import get_bin_path
from pyvoice.utils.time_parser import parse_time_to_seconds
from pyvoice.core.video import get_media_duration_seconds

@dataclass
class TimelineClip:
    """Описує фрагмент відео на таймлайні"""
    file_path: str
    start_sec: float
    end_sec: float
    
    @property
    def duration(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)
    
    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path)

def extract_audio_track(video_path: str, output_wav_path: str) -> bool:
    """Швидко видобуває аудіодоріжку у PCM WAV для синхронізованого відтворення в плеєрі"""
    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        output_wav_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
    return res.returncode == 0 and os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0

def merge_videos(
    video_paths: List[str], 
    output_path: str, 
    log_callback: Callable[[str], None] = print
) -> None:
    """Склеює список відеофайлів в один"""
    if len(video_paths) < 2:
        raise ValueError("Для склеювання потрібно обрати щонайменше 2 відеофайли.")

    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    temp_dir = tempfile.mkdtemp()
    concat_list_path = os.path.join(temp_dir, "concat_list.txt")

    try:
        log_callback(f"🔗 Склеювання {len(video_paths)} відеофайлів...")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for p in video_paths:
                normalized = os.path.abspath(p).replace("\\", "/")
                f.write(f"file '{normalized}'\n")

        cmd_copy = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        res = subprocess.run(cmd_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        
        if res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            log_callback("  ℹ️ Формати відео відрізняються, виконується ре-енкод сумісності...")
            cmd_reencode = [
                ffmpeg_exe, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac",
                output_path
            ]
            subprocess.run(cmd_reencode, check=True, creationflags=creationflags)

        log_callback(f"✅ Відео успішно склеєно:\n{output_path}")

    finally:
        try:
            if os.path.exists(concat_list_path):
                os.remove(concat_list_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

def trim_video(
    input_path: str, 
    start_time: str, 
    end_time: str, 
    output_path: str, 
    log_callback: Callable[[str], None] = print
) -> None:
    """Обрізає відео (залишає діапазон від start_time до end_time)"""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Файл не знайдено: {input_path}")

    start_sec = parse_time_to_seconds(start_time)
    end_sec = parse_time_to_seconds(end_time)

    if end_sec <= start_sec:
        raise ValueError("Час кінця повинен бути більшим за час початку.")

    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    log_callback(f"✂️ Обрізка відео від {start_time} до {end_time}...")

    cmd = [
        ffmpeg_exe, "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", input_path,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True, creationflags=creationflags)
    log_callback(f"✅ Обрізку завершено:\n{output_path}")

def cut_out_middle_segment(
    input_path: str, 
    cut_start_time: str, 
    cut_end_time: str, 
    output_path: str, 
    log_callback: Callable[[str], None] = print
) -> None:
    """Вирізає невдалий фрагмент посередині та зшиває відео"""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Файл не знайдено: {input_path}")

    total_duration = get_media_duration_seconds(input_path)
    cut_start = parse_time_to_seconds(cut_start_time)
    cut_end = parse_time_to_seconds(cut_end_time)

    if cut_end <= cut_start:
        raise ValueError("Кінець вирізання повинен бути більшим за початок.")

    if cut_start <= 0:
        return trim_video(input_path, cut_end_time, str(total_duration), output_path, log_callback)

    if cut_end >= total_duration:
        return trim_video(input_path, "00:00", cut_start_time, output_path, log_callback)

    temp_dir = tempfile.mkdtemp()
    part1_path = os.path.join(temp_dir, "part1.mp4")
    part2_path = os.path.join(temp_dir, "part2.mp4")

    try:
        log_callback(f"✂️ Видалення невдалого дублю з {cut_start_time} по {cut_end_time}...")
        trim_video(input_path, "00:00", cut_start_time, part1_path, lambda msg: None)
        trim_video(input_path, cut_end_time, str(total_duration), part2_path, lambda msg: None)
        merge_videos([part1_path, part2_path], output_path, log_callback)
        log_callback(f"✅ Фрагмент вирізано, відео зшито:\n{output_path}")

    finally:
        try:
            if os.path.exists(part1_path):
                os.remove(part1_path)
            if os.path.exists(part2_path):
                os.remove(part2_path)
            os.rmdir(temp_dir)
        except Exception:
            pass

def export_timeline_clips(
    clips: List[TimelineClip], 
    output_path: str, 
    log_callback: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> None:
    """
    Рендерить усі фрагменти з візуального таймлайну з детальним прогресом
    та зшиває їх в одне бездоганне відео.
    """
    if not clips:
        raise ValueError("Таймлайн порожній. Додайте хоча б одне відео.")

    ffmpeg_exe = get_bin_path("ffmpeg.exe")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    temp_dir = tempfile.mkdtemp()
    segment_files = []

    try:
        total_clips = len(clips)
        total_steps = total_clips + (1 if total_clips > 1 else 0)
        log_callback(f"🎬 Рендер таймлайну ({total_clips} фрагментів)...")

        for idx, clip in enumerate(clips):
            msg = f"Нарізка фрагменту {idx+1}/{total_clips} ({clip.file_name})..."
            log_callback(f"  {msg}")
            if progress_callback:
                progress_callback(idx + 1, total_steps, msg)
                
            chunk_file = os.path.join(temp_dir, f"tchunk_{idx}.mp4")
            cmd = [
                ffmpeg_exe, "-y",
                "-ss", str(clip.start_sec),
                "-to", str(clip.end_sec),
                "-i", clip.file_path,
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac",
                chunk_file
            ]
            subprocess.run(cmd, check=True, creationflags=creationflags)
            segment_files.append(chunk_file)

        if len(segment_files) == 1:
            if os.path.exists(output_path):
                os.remove(output_path)
            os.replace(segment_files[0], output_path)
        else:
            if progress_callback:
                progress_callback(total_steps, total_steps, "Склеювання фінального відео...")
            merge_videos(segment_files, output_path, log_callback)

        if progress_callback:
            progress_callback(total_steps, total_steps, "Експорт завершено успішно!")
        log_callback(f"🎉 Змонтоване відео успішно експортовано:\n{output_path}")

    finally:
        try:
            for s in segment_files:
                if os.path.exists(s):
                    os.remove(s)
            os.rmdir(temp_dir)
        except Exception:
            pass
