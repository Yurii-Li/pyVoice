import os
import sys
import subprocess
import tempfile
import requests
from typing import Optional, Tuple, Callable
from dataclasses import dataclass

GITHUB_OWNER = "Yurii-Li"
GITHUB_REPO = "pyVoice"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

@dataclass
class UpdateInfo:
    has_update: bool
    current_version: str
    latest_version: str
    release_notes: str
    download_url: Optional[str]
    asset_name: Optional[str]
    asset_size: int

def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Конвертує версію 'v1.4.0' у кортеж чисел (1, 4, 0) для коректного порівняння"""
    clean = v_str.strip().lstrip("vV")
    parts = []
    for chunk in clean.split("."):
        digits = "".join(filter(str.isdigit, chunk))
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    return tuple(parts)

def check_for_updates(current_version: str) -> UpdateInfo:
    """
    Перевіряє наявність новішого релізу на GitHub Releases.
    Повертає об'єкт UpdateInfo з посиланням на EXE та списком змін.
    """
    headers = {"User-Agent": "PyVoiceAI-Updater"}
    res = requests.get(GITHUB_API_LATEST, headers=headers, timeout=10)
    if res.status_code != 200:
        raise RuntimeError(f"Не вдалося отримати дані з GitHub (HTTP {res.status_code})")

    data = res.json()
    latest_tag = data.get("tag_name", "").strip()
    release_notes = data.get("body", "").strip()

    curr_tuple = parse_version_tuple(current_version)
    latest_tuple = parse_version_tuple(latest_tag)

    has_update = latest_tuple > curr_tuple

    download_url = None
    asset_name = None
    asset_size = 0

    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            download_url = asset.get("browser_download_url")
            asset_name = name
            asset_size = asset.get("size", 0)
            break

    return UpdateInfo(
        has_update=has_update,
        current_version=current_version,
        latest_version=latest_tag,
        release_notes=release_notes,
        download_url=download_url,
        asset_name=asset_name,
        asset_size=asset_size
    )

def download_and_apply_update(
    download_url: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> None:
    """
    Завантажує новий EXE у тимчасовий файл і запускає процес безшовної заміни та перезапуску.
    """
    if not getattr(sys, 'frozen', False):
        raise RuntimeError("Оновлення EXE доступне лише у зібраній версії програми (.exe). У режимі розробки використовуйте git pull.")

    current_exe = os.path.abspath(sys.executable)
    temp_dir = tempfile.mkdtemp(prefix="pyvoice_update_")
    new_exe_path = os.path.join(temp_dir, "PyVoiceAI_new.exe")

    # 1. Завантаження файлу частинами з прогресом
    headers = {"User-Agent": "PyVoiceAI-Updater"}
    with requests.get(download_url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total_length = int(resp.headers.get('content-length', 0))
        downloaded = 0

        with open(new_exe_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_length > 0:
                        progress_callback(downloaded, total_length)

    # 2. Створення батника для заміни та перезапуску програми
    # Оскільки запущений EXE заблокований ОС Windows, батник чекає на закриття процесу,
    # замінює старий EXE новим, запускає оновлений додаток і самознищується.
    bat_path = os.path.join(temp_dir, "apply_update.bat")
    
    bat_content = f"""@echo off
setlocal
set "OLD_EXE={current_exe}"
set "NEW_EXE={new_exe_path}"
set "TEMP_DIR={temp_dir}"

:: Чекаємо 1.5 секунди до повного виходу старого процесу
timeout /t 2 /nobreak >nul

:RETRY_MOVE
move /y "%NEW_EXE%" "%OLD_EXE%" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto RETRY_MOVE
)

:: Запуск оновленої програми
start "" "%OLD_EXE%"

:: Очищення тимчасової папки та батника
rmdir /s /q "%TEMP_DIR%" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""

    with open(bat_path, "w", encoding="cp1251") as f:
        f.write(bat_content)

    # 3. Запуск батника у фоні без консольного вікна
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=creationflags)

    # 4. Завершення поточної програми
    sys.exit(0)
