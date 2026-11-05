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
    Завантажує новий EXE у тимчасовий файл і запускає процес заміни та перезапуску.
    """
    if not getattr(sys, 'frozen', False):
        raise RuntimeError("Оновлення EXE доступне лише у зібраній версії програми (.exe). У режимі розробки використовуйте git pull.")

    current_exe = os.path.abspath(sys.executable)
    exe_dir = os.path.dirname(current_exe)
    temp_dir = tempfile.mkdtemp(prefix="pyvoice_update_")
    new_exe_path = os.path.join(temp_dir, "PyVoiceAI_new.exe")

    # 1. Завантаження файлу частинами з відстеженням прогресу
    headers = {"User-Agent": "PyVoiceAI-Updater"}
    with requests.get(download_url, headers=headers, stream=True, timeout=120) as resp:
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

    # 2. Надійний скрипт оновлення PowerShell
    # Використовує Wait-Process для гарантованого очікування завершення старого процесу
    pid = os.getpid()
    ps1_path = os.path.join(temp_dir, "update.ps1")
    
    ps_script = f"""
$ErrorActionPreference = 'SilentlyContinue'
# Чекаємо повного закриття процесу PyVoiceAI
Wait-Process -Id {pid} -Timeout 10
Start-Sleep -Seconds 1

# Замінюємо старий exe оновленим
$retries = 0
while ($retries -lt 10) {{
    try {{
        Copy-Item -Path '{new_exe_path}' -Destination '{current_exe}' -Force
        break
    }} catch {{
        Start-Sleep -Seconds 1
        $retries++
    }}
}}

# Запускаємо оновлений додаток
Start-Process -FilePath '{current_exe}'

# Прибираємо тимчасові файли
Start-Sleep -Seconds 2
Remove-Item -Path '{temp_dir}' -Recurse -Force
"""

    with open(ps1_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    # 3. Запуск PowerShell у фоновому автономному процесі
    subprocess.Popen(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", ps1_path],
        creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
    )

    # 4. Примусове та миттєве закриття поточної програми, щоб звільнити файл .exe
    os._exit(0)
