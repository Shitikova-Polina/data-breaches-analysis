-- Запросы к базе data/breaches.db.
-- Каждый запрос начинается со строки-маркера «name» с именем файла: по ней скрипт
-- scripts/04_run_sql.py понимает, куда сохранить результат (results/sql_<имя>.csv).
-- Таблицы:
--   breaches            — одна строка на утечку (breach_id, title, breach_date, pwn_count, industry, ...)
--   data_classes        — справочник типов данных (class_id, data_class)
--   breach_data_classes — какие типы были в какой утечке (breach_id, class_id)


-- name: 01_top_breaches
-- Топ-10 утечек по числу затронутых аккаунтов.
SELECT title,
       breach_date,
       industry,
       pwn_count
FROM breaches
ORDER BY pwn_count DESC
LIMIT 10;


-- name: 02_by_year
-- Утечки по годам: сколько утечек произошло и сколько аккаунтов затронуто.
-- GROUP BY собирает строки с одинаковым годом в одну группу.
SELECT CAST(strftime('%Y', breach_date) AS INTEGER) AS year,
       COUNT(*)                                     AS breaches,
       SUM(pwn_count)                               AS accounts
FROM breaches
GROUP BY year
ORDER BY year;


-- name: 03_top_data_classes
-- Самые частые типы утёкших данных: в скольких утечках встречается каждый тип
-- и какая это доля от всех утечек. JOIN соединяет связующую таблицу со справочником.
SELECT dc.data_class,
       COUNT(*)                                                        AS breaches,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM breaches), 1)    AS pct_of_breaches
FROM breach_data_classes AS bdc
JOIN data_classes AS dc ON dc.class_id = bdc.class_id
GROUP BY dc.data_class
ORDER BY breaches DESC
LIMIT 15;


-- name: 04_pairs
-- Какие типы данных чаще всего утекают вместе.
-- Соединяем связующую таблицу саму с собой (self-join) по номеру утечки:
-- так получаем все пары типов внутри одной утечки. Условие a.class_id < b.class_id
-- убирает пары «тип сам с собой» и повторы (A+B и B+A).
SELECT dca.data_class AS class_a,
       dcb.data_class AS class_b,
       COUNT(*)       AS breaches_together
FROM breach_data_classes AS a
JOIN breach_data_classes AS b  ON a.breach_id = b.breach_id AND a.class_id < b.class_id
JOIN data_classes        AS dca ON dca.class_id = a.class_id
JOIN data_classes        AS dcb ON dcb.class_id = b.class_id
GROUP BY class_a, class_b
ORDER BY breaches_together DESC
LIMIT 15;


-- name: 05_by_industry
-- Отрасли: число утечек, затронутые аккаунты и доля утечек, где были пароли.
-- LEFT JOIN на подзапрос с паролями: если паролей в утечке не было, получим NULL.
WITH password_breaches AS (
    SELECT bdc.breach_id
    FROM breach_data_classes AS bdc
    JOIN data_classes AS dc ON dc.class_id = bdc.class_id
    WHERE dc.data_class = 'Passwords'
)
SELECT b.industry,
       COUNT(*)                                          AS breaches,
       SUM(b.pwn_count)                                  AS accounts,
       ROUND(100.0 * COUNT(pb.breach_id) / COUNT(*), 1)  AS pct_with_passwords
FROM breaches AS b
LEFT JOIN password_breaches AS pb ON pb.breach_id = b.breach_id
GROUP BY b.industry
ORDER BY breaches DESC;


-- name: 06_largest_per_year
-- Крупнейшая утечка каждого года (CTE + оконная функция).
-- ROW_NUMBER() OVER (PARTITION BY year ORDER BY pwn_count DESC) нумерует утечки
-- внутри каждого года от самой большой к самой маленькой, не схлопывая строки,
-- как это сделал бы GROUP BY. Потом оставляем только номер 1.
WITH ranked AS (
    SELECT CAST(strftime('%Y', breach_date) AS INTEGER) AS year,
           title,
           industry,
           pwn_count,
           ROW_NUMBER() OVER (
               PARTITION BY strftime('%Y', breach_date)
               ORDER BY pwn_count DESC
           ) AS rank_in_year
    FROM breaches
)
SELECT year, title, industry, pwn_count
FROM ranked
WHERE rank_in_year = 1
ORDER BY year;


-- name: 07_passwords_share_by_year
-- Как менялась доля утечек с паролями по годам, плюс накопительный итог
-- утечек (оконная функция SUM() OVER с сортировкой по году).
WITH yearly AS (
    SELECT CAST(strftime('%Y', b.breach_date) AS INTEGER) AS year,
           COUNT(*) AS breaches,
           SUM(CASE WHEN EXISTS (
                   SELECT 1
                   FROM breach_data_classes AS bdc
                   JOIN data_classes AS dc ON dc.class_id = bdc.class_id
                   WHERE bdc.breach_id = b.breach_id AND dc.data_class = 'Passwords'
               ) THEN 1 ELSE 0 END) AS with_passwords
    FROM breaches AS b
    GROUP BY year
)
SELECT year,
       breaches,
       with_passwords,
       ROUND(100.0 * with_passwords / breaches, 1) AS pct_with_passwords,
       SUM(breaches) OVER (ORDER BY year)          AS breaches_cumulative
FROM yearly
ORDER BY year;


-- name: 08_sensitive_types_by_industry
-- В каких отраслях чаще утекают особо опасные данные: документы, данные карт,
-- личные сообщения. Считаем, в скольких утечках отрасли встречается каждый тип.
SELECT b.industry,
       SUM(CASE WHEN dc.data_class = 'Government issued IDs'    THEN 1 ELSE 0 END) AS gov_ids,
       SUM(CASE WHEN dc.data_class = 'Partial credit card data' THEN 1 ELSE 0 END) AS partial_cards,
       SUM(CASE WHEN dc.data_class = 'Credit cards'             THEN 1 ELSE 0 END) AS credit_cards,
       SUM(CASE WHEN dc.data_class = 'Private messages'         THEN 1 ELSE 0 END) AS private_messages
FROM breaches AS b
JOIN breach_data_classes AS bdc ON bdc.breach_id = b.breach_id
JOIN data_classes        AS dc  ON dc.class_id   = bdc.class_id
GROUP BY b.industry
ORDER BY gov_ids + partial_cards + credit_cards + private_messages DESC;


-- name: 09_disclosure_lag
-- Сколько времени проходит от утечки до её появления в HIBP.
-- julianday переводит дату в число дней, разница — задержка в днях.
-- Это важно: утечки последних лет ещё не все стали известны.
SELECT CAST(strftime('%Y', breach_date) AS INTEGER)                  AS year,
       COUNT(*)                                                      AS breaches,
       ROUND(AVG(julianday(added_date) - julianday(breach_date)))    AS avg_lag_days,
       ROUND(100.0 * SUM(CASE WHEN julianday(added_date) - julianday(breach_date) > 365
                              THEN 1 ELSE 0 END) / COUNT(*), 1)      AS pct_added_after_1_year
FROM breaches
GROUP BY year
ORDER BY year;


-- name: 10_shinyhunters
-- Почему в последние годы падает доля утечек с паролями? Проверяем одну
-- гипотезу: в 2026 году много утечек от группы вымогателей ShinyHunters
-- («заплати, или опубликуем»), которые крадут базы клиентов, а не пароли.
-- LIKE '%ShinyHunters%' ищет это слово в любом месте описания.
WITH tagged AS (
    SELECT b.breach_id,
           CAST(strftime('%Y', b.breach_date) AS INTEGER)            AS year,
           CASE WHEN b.description LIKE '%ShinyHunters%' THEN 1 ELSE 0 END AS is_shinyhunters,
           CASE WHEN EXISTS (
               SELECT 1
               FROM breach_data_classes AS bdc
               JOIN data_classes AS dc ON dc.class_id = bdc.class_id
               WHERE bdc.breach_id = b.breach_id AND dc.data_class = 'Passwords'
           ) THEN 1 ELSE 0 END                                       AS has_passwords
    FROM breaches AS b
)
SELECT year,
       is_shinyhunters,
       COUNT(*)                                     AS breaches,
       ROUND(100.0 * SUM(has_passwords) / COUNT(*), 1) AS pct_with_passwords
FROM tagged
WHERE year >= 2024
GROUP BY year, is_shinyhunters
ORDER BY year, is_shinyhunters;
