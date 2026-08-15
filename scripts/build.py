import os
import urllib.request
import zipfile
import subprocess
import sys
import shutil

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(ROOT_DIR, "bin")
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
ZIP_FILE = os.path.join(ROOT_DIR, "ffmpeg.zip")

def download_binaries():
    if not os.path.exists(BIN_DIR):
        os.makedirs(BIN_DIR)
        
    ffmpeg_exe = os.path.join(BIN_DIR, "ffmpeg.exe")
    ffprobe_exe = os.path.join(BIN_DIR, "ffprobe.exe")
    
    # Очищуємо старі/зайві файли, якщо були
    for fname in os.listdir(BIN_DIR):
        if fname.startswith("ggml") or fname.startswith("whisper") or fname.startswith("parakeet") or fname.startswith("SDL2"):
            try:
                os.remove(os.path.join(BIN_DIR, fname))
            except Exception:
                pass

    # Завантаження FFmpeg
    if not (os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe)):
        print("⏳ Завантаження FFmpeg...")
        urllib.request.urlretrieve(FFMPEG_URL, ZIP_FILE)
        print("📦 Розпакування FFmpeg...")
        with zipfile.ZipFile(ZIP_FILE, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('ffmpeg.exe'):
                    file_info.filename = 'ffmpeg.exe'
                    zip_ref.extract(file_info, BIN_DIR)
                elif file_info.filename.endswith('ffprobe.exe'):
                    file_info.filename = 'ffprobe.exe'
                    zip_ref.extract(file_info, BIN_DIR)
        if os.path.exists(ZIP_FILE):
            os.remove(ZIP_FILE)
        print("✅ FFmpeg завантажено.")
    else:
        print("✅ FFmpeg вже наявний.")

def build_exe():
    print("🔨 Початок збірки .exe файлу за допомогою PyInstaller...")
    
    # Закриваємо попередньо запущений процес PyVoiceAI перед перезаписом
    if sys.platform == "win32":
        subprocess.run(
            ["powershell", "-Command", "Stop-Process -Name PyVoiceAI -Force -ErrorAction SilentlyContinue"],
            capture_output=True
        )
    
    # Видаляємо старі папки збірки
    shutil.rmtree(os.path.join(ROOT_DIR, "build"), ignore_errors=True)
    shutil.rmtree(os.path.join(ROOT_DIR, "dist"), ignore_errors=True)
    
    # Автоматично використовуємо локальний .venv Python, якщо він існує
    python_exe = sys.executable
    venv_python = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        python_exe = venv_python
    
    entry_point = os.path.join(ROOT_DIR, "run.py")
    src_path = os.path.join(ROOT_DIR, "src")
    
    cmd = [
        python_exe, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "PyVoiceAI",
        "--paths", src_path,
        "--add-data", f"{BIN_DIR}{os.pathsep}bin",
        "--collect-all", "edge_tts",
        entry_point
    ]
    
    subprocess.run(cmd, check=True, cwd=ROOT_DIR)
    print("\n🎉 Збірка успішно завершена! Ваш файл PyVoiceAI.exe знаходиться у папці 'dist'.")

if __name__ == "__main__":
    download_binaries()
    build_exe()
