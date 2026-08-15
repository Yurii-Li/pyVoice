import os
import sys

def get_project_root() -> str:
    """Повертає кореневу директорію проєкту"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # 3 рівні вгору від utils/paths.py -> src/pyvoice/utils/paths.py -> root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", "..", ".."))

def get_bin_path(exe_name: str) -> str:
    """Отримує шлях до бінарного файлу (ffmpeg, ffprobe) для розробки або у зібраному .exe"""
    if getattr(sys, 'frozen', False):
        # PyInstaller розпаковує в _MEIPASS
        bundled_bin = os.path.join(sys._MEIPASS, "bin", exe_name)
        if os.path.exists(bundled_bin):
            return bundled_bin
        return exe_name
    else:
        # У режимі розробки шукаємо в root/bin/
        root_dir = get_project_root()
        local_bin = os.path.join(root_dir, "bin", exe_name)
        if os.path.exists(local_bin):
            return local_bin
        return exe_name
