import os
import sys
import time
import subprocess

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
RUN_SCRIPT = os.path.join(ROOT_DIR, "run.py")

def get_python_exe():
    venv_python = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable

def get_files_mtime():
    """Збирає час останньої модифікації всіх .py файлів у проєкті"""
    mtimes = {}
    for root, _, files in os.walk(SRC_DIR):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    mtimes[path] = os.path.getmtime(path)
                except Exception:
                    pass
    if os.path.exists(RUN_SCRIPT):
        mtimes[RUN_SCRIPT] = os.path.getmtime(RUN_SCRIPT)
    return mtimes

def run_dev_server():
    python_exe = get_python_exe()
    print("🔥 [Hot Reload Dev Mode] Запуск PyVoice AI...")
    print("👀 Відстеження змін у файлах src/ (при Ctrl+S вікно перезапуститься автоматично)")
    print("🛑 Щоб зупинити — натисніть Ctrl+C у цьому терміналі.\n")

    process = None
    last_mtimes = get_files_mtime()

    def start_app():
        return subprocess.Popen([python_exe, RUN_SCRIPT], cwd=ROOT_DIR)

    process = start_app()

    try:
        while True:
            time.sleep(0.5)
            
            # Якщо додаток закрив сам користувач — не перезапускаємо автоматично
            if process.poll() is not None:
                # Перевіряємо чи була зміна файлу після закриття
                current_mtimes = get_files_mtime()
                if current_mtimes != last_mtimes:
                    last_mtimes = current_mtimes
                    print("\n♻️ Виявлено збереження коду! Перезапуск вікна...")
                    process = start_app()
                continue

            current_mtimes = get_files_mtime()
            if current_mtimes != last_mtimes:
                last_mtimes = current_mtimes
                print("\n♻️ [Hot Reload] Збережено файл! Перезапуск програми...")
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                process = start_app()

    except KeyboardInterrupt:
        print("\n👋 Зупинка режиму розробки.")
        if process and process.poll() is None:
            process.terminate()

if __name__ == "__main__":
    run_dev_server()
