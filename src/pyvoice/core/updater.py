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

def download_update_file(
    download_url: str,
    target_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> None:
    """Завантажує файл релізу частинами з оновленням прогресу"""
    headers = {"User-Agent": "PyVoiceAI-Updater"}
    with requests.get(download_url, headers=headers, stream=True, timeout=180) as resp:
        resp.raise_for_status()
        total_length = int(resp.headers.get('content-length', 0))
        downloaded = 0

        with open(target_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=131072):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_length > 0:
                        progress_callback(downloaded, total_length)

def launch_updater_and_exit(new_exe_path: str, current_exe: str, pid: int) -> None:
    """
    Запускає надійний автономний батник у Windows cmd.exe,
    який очікує завершення процесу PyVoiceAI, замінює EXE і запускає нову версію.
    """
    temp_dir = os.path.dirname(new_exe_path)
    bat_path = os.path.join(temp_dir, "run_update.bat")

    # Батник cmd.exe працює на будь-якому Windows без обмежень ExecutionPolicy чи блокувань PowerShell
    bat_script = f"""@echo off
setlocal
set "PID={pid}"
set "OLD_EXE={current_exe}"
set "NEW_EXE={new_exe_path}"
set "TMP_DIR={temp_dir}"

:: 1. Чекаємо поки старий процес завершиться
:WAIT_LOOP
tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto WAIT_LOOP
)

:: Коротка пауза, щоб Windows повністю звільнила дескриптор файлу
timeout /t 1 /nobreak >nul

:: 2. Заміна старого файлу новим із повторними спробами
:COPY_LOOP
copy /y "%NEW_EXE%" "%OLD_EXE%" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto COPY_LOOP
)

:: 3. Запуск оновленої програми
start "" "%OLD_EXE%"

:: 4. Очищення тимчасових файлів
del /f /q "%NEW_EXE%" >nul 2>&1
(goto) 2>nul & del "%~f0"
exit
"""

    with open(bat_path, "w", encoding="cp1251") as f:
        f.write(bat_script)

    # Запускаємо cmd.exe повністю від'єднаним від поточного процесу (CREATE_NEW_PROCESS_GROUP + DETACHED)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=flags,
        close_fds=True
    )

    # Миттєвий вихід з процесу на рівні ядра ОС
    os._exit(0)
