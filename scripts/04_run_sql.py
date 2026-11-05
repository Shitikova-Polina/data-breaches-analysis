"""Шаг 4. Выполняем SQL-запросы из sql/queries.sql и сохраняем ответы.

Каждый запрос в файле начинается со строки-маркера «name»...
Делим файл по этим строкам, выполняем запросы по очереди и сохраняем
результат каждого в results/sql_<имя>.csv.
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SQL_FILE = ROOT / "sql" / "queries.sql"
RESULTS = ROOT / "results"

pd.set_option("display.width", 160)
con = sqlite3.connect(ROOT / "data" / "breaches.db")

# Режем файл на куски по маркеру «-- name:». Первый кусок — шапка, пропускаем.
chunks = SQL_FILE.read_text(encoding="utf-8").split("-- name:")[1:]
for chunk in chunks:
    name, query = chunk.split("\n", 1)
    name = name.strip()
    result = pd.read_sql(query, con)
    result.to_csv(RESULTS / f"sql_{name}.csv", index=False)
    print(f"\n===== {name} =====")
    print(result.to_string(index=False))

con.close()
