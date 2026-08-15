import os
import sys

# Додаємо src/ у шлях пошуку модулів
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

def start():
    """Точка запуску додатку"""
    from pyvoice.main import main
    main()

if __name__ == "__main__":
    if "--reload" in sys.argv:
        try:
            import hupper
            # Офіційний reloader від hupper для десктопних застосунків
            reloader = hupper.start_reloader("run.start")
        except ImportError:
            print("⚠️ Пакунок 'hupper' не знайдено, запускаємо у звичайному режимі...")
            start()
    else:
        start()
