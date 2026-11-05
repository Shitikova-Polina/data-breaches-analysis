"""Шаг 3. Проверяем правило отраслей вручную.

Я взяла 50 случайных утечек (pandas sample, random_state=2026), прочитала
описание каждой и сама записала отрасль в data/industry_manual_check.csv.
Скрипт сравнивает ручную разметку с автоматической и считает, как часто
они совпадают. Так видно, насколько можно доверять графику по отраслям.
"""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(ROOT / "data" / "breaches.db")
auto = pd.read_sql("SELECT title, industry FROM breaches", con)
con.close()

manual = pd.read_csv(ROOT / "data" / "industry_manual_check.csv")
check = manual.merge(auto, on="title", how="left")
check["match"] = check["manual_industry"] == check["industry"]

# Отдельно смотрим на утечки, которым правило дало отрасль (не «Другое»)
classified = check[check["industry"] != "Другое"]
lines = [
    f"Проверено вручную: {len(check)} утечек",
    f"Совпало с ручной разметкой всего: {check['match'].sum()} из {len(check)} ({check['match'].mean():.0%})",
    f"Правило дало отрасль (не «Другое»): {len(classified)}, из них верно: "
    f"{classified['match'].sum()} ({classified['match'].mean():.0%})",
    f"Правило дало «Другое», а вручную отрасль понятна: "
    f"{((check['industry'] == 'Другое') & (check['manual_industry'] != 'Другое')).sum()}",
    "",
    "Расхождения:",
    check.loc[~check["match"], ["title", "industry", "manual_industry"]].to_string(index=False),
]
text = "\n".join(lines) + "\n"
(ROOT / "results" / "02_industry_check.txt").write_text(text, encoding="utf-8")
print(text)
