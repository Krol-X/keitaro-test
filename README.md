# Keitaro Campaign Manager (MVP)

Веб-приложение для управления кампаниями Keitaro: просмотр списка кампаний, создание кампаний и редактирование офферов в потоках через HTTP API.

Проект состоит из двух частей:
- **backend/** — FastAPI + SQLAlchemy, интеграция с Keitaro Admin API (`/admin_api/v1`), журнал операций в БД.
- **frontend/** — Vue 3 (Vite) + Pinia + PrimeVue 4 + Tailwind CSS.

Подробные заметки/спецификации:
- [docs/backend-notes.md](docs/backend-notes.md)
- [docs/frontend-spec.md](docs/frontend-spec.md)

## Структура репозитория

```text
.
├─ backend/                 # FastAPI-приложение (app/, tests/, requirements.txt)
├─ frontend/                # Vue/Vite SPA (src/, tests/, assets/)
├─ deploy/                  # Конфиги для Docker-образа (nginx, entrypoint)
├─ docs/                    # Описания/заметки по backend и frontend
├─ Dockerfile               # Production-сборка (frontend build + backend + nginx)
├─ .dockerignore
├─ .gitignore
└─ .env.example
```

## Требования

- **Docker** (рекомендуемый способ деплоя) или
- **Python 3.11+** и **Node.js 20+** / npm для локальной разработки

## Конфигурация (переменные окружения)

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `KEITARO_BASE_URL` | Базовый URL Keitaro (без `/admin_api/v1`) | пусто (нужно задать) |
| `KEITARO_API_KEY` | API-ключ Keitaro (`Api-Key`) | пусто (нужно задать) |
| `DATABASE_URL` | URL БД SQLAlchemy | `sqlite:///./keitaro.db` (локально), в Docker-образе: `sqlite:////data/keitaro.db` |
| `DEFAULT_DOMAIN_ID` | Домен по умолчанию (для справочников/создания) | не задан |
| `DEFAULT_GROUP_ID` | Группа кампаний по умолчанию | не задан |
| `DEFAULT_TRAFFIC_SOURCE_ID` | Источник трафика по умолчанию | не задан |

См. шаблон: [.env.example](.env.example).

## Локальный запуск (разработка)

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# задайте переменные окружения (KEITARO_BASE_URL, KEITARO_API_KEY, ...)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Проверка:
- API: `http://localhost:8000/api/v1/...`
- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

### 2. Frontend (Vue + Vite)

```bash
cd frontend
npm install
npm run dev
```

По умолчанию dev-сервер: `http://localhost:5173`.

- Vite proxy перенаправляет `/api` на `http://localhost:8000` (см. `frontend/vite.config.ts`).
- Базовый URL API во frontend можно переопределить через `VITE_API_BASE` (по умолчанию `http://localhost:8000/api/v1`).

## Деплой в Docker

`Dockerfile` собирает frontend и запускает backend + nginx в одном контейнере:
- nginx отдаёт SPA и проксирует `/api/`, `/health`, `/docs`, `/openapi.json`, `/redoc` на `uvicorn`;
- для SPA включён fallback на `index.html` (Vue Router history mode).

### Сборка

```bash
docker build -t keitaro-campaign-manager .
```

При необходимости можно задать базовый путь API на этапе сборки frontend:

```bash
docker build --build-arg VITE_API_BASE=/api/v1 -t keitaro-campaign-manager .
```

### Запуск

```bash
docker run --rm -p 8080:80 \
  -e KEITARO_BASE_URL="https://your-keitaro-host" \
  -e KEITARO_API_KEY="your_api_key" \
  -e DEFAULT_DOMAIN_ID="1" \
  -e DEFAULT_GROUP_ID="1" \
  -e DEFAULT_TRAFFIC_SOURCE_ID="1" \
  -v keitaro-data:/data \
  keitaro-campaign-manager
```

После запуска:
- UI: `http://localhost:8080/`
- API: `http://localhost:8080/api/v1/...`
- Health/Docs: `http://localhost:8080/health`, `http://localhost:8080/docs`

> В Docker-образе по умолчанию используется `DATABASE_URL=sqlite:////data/keitaro.db`. Для сохранения данных монтируйте volume в `/data` или переопределите `DATABASE_URL`.

## Тесты

```bash
# backend
cd backend
pytest

# frontend
cd frontend
npm test
```

## Примечания

- Источник истины по данным кампаний/потоков/офферов — Keitaro; в локальной БД хранится журнал операций (`operations`).
- В проекте присутствуют заметки/ТЗ в `docs/` (часть пунктов может описывать целевое поведение MVP шире текущей реализации).
- Для корректной работы создания/обновления сущностей необходим доступ к Keitaro Admin API и валидные дефолтные ID (домены/группы/источники) в вашей инсталляции Keitaro.
