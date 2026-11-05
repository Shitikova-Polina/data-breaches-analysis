"""Шаг 5. Графики по результатам SQL-запросов. Сохраняются в figures/."""
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # рисуем в файл, без окна
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

BLUE = "#2a78d6"
GREY = "#8a8984"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "text.color": "#0b0b0b",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e8e7e3", "font.size": 10,
})

# Русские подписи для самых частых типов данных
RU = {
    "Email addresses": "Email", "Passwords": "Пароли", "Names": "Имена",
    "Usernames": "Логины", "IP addresses": "IP-адреса", "Phone numbers": "Телефоны",
    "Physical addresses": "Почтовые адреса", "Dates of birth": "Даты рождения",
    "Genders": "Пол", "Geographic locations": "Местоположение", "Purchases": "Покупки",
    "Website activity": "Активность на сайте", "Job titles": "Должности",
    "Social media profiles": "Профили в соцсетях", "Employers": "Работодатели",
}

# ---------- График 1. Утечки по годам ----------
by_year = pd.read_csv(RESULTS / "sql_02_by_year.csv")
fig, ax = plt.subplots(figsize=(9, 4.5))
# Последние 3 года рисуем серым: часть их утечек станет известна позже
colors = [GREY if y >= 2024 else BLUE for y in by_year["year"]]
ax.bar(by_year["year"], by_year["breaches"], color=colors, width=0.75)
ax.set_xticks(by_year["year"], by_year["year"], rotation=45)
ax.set_ylabel("Число утечек")
ax.set_title("1. Утечки в списке HIBP по году, когда утечка произошла")
# Средняя задержка между утечкой и её появлением в HIBP (из запроса 09)
lag = pd.read_csv(RESULTS / "sql_09_disclosure_lag.csv")
avg_lag = (lag["avg_lag_days"] * lag["breaches"]).sum() / lag["breaches"].sum()
ax.text(2006.6, by_year["breaches"].max() * 0.97,
        f"серые годы ещё неполные: утечки попадают\nв HIBP в среднем через {avg_lag:.0f} дней",
        fontsize=9, color="#52514e", ha="left", va="top")
ax.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(FIG / "1_breaches_by_year.png", dpi=150)
plt.close(fig)

# ---------- График 2. Самые частые типы данных ----------
types = pd.read_csv(RESULTS / "sql_03_top_data_classes.csv").iloc[::-1]  # переворот: большие сверху
fig, ax = plt.subplots(figsize=(8, 5.5))
bars = ax.barh(types["data_class"].map(RU), types["pct_of_breaches"], color=BLUE, height=0.7)
ax.bar_label(bars, labels=[f"{v:.0f}%" for v in types["pct_of_breaches"]], padding=3, fontsize=9)
ax.set_xlabel("% утечек, в которых есть этот тип данных")
ax.set_title("2. Какие данные утекают чаще всего")
ax.set_xlim(0, 110)
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(FIG / "2_top_data_classes.png", dpi=150)
plt.close(fig)

# ---------- График 3. Отрасли ----------
ind = pd.read_csv(RESULTS / "sql_05_by_industry.csv").sort_values("breaches")
fig, ax = plt.subplots(figsize=(8, 5.5))
colors = [GREY if i == "Другое" else BLUE for i in ind["industry"]]
bars = ax.barh(ind["industry"], ind["breaches"], color=colors, height=0.7)
ax.bar_label(bars, padding=3, fontsize=9)
ax.set_xlabel("Число утечек")
ax.set_title("3. Утечки по отраслям (классификация по ключевым словам)")
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(FIG / "3_breaches_by_industry.png", dpi=150)
plt.close(fig)

# ---------- График 4. Какие типы утекают вместе ----------
# Берём 8 самых частых типов и для каждой пары считаем, в каком проценте
# утечек с типом из строки есть и тип из столбца.
con = sqlite3.connect(ROOT / "data" / "breaches.db")
pairs = pd.read_sql("""
    SELECT b.breach_id, dc.data_class
    FROM breach_data_classes AS b
    JOIN data_classes AS dc ON dc.class_id = b.class_id
""", con)
con.close()
top8 = list(types["data_class"].iloc[::-1][:8])  # 8 самых частых
# Таблица «утечка × тип»: 1, если тип есть в утечке
matrix = pd.crosstab(pairs["breach_id"], pairs["data_class"])[top8]
together = matrix.T @ matrix                      # сколько утечек содержит оба типа
share = together.div(np.diag(together), axis=0) * 100  # % от утечек с типом из строки
labels = [RU[t] for t in top8]
fig, ax = plt.subplots(figsize=(8, 6.5))
im = ax.imshow(share.values, cmap="Blues", vmin=0, vmax=100)
ax.set_xticks(range(8), labels, rotation=45, ha="right")
ax.set_yticks(range(8), labels)
ax.grid(False)
for i in range(8):
    for j in range(8):
        value = share.values[i, j]
        ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=9,
                color="white" if value > 60 else "#0b0b0b")
ax.set_title("4. Если утёк тип из строки, в каком % утечек\nесть и тип из столбца")
fig.colorbar(im, ax=ax, shrink=0.8, label="%")
fig.tight_layout()
fig.savefig(FIG / "4_data_classes_together.png", dpi=150)
plt.close(fig)

# ---------- График 5. Доля утечек с паролями по годам ----------
pw = pd.read_csv(RESULTS / "sql_07_passwords_share_by_year.csv")
pw = pw[pw["year"] >= 2011]  # до 2011 года утечек в списке 1–4 в год, проценты прыгают
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.plot(pw["year"], pw["pct_with_passwords"], color=BLUE, linewidth=2, marker="o", markersize=5)
for _, row in pw.iterrows():
    ax.annotate(f"{row['pct_with_passwords']:.0f}%", (row["year"], row["pct_with_passwords"]),
                textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8, color="#52514e")
ax.set_ylim(0, 110)
ax.set_xticks(pw["year"], pw["year"], rotation=45)
ax.set_ylabel("% утечек, где были пароли")
ax.set_title("5. Доля утечек с паролями по годам (с 2011 года)")
fig.tight_layout()
fig.savefig(FIG / "5_passwords_share_by_year.png", dpi=150)
plt.close(fig)

print("Графики сохранены в", FIG)
