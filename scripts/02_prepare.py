"""Шаг 2. Готовим данные и загружаем их в базу SQLite.

1. Разбираем JSON: даты, числа, флаги.
2. Убираем утечки, которые HIBP пометил как поддельные (IsFabricated).
3. Относим каждый сервис к отрасли по ключевым словам (правило ниже).
4. «Разворачиваем» список типов данных: одна строка = одна утечка + один тип.
5. Складываем всё в базу data/breaches.db из трёх таблиц:
     breaches             — одна строка на утечку
     data_classes         — справочник типов данных (email, пароль, ...)
     breach_data_classes  — какие типы данных были в какой утечке
"""
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "breaches.json"
DB = ROOT / "data" / "breaches.db"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

log = []


def say(text):
    print(text)
    log.append(text)


# ---------- 1. Читаем JSON ----------
raw = json.loads(RAW.read_text(encoding="utf-8"))
df = pd.DataFrame(raw)
say(f"Утечек в списке HIBP: {len(df)}")

# ---------- 2. Убираем поддельные утечки ----------
# IsFabricated = HIBP считает, что данные, скорее всего, выдуманы
say(f"Помечены как поддельные (IsFabricated): {df['IsFabricated'].sum()} — убраны")
df = df[~df["IsFabricated"]].copy()

# Даты: из текста «2019-07-01» делаем настоящую дату
df["breach_date"] = pd.to_datetime(df["BreachDate"])
df["added_date"] = pd.to_datetime(df["AddedDate"]).dt.tz_localize(None)
df["breach_year"] = df["breach_date"].dt.year
say(f"Даты утечек: от {df['breach_date'].min():%Y-%m-%d} до {df['breach_date'].max():%Y-%m-%d}")
say(f"Пропуски: без домена {(df['Domain'] == '').sum()}, без даты {df['breach_date'].isna().sum()}, "
    f"без числа аккаунтов {df['PwnCount'].isna().sum()}")

# Текст описания приходит с HTML-тегами (<a href=...>), убираем их
df["description_text"] = df["Description"].apply(lambda s: re.sub(r"<[^>]+>", "", s))

# ---------- 3. Отрасль ----------
# В HIBP нет поля «отрасль». Почти каждое описание начинается так:
# «In 2019, the Russian Minecraft service VimeWorld suffered a data breach».
# Берём название утечки и первое предложение описания и ищем в них
# ключевые слова. Правила проверяются СВЕРХУ ВНИЗ: первое совпадение
# решает, поэтому узкие отрасли стоят выше широких.
# Слово ищется с начала слова: «game» найдёт «games» и «gaming»,
# но «app» не найдёт «happened». Знак $ в конце значит «слово целиком»
# («car$» найдёт «car», но не «card»).
INDUSTRY_RULES = [
    ("Сборники и спам-базы",   ["combolist", "combo list", "credential stuffing", "stealer log",
                                "spambot", "spam list", "collection #", "data enrichment",
                                "data aggregator", "data broker"]),
    # «dating» отдельно не берём: оно ловит фразу «dating back to» («начиная с»)
    ("Знакомства и 18+",       ["dating app", "dating site", "dating website", "dating service",
                                "dating platform", "online dating", "adult", "porn", "sex$", "escort", "hookup", "relationship",
                                "camming", "webcam", "affair", "fetish"]),
    ("Игры",                   ["game", "gaming", "minecraft", "esports", "e-sports", "mmo", "rpg$",
                                "cheat", "roblox", "runescape", "warcraft", "counter-strike"]),
    ("Финансы и криптовалюты", ["bank", "crypto", "bitcoin", "financ", "loan", "insurance",
                                "payment", "invest", "fintech", "cryptocurrency exchange"]),
    ("Медицина и здоровье",    ["health", "medical", "clinic", "pharma", "hospital", "fitness", "acne",
                                "diet", "wellness", "dental", "patient"]),
    ("Образование",            ["universit", "school", "education", "learning", "course", "student",
                                "college", "tutor", "academ"]),
    ("Госсектор",              ["government", "ministry", "municipal", "police", "city of", "council",
                                "federal", "military", "department"]),
    ("Магазины и e-commerce",  ["shop", "store", "retail", "e-commerce", "ecommerce", "marketplace",
                                "fashion", "clothing", "apparel", "seller", "merchant", "grocery",
                                "coupon", "auction"]),
    ("Путешествия и транспорт", ["travel", "hotel", "airline", "flight", "booking", "tourism", "car$",
                                 "cars$", "taxi", "transport", "rental", "vehicle", "automotive"]),
    ("СМИ и развлечения",      ["news", "magazine", "music", "video", "stream", "movie", "film", "anime",
                                "media", "radio", "podcast", "book$", "books$", "ebook", "comic", "entertainment", "photo",
                                "publish", "torrent", "tv$"]),
    ("Форумы и соцсети",       ["forum", "community", "social", "message board", "chat", "fan site",
                                "fansite", "blog"]),
    ("IT-сервисы и телеком",   ["software", "app$", "apps$", "application", "cloud", "hosting",
                                "developer", "saas", "telecom", "isp$", "internet provider",
                                "email provider", "vpn", "security", "technology", "tech$", "website",
                                "domain", "file sharing", "platform", "service", "provider"]),
]


# Глаголы, на которых заканчивается описание сервиса в первом предложении
SUBJECT_END = (r"\b(suffered|was|were|had|has|have|is|are|disclosed|confirmed|appeared|began|"
               r"allegedly|discovered|posted|contacted|experienced|reported|announced|"
               r"exposed|left|became|found|named|targeted)\b")


def keyword_found(keyword, text):
    """Есть ли ключевое слово в тексте (с начала слова, «$» — слово целиком)."""
    pattern = r"\b" + re.escape(keyword.rstrip("$")) + (r"\b" if keyword.endswith("$") else "")
    return re.search(pattern, text) is not None


# Ручные исправления для 30 крупнейших утечек: в их описаниях часто нет слов
# про сам сервис («In 2016, LinkedIn had 164 million email addresses...»),
# а именно они дают основную часть затронутых аккаунтов. Я прочитала
# описания этих утечек и отнесла их к отрасли сама. Ключ — поле Name из HIBP.
MANUAL_OVERRIDES = {
    "ExploitIn": "Сборники и спам-базы",       # «combo list» из многих утечек
    "Cit0day": "Сборники и спам-базы",         # сборник из 23 000 взломанных сайтов
    "NotSOCRadar": "Сборники и спам-базы",     # собранный список адресов
    "NationalPublicData": "Сборники и спам-базы",  # брокер данных (проверка биографий)
    "Exactis": "Сборники и спам-базы",         # маркетинговый брокер данных
    "Facebook": "Форумы и соцсети",
    "MySpace": "Форумы и соцсети",
    "Twitter200M": "Форумы и соцсети",
    "LinkedIn": "Форумы и соцсети",
    "LinkedInScrape": "Форумы и соцсети",
    "NetEase": "IT-сервисы и телеком",         # почтовый сервис и портал 163.com
    "Adobe": "IT-сервисы и телеком",
    "Apollo": "IT-сервисы и телеком",          # облачный сервис для продаж
    "Wattpad": "СМИ и развлечения",            # платформа для чтения историй
}


def classify(row):
    """Возвращает отрасль по первому совпавшему правилу или «Другое»."""
    if row["Name"] in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[row["Name"]]
    # Спам-базы, сборники из вредоносных программ и логи стилеров HIBP помечает
    # флагами: это не взлом конкретного сервиса, отрасли у них нет
    if row["IsSpamList"] or row["IsMalware"] or row["IsStealerLog"]:
        return "Сборники и спам-базы"
    # Берём из первого предложения только начало — до глагола «suffered»,
    # «was», «were» и т.п. Там описан сам сервис («the Russian Minecraft
    # service VimeWorld»). Дальше часто идёт «posted to a hacking forum»,
    # и слово «forum» иначе ошибочно отнесло бы сервис к форумам.
    first_sentence = row["description_text"].split(". ")[0]
    subject = re.split(SUBJECT_END, first_sentence)[0]
    text = (row["Title"] + " " + subject).lower()
    for industry, keywords in INDUSTRY_RULES:
        if any(keyword_found(word, text) for word in keywords):
            return industry
    return "Другое"


df["industry"] = df.apply(classify, axis=1)
say("\nОтрасли (число утечек):")
say(df["industry"].value_counts().to_string())

# ---------- 4. Разворачиваем типы данных ----------
# В исходных данных типы лежат списком: ["Email addresses", "Passwords"].
# explode делает из одной строки со списком несколько строк, по одной на тип.
pairs = df[["Name", "DataClasses"]].explode("DataClasses").rename(columns={"DataClasses": "data_class"})
pairs = pairs.dropna()
say(f"\nПосле «разворачивания» типов данных: {len(pairs)} строк (утечка + тип), "
    f"разных типов: {pairs['data_class'].nunique()}")

# ---------- 5. Загружаем в SQLite ----------
DB.unlink(missing_ok=True)  # каждый раз создаём базу заново
con = sqlite3.connect(DB)

breaches = pd.DataFrame({
    "breach_id": range(1, len(df) + 1),
    "name": df["Name"].to_numpy(),
    "title": df["Title"].to_numpy(),
    "domain": df["Domain"].replace("", None).to_numpy(),
    "breach_date": df["breach_date"].dt.strftime("%Y-%m-%d").to_numpy(),
    "added_date": df["added_date"].dt.strftime("%Y-%m-%d").to_numpy(),
    "pwn_count": df["PwnCount"].to_numpy(),
    "industry": df["industry"].to_numpy(),
    "is_verified": df["IsVerified"].astype(int).to_numpy(),
    "is_sensitive": df["IsSensitive"].astype(int).to_numpy(),
    "is_spam_list": df["IsSpamList"].astype(int).to_numpy(),
})
data_classes = pd.DataFrame({"data_class": sorted(pairs["data_class"].unique())})
data_classes.insert(0, "class_id", range(1, len(data_classes) + 1))

# Связующая таблица: вместо текстов храним номера утечки и типа
links = (pairs.merge(breaches[["breach_id", "name"]], left_on="Name", right_on="name")
              .merge(data_classes, on="data_class")[["breach_id", "class_id"]])

breaches.to_sql("breaches", con, index=False)
data_classes.to_sql("data_classes", con, index=False)
links.to_sql("breach_data_classes", con, index=False)
con.close()
say(f"\nБаза {DB.name}: breaches={len(breaches)}, data_classes={len(data_classes)}, "
    f"breach_data_classes={len(links)}")

(RESULTS / "01_preparation_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
