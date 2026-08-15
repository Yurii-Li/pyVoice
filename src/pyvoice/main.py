import sys
import os

# Додаємо src/ у sys.path, щоб імпорти завжди працювали автономно
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from pyvoice.ui.app import PyVoiceApp

def main():
    """Головна точка входу додатку PyVoice AI"""
    app = PyVoiceApp()
    app.mainloop()

if __name__ == "__main__":
    main()
