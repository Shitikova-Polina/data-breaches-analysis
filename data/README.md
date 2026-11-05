# Данные

| Файл | Что внутри |
|---|---|
| `raw/breaches.json` | публичный список утечек Have I Been Pwned, снимок от 4 ноября 2026 года (время — в `raw/downloaded_at.txt`) |
| `industry_manual_check.csv` | моя ручная разметка отраслей для 50 случайных утечек (для проверки правила) |
| `breaches.db` | база SQLite, создаётся скриптом `scripts/02_prepare.py`, в репозиторий не попадает |

**Источник:** https://haveibeenpwned.com/api/v3/breaches — открытый адрес, ключ API и регистрация не нужны.
Документация: https://haveibeenpwned.com/API/v3

**Лицензия:** данные об утечках HIBP распространяются по лицензии
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/): их можно использовать,
указав источник — [Have I Been Pwned](https://haveibeenpwned.com). Условия API также просят указывать
честный User-Agent; скрипт это делает.

**Личных данных людей в файле нет:** только название сервиса, домен, даты, число затронутых аккаунтов,
список типов утёкших данных и текстовое описание инцидента.

Скачать свежий список (результаты могут отличаться от README):

```bash
python scripts/01_download_data.py --refresh
```
