"""Запускает все шаги проекта по порядку: данные, подготовка, проверка отраслей, SQL, графики."""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent / "scripts"
STEPS = ["01_download_data.py", "02_prepare.py", "03_check_industry.py", "04_run_sql.py", "05_plots.py"]

for step in STEPS:
    print(f"\n===== {step} =====", flush=True)
    # sys.executable — тот же Python, которым запущен этот файл (из .venv)
    subprocess.run([sys.executable, str(SCRIPTS / step)], check=True)
