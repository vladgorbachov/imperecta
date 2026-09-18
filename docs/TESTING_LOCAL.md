# Локальный тестовый контур (канон с 2026-09-18)

Полный суит гоняется через `backend/scripts/run_tests_local.sh` против
docker-контейнеров `imperecta-pg-test` (postgres:16, порт 5432) и
`imperecta-redis-test` (redis:7, порт 6379).

## Почему так

- venv живёт на python3.14 + свежих fastapi/starlette — так же резолвит
  прод-образ (requirements без пинов, Dockerfile python:3.12-slim; апгрейд
  прода на 3.14 — отдельное решение).
- DB-зависимые тесты (gate-записи, auth-контракты, pipeline) ходят в
  реальную БД с настоящими gate-функциями — HMAC-путь проверяется целиком.
- pytest-asyncio работает в session-scope лупе (pyproject) — модульный
  async-движок с пулом asyncpg живёт в одном лупе на весь прогон.

## Бутстрап свежей БД (однократно / при пересоздании)

```bash
docker start imperecta-pg-test imperecta-redis-test
```

В контейнере должен лежать stub pg_cron (см. ниже). Затем:

```sql
DROP DATABASE IF EXISTS imperecta_test; CREATE DATABASE imperecta_test;
-- в imperecta_test:
CREATE EXTENSION pg_trgm; CREATE EXTENSION pgcrypto; CREATE EXTENSION pg_cron;
CREATE SCHEMA vault;
CREATE TABLE vault.decrypted_secrets(name text PRIMARY KEY, decrypted_secret text NOT NULL);
INSERT INTO vault.decrypted_secrets VALUES
  ('data_firewall_signing_secret','test-data-firewall-signing-secret');
CREATE SCHEMA extensions;
ALTER EXTENSION pgcrypto SET SCHEMA extensions;
ALTER EXTENSION pg_trgm SET SCHEMA extensions;
-- роли Supabase-паритета:
CREATE ROLE imperecta_app LOGIN PASSWORD 'imperecta_app';
CREATE ROLE authenticated NOLOGIN; CREATE ROLE anon NOLOGIN; CREATE ROLE service_role NOLOGIN;
```

Потом `alembic upgrade head` с DATABASE_URL на imperecta_test — цепочка
001→062 реплеится с нуля (проверено; 019/022 содержат replay-гигиену
констрейнтов).

### Stub pg_cron

Настоящий pg_cron в тестах не нужен (фоновые джобы вредны герметичности).
В контейнере лежат `/usr/share/postgresql/16/extension/pg_cron.control` и
`pg_cron--1.6.sql` — схема `cron` с таблицей `cron.job` и функциями
`cron.schedule/unschedule`, только бухгалтерия расписаний. Миграции
051/059 проходят, ничего не исполняется.

## Гигиена данных

БД перманентна между прогонами; conftest на старте сессии чистит
тест-артефакты (тест-юзеры, scrape_jobs/logs), отдельные файлы — свои
сиды (fixed-URL листинги, pipeline-джобы). Новые тесты с фикс-сидами
обязаны чистить за собой или в autouse-фикстуре файла.

## История

2026-09-18: суит был «зелёным» иллюзорно — starlette 1.x сломал плоскую
итерацию `app.routes` (route-тесты проходили вакуумно), DB-тесты падали в
connection refused. Починено: `tests/route_flatten.py`, реальный DB-контур,
session-loop, синк ORM-инстансов при gate-записях (seam-3 контракт v2 —
`set_committed_value`: значения свежие, echo-UPDATE нет), реплей-гигиена
миграций 019/022. Два теста discovery-integration ждут новый оффлайн-harness
(sitemap-first их обесценил) — помечены skip.
