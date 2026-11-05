"""Шаг 1. Скачиваем публичный список утечек Have I Been Pwned (HIBP).

Адрес https://haveibeenpwned.com/api/v3/breaches открыт: ключ API и
регистрация не нужны. В ответе только сведения об утечках (название
сервиса, дата, число аккаунтов, типы данных), никаких данных о людях.

Лицензия: CC BY 4.0 — можно использовать, указав HIBP как источник.
Правила HIBP просят честно представляться в заголовке User-Agent.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "https://haveibeenpwned.com/api/v3/breaches"
USER_AGENT = "data-breaches-analysis/1.0 (portfolio project; Python urllib)"

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)


def main():
    # Снимок уже лежит в репозитории, и анализ в README сделан по нему.
    # Перекачиваем только по явной просьбе: --refresh
    if (RAW / "breaches.json").exists() and "--refresh" not in sys.argv:
        print("Снимок уже есть в data/raw/ (дата:",
              (RAW / "downloaded_at.txt").read_text().strip() + ").",
              "Чтобы скачать свежий список, добавьте --refresh.")
        return

    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        breaches = json.load(resp)
    (RAW / "breaches.json").write_text(json.dumps(breaches, ensure_ascii=False, indent=1), encoding="utf-8")
    (RAW / "downloaded_at.txt").write_text(time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()) + "\n")
    print("Утечек в списке:", len(breaches))


if __name__ == "__main__":
    main()
