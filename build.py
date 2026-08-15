import os
import subprocess
import sys

if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "build.py")
    subprocess.run([sys.executable, script_path], check=True)
