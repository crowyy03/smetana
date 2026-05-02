# Smeta Bot v2 (ВИЛИНС)

Telegram-бот: входящие **xlsx / pdf / docx / текст** → разбор → **цены только из базы исторических КП** (эмбеддинги + top‑K + Claude). Фиксированного прайс-листа нет. После выдачи PDF подтверждённые позиции **автоматически** попадают в прецеденты (`ReferenceItem`).

## Требования

- Python 3.11+
- **OPENAI_API_KEY** — через ProxyAPI на OpenAI-совместимый эндпойнт (эмбеддинги).
- **ANTHROPIC_API_KEY** — для разбора текста и батч-оценки (Claude через ProxyAPI).
- macOS: для WeasyPrint: `brew install cairo pango gdk-pixbuf libffi`
- Linux: `python3-cffi`, `libcairo2`, `libpango`, `libgdk-pixbuf`, и т.д. (см. WeasyPrint docs).

## Установка

```bash
cd vilins
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# BOT_TOKEN, ADMIN_IDS, ANTHROPIC_*, OPENAI_* — см. .env.example
```

Логотип (опционально):

```bash
python scripts/make_placeholder_logo.py
```

## База прецедентов

1. Положите исторические КП в `data/reference_kp/` с именами вида  
   `kp_<YYYY-MM>_<slug>.{pdf|xlsx|docx}` (slug латиницей, через `_`).
2. Импорт (идемпотентно по SHA256 текста):

```bash
python scripts/import_history.py
python scripts/import_history.py --only kp_2025-01_zil_technopark
python scripts/import_history.py --force   # переимпорт по hash
```

После смены `EMBEDDINGS_MODEL`:

```bash
python scripts/rebuild_embeddings.py
```

Админ в чате: **`/import_kp`** → файл → подтверждение (LLM + embeddings).

## Запуск

```bash
python main.py
```

## Smoke-проверки

Из корня репозитория (после `pip install -r requirements.txt`):

```bash
python -m compileall -q .
python scripts/smoke_checks.py
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Новая смета, ожидание файла/текста |
| `/help` | Справка |
| `/cancel` | Сброс FSM |
| `/stats` | (admin) сметы за сегодня/месяц |
| `/import_kp` | (admin) загрузка КП в `data/reference_kp/` и импорт в БД |

## Структура

- `bot/` — aiogram 3, FSM, хендлеры v2
- `core/parsers/` — Excel, PDF, DOCX, текст
- `core/reference_db/` — импорт КП, эмбеддинги, retriever
- `core/estimator/` — Claude, батч-оценка
- `core/pdf/` — WeasyPrint + Jinja2
- `db/` — SQLAlchemy 2 + aiosqlite
- `data/reference_kp/` — только эта папка + импорт = база прецедентов
- `data/extracted/` — JSON после LLM-импорта (отладка)
- `data/sample_requests/` — необязательно, для разработчика, в БД не идёт

Спецификация: [smeta_bot_spec_v2.md](smeta_bot_spec_v2.md) (если файл есть в репозитории).
