import os
import sys

# Додаємо src/ у шлях пошуку модулів
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from pyvoice.main import main

if __name__ == "__main__":
    main()
