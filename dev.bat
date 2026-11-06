@echo off
chcp 65001 >nul
echo 🚀 Запуск PyVoice AI у режимі розробки з автоперезавантаженням (hupper)...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py --reload
) else (
    python run.py --reload
)
pause
