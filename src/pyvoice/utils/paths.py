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
    """Отримує абсолютний шлях до бінарного файлу (ffmpeg, ffprobe, whisper-cli, ggml-моделей)"""
    if getattr(sys, 'frozen', False):
        bundled_bin = os.path.join(sys._MEIPASS, "bin", exe_name)
        if os.path.exists(bundled_bin):
            return bundled_bin
        return os.path.join(get_project_root(), "bin", exe_name)
    else:
        root_dir = get_project_root()
        local_bin = os.path.join(root_dir, "bin", exe_name)
        return local_bin
