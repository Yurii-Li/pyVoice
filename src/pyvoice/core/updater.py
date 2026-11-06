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
    is_setup: bool

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
    """
    Перевіряє наявність новішого релізу на GitHub Releases.
    Надає перевагу офіційному інсталятору Inno Setup (PyVoiceAI-Setup.exe).
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

    # Шукаємо спочатку Setup інсталятор (Inno Setup), якщо немає — звичайний .exe
    setup_asset = None
    fallback_exe = None

    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            if "setup" in name.lower():
                setup_asset = asset
                break
            elif not fallback_exe:
                fallback_exe = asset

    chosen = setup_asset or fallback_exe
    download_url = chosen.get("browser_download_url") if chosen else None
    asset_name = chosen.get("name") if chosen else None
    asset_size = chosen.get("size", 0) if chosen else 0
    is_setup = "setup" in (asset_name or "").lower()

    return UpdateInfo(
        has_update=has_update,
        current_version=current_version,
        latest_version=latest_tag,
        release_notes=release_notes,
        download_url=download_url,
        asset_name=asset_name,
        asset_size=asset_size,
        is_setup=is_setup
    )

def download_update_file(
    download_url: str,
    target_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> None:
    """Завантажує файл оновлення частинами з відстеженням прогресу"""
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

def launch_installer_and_exit(installer_path: str) -> None:
    """
    Запускає офіційний Inno Setup інсталятор у тихому режимі:
    Inno Setup автоматично:
    1. Закриває старий процес PyVoiceAI (Restart Manager)
    2. Оновлює файли та ярлики у {localappdata}\\Programs\\PyVoice AI
    3. Автоматично запускає оновлену програму
    """
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    # Запускаємо Inno Setup з прапорцями тихого оновлення та закриття старих процесів
    cmd = [installer_path, "/SILENT", "/CLOSEAPPLICATIONS"]

    subprocess.Popen(
        cmd,
        creationflags=flags,
        close_fds=True
    )

    # Завершуємо поточну програму
    os._exit(0)
