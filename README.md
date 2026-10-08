# Kanban-доска (аналог Jira) — курсовой проект

Веб-приложение Kanban-доски: проекты, доски с колонками (WIP-лимиты, порядок),
карточки задач с drag-and-drop, фильтрами и полнотекстовым поиском, историей
изменений и комментариями. Ролевая модель JWT-аутентификации
(`administrator` / `manager` / `developer`), защита от XSS/CSRF/SQLi,
автотесты (unit + интеграционные + Playwright E2E), нагрузочное тестирование
(Locust) и строгий CI/CD (GitHub Actions).

## Стек

* **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + SQLite, Alembic, PyJWT + bcrypt
* **Frontend:** ванильные HTML5/CSS3/JavaScript (ES6), раздаётся FastAPI как статика
* **Тесты/качество:** pytest, pytest-asyncio, TestClient (httpx), coverage.py, flake8, bandit, pip-audit
* **E2E/нагрузка:** Playwright (pytest-playwright), Locust
* **CI/CD:** GitHub Actions (`.github/workflows/ci-cd.yml`)

Подробное обоснование выбора — в [STACK.md](STACK.md), полное описание REST API — в [backend/API.md](backend/API.md),
отчёт по тестированию — в [TEST_REPORT.md](TEST_REPORT.md).

## Структура

```
├── .github/workflows/ci-cd.yml   # CI: lint → unit → build → integration → e2e → security → deploy
├── backend/
│   ├── app/
│   │   ├── api/                  # роуты + зависимости (роли, JWT)
│   │   ├── core/config.py        # настройки (env: SECRET_KEY, DATABASE_URL, ...)
│   │   ├── db/                   # сессия, посев данных, Alembic-миграции
│   │   ├── models/ schemas/      # SQLAlchemy-модели, Pydantic-схемы
│   │   ├── repositories/ services/  # слой доступа и бизнес-логика
│   │   ├── main.py               # приложение + lifespan (миграции + посев)
│   │   └── static/index.html     # SPA фронтенд
│   ├── alembic/                  # миграции схемы
│   ├── tests/                    # unit / integration / e2e (Playwright)
│   ├── locustfile.py             # нагрузочный сценарий
│   ├── check_coverage.py         # gate: ≥80% строк, ≥70% ветвлений
│   ├── run_ci.sh                 # локальный прогон всего CI
│   └── requirements.txt
├── STACK.md  TEST_REPORT.md
```

## Запуск

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8080
```

Приложение: `http://127.0.0.1:8080` (Swagger: `/docs`).  
При первом запуске схема создаётся миграциями Alembic, БД заполняется
администратором по умолчанию: **логин `admin`, пароль `admin`**
(задаётся через `ADMIN_USERNAME` / `ADMIN_PASSWORD`).

Переменные окружения (все опциональны): `SECRET_KEY`, `DATABASE_URL`,
`BCRYPT_ROUNDS`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ACCESS_TOKEN_TTL_HOURS`.

## Тестирование

```bash
cd backend

# unit + интеграционные с покрытием (≥80% строк, ≥70% ветвлений)
pytest tests/test_unit.py tests/test_integration.py \
  --cov=app --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
python check_coverage.py coverage.json

# E2E в браузере (Playwright; браузеры: playwright install --with-deps chromium)
pytest tests/test_e2e.py

# линт и безопасность
python -m flake8 .
bandit -r app -q
python -m pip_audit -r requirements.txt

# нагрузочный тест (сервер должен быть запущен)
locust -f locustfile.py --host http://127.0.0.1:8080

# весь CI-конвейер локально (строгий, падает при любой ошибке)
./run_ci.sh
```

## CI/CD

`.github/workflows/ci-cd.yml` — последовательные джобы без `|| true`:

1. **lint** — flake8 (PEP8, exit-код строгий);
2. **unit-tests** — pytest + gate покрытия ≥80%;
3. **build** — проверка импорта приложения и конфига Alembic;
4. **integration-tests** — unit+integration, `check_coverage.py` (≥80% строк / ≥70% ветвей);
5. **e2e-tests** — Playwright (chromium, трейсы при падении — артефакт);
6. **security-scan** — bandit + pip-audit;
7. **deploy** — симуляция деплоя только после успешного прохождения всех проверок.
