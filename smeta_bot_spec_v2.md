# ТЕХНИЧЕСКОЕ ЗАДАНИЕ v2: Telegram-бот для генерации смет
## Полная спецификация MVP — версия с обучением на исторических КП

---

## КОНТЕКСТ ПРОЕКТА

Компания ВИЛИНС производит навигационные системы и металлические изделия для жилых комплексов и бизнес-центров (номера этажей, квартир, таблички, дверные порталы, декоративные панели, стойки).

**Главная особенность:** прайс-листа в традиционном виде НЕТ. Каждое коммерческое предложение считается индивидуально, цены варьируются от проекта к проекту и зависят от материала, размера, сложности, объёма заказа.

**Что есть:** 10 готовых исторических КП с уже рассчитанными позициями. Это и есть «обучающая база» — бот должен научиться считать новые сметы по аналогии с прошлыми.

**Принцип работы:** при поступлении нового запроса бот находит в исторических КП похожие позиции и предлагает цены на их основе. Менеджер подтверждает/правит каждую позицию. После подтверждения новая смета сама становится прецедентом для будущих расчётов.

---

## КРИТИЧЕСКИЕ АРХИТЕКТУРНЫЕ ПРИНЦИПЫ

### Принцип 1: LLM не придумывает цены из воздуха

Каждая предложенная цена должна быть обоснована конкретным историческим прецедентом. Если нет похожего случая — бот честно говорит «нет аналога, нужна ручная оценка», а не угадывает.

### Принцип 2: Все цены идут через подтверждение менеджера

В отличие от каталожной модели, где можно автоматически генерировать PDF, здесь критичен этап `ручного подтверждения`. Менеджер видит предложение, обоснование, и подтверждает или правит. Это защита от ошибок при динамических ценах.

### Принцип 3: Система самообучается

Каждое подтверждённое менеджером КП автоматически добавляется в базу прецедентов. Через 3–6 месяцев бот будет иметь 50–100 прецедентов и предлагать всё более точные цены.

### Принцип 4: Прозрачность вычислений

Для каждой позиции бот показывает: «Предлагаю X ₽ — основано на проекте Y от такой-то даты, где аналогичная позиция стоила Z ₽». Менеджер всегда понимает откуда взялась цена.

---

## СТЕК ТЕХНОЛОГИЙ

```
Python 3.11+
aiogram 3.x          — Telegram Bot framework
openpyxl             — чтение Excel файлов
pdfplumber           — извлечение текста и таблиц из PDF
python-docx          — чтение Word документов
rapidfuzz            — быстрый предматчинг
anthropic            — SDK для Claude API (через ProxyAPI)
openai               — SDK для embeddings (через ProxyAPI)
numpy                — работа с векторами эмбеддингов
jinja2               — HTML-шаблоны для PDF
weasyprint           — рендеринг HTML → PDF
sqlalchemy + aiosqlite — async ORM для SQLite
pydantic v2          — валидация данных
python-dotenv        — переменные окружения
loguru               — логирование
num2words            — суммы прописью
```

---

## СТРУКТУРА ПРОЕКТА

```
smeta_bot/
├── .env                          # переменные окружения
├── .env.example
├── requirements.txt
├── main.py                       # точка входа
├── config.py                     # конфиг
│
├── bot/
│   ├── __init__.py
│   ├── router.py                 # сборка роутеров
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py              # /start, /help
│   │   ├── upload.py             # приём файлов и текста
│   │   ├── estimation.py         # пошаговое подтверждение позиций
│   │   ├── manual.py             # ручной ввод цены
│   │   ├── confirm.py            # финальная генерация PDF
│   │   └── admin.py              # админ-команды
│   ├── keyboards/
│   │   ├── __init__.py
│   │   └── inline.py             # все inline-клавиатуры
│   ├── states.py                 # FSM
│   └── middlewares.py
│
├── core/
│   ├── __init__.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── excel_parser.py       # парсинг Excel
│   │   ├── pdf_parser.py         # парсинг PDF (для исторических КП и входящих)
│   │   ├── docx_parser.py        # парсинг Word
│   │   ├── text_parser.py        # парсинг свободного текста через Claude
│   │   └── universal.py          # роутер: определяет формат и вызывает парсер
│   │
│   ├── reference_db/
│   │   ├── __init__.py
│   │   ├── importer.py           # импорт исторических КП в базу прецедентов
│   │   ├── embeddings.py         # генерация и поиск эмбеддингов
│   │   └── retriever.py          # поиск похожих позиций
│   │
│   ├── estimator/
│   │   ├── __init__.py
│   │   ├── price_estimator.py    # главный модуль оценки цен через LLM
│   │   ├── prompts.py            # все промпты в одном месте
│   │   └── confidence.py         # классификация уверенности матчинга
│   │
│   ├── pdf/
│   │   ├── __init__.py
│   │   ├── generator.py          # генерация PDF
│   │   └── templates/
│   │       ├── invoice.html
│   │       └── invoice.css
│   │
│   └── llm/
│       ├── __init__.py
│       ├── client.py             # обёртка над Claude API
│       └── embeddings_client.py  # обёртка над OpenAI embeddings API
│
├── db/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   ├── reference_repo.py         # CRUD для прецедентов
│   └── invoice_repo.py           # CRUD для смет
│
├── data/
│   ├── reference_kp/             # сюда положить 10 исторических КП
│   │   ├── kp_01_era.pdf
│   │   ├── kp_02_wave.pdf
│   │   └── ...
│   └── extracted/                # извлечённые JSON прецедентов (генерируется при импорте)
│
├── static/
│   ├── logo.png
│   └── company_info.json         # реквизиты компании для PDF
│
└── scripts/
    ├── import_history.py         # одноразовый скрипт импорта 10 КП
    └── rebuild_embeddings.py     # пересчёт эмбеддингов при изменениях
```

---

## ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (.env)

```env
# Telegram
BOT_TOKEN=your_telegram_bot_token
ADMIN_IDS=123456789

# LLM через ProxyAPI
ANTHROPIC_API_KEY=your_proxyapi_key
ANTHROPIC_BASE_URL=https://api.proxyapi.ru/anthropic/

# Embeddings через тот же ProxyAPI (поддерживает OpenAI API)
OPENAI_API_KEY=your_proxyapi_key
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1/

# Модели
PRIMARY_MODEL=claude-sonnet-4-6
FALLBACK_MODEL=claude-opus-4-6
EMBEDDINGS_MODEL=text-embedding-3-small

# Пороги
HIGH_CONFIDENCE_THRESHOLD=0.85   # выше → авто-предложение
MEDIUM_CONFIDENCE_THRESHOLD=0.6  # выше → предложение с пометкой "проверить"
                                  # ниже → ручная оценка обязательна
TOP_K_REFERENCES=5               # сколько похожих прецедентов передавать в Claude

# База данных
DATABASE_URL=sqlite+aiosqlite:///./data/smeta_bot.db

# Логи
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log

# Реквизиты компании (для PDF)
COMPANY_NAME=ООО ВИЛИНС
COMPANY_INN=7714356598
COMPANY_KPP=504701001
COMPANY_ADDRESS=141421, Московская область, г.о. Химки, г Химки, мкр. Сходня, ул Первомайская, д. 56А
COMPANY_PHONE=+7 (495) 275-40-01
COMPANY_WEB=WWW.VILINS.COM
EXECUTOR_NAME=Алексей
EXECUTOR_PHONE=8 999 916 04 24
```

---

## МОДЕЛИ ДАННЫХ (db/models.py)

```python
# SQLAlchemy 2.0 декларативный стиль, async

class ReferenceProject(Base):
    """Историческое КП — прецедент"""
    __tablename__ = "reference_projects"
    
    id: int (PK)
    
    # Метаданные
    source_file: str              # имя исходного файла
    project_name: str             # "ЖК ЭРА", "БЦ Upside", "ЗИЛ Технопарк"
    client_name: str | None       # "ANT YAPI", "СТР Констракшн"
    object_type: str              # "residential", "business_center", "mixed"
    project_date: date            # из КП
    
    # Сводные данные
    total_amount: Decimal
    items_count: int
    raw_content: str              # полный текст КП для контекста
    
    # Системные
    imported_at: datetime
    is_active: bool (default=True)
    
    # Связи
    items: List[ReferenceItem]


class ReferenceItem(Base):
    """Позиция из исторического КП — единица обучения"""
    __tablename__ = "reference_items"
    
    id: int (PK)
    project_id: int (FK → ReferenceProject)
    
    # Описание позиции
    name: str                     # "Дверной портал ДВ-2"
    description: str              # полное описание включая отделку
    material: str | None          # "нержавеющая сталь AISI 430 1мм"
    coating: str | None           # "нитрид титана brown"
    size_text: str | None         # "1505×2400" или "м2" или null
    mounting: str | None          # тип крепления
    category: str                 # "navigation", "door_portal", "panel", "stand", "service", "other"
    
    # Числовые
    quantity: Decimal
    unit: str                     # "шт.", "м2", "компл.", "м"
    unit_price: Decimal
    total_price: Decimal
    
    # Раздел КП
    section: int                  # 1 = изготовление, 2 = подрядные услуги
    
    # Поисковая оптимизация
    search_text: str              # объединение всех текстовых полей
    embedding: bytes              # numpy vector (1536 dim для text-embedding-3-small)


class Invoice(Base):
    """Сгенерированная смета (новый расчёт)"""
    __tablename__ = "invoices"
    
    id: int (PK)
    invoice_number: str           # "25-12/7"
    
    # Клиент
    client_name: str | None
    contact_name: str | None
    object_name: str | None
    object_type: str | None
    
    # Состояние
    status: str                   # "draft", "estimating", "confirmed", "generated"
    
    # Итоги
    total_section1: Decimal
    total_section2: Decimal
    total_amount: Decimal
    
    # Telegram
    telegram_user_id: int
    telegram_username: str | None
    
    # Системные
    created_at: datetime
    completed_at: datetime | None
    pdf_path: str | None
    
    # Источник запроса
    source_file_name: str | None
    source_format: str            # "excel", "pdf", "docx", "text", "manual"
    
    # Связи
    items: List[InvoiceItem]


class InvoiceItem(Base):
    """Позиция в сгенерированной смете"""
    __tablename__ = "invoice_items"
    
    id: int (PK)
    invoice_id: int (FK)
    
    # Что было запрошено
    original_text: str            # как написал клиент
    
    # Что подобрано
    name: str                     # финальное название позиции для PDF
    description: str              # полное описание для PDF
    quantity: Decimal
    unit: str
    unit_price: Decimal
    total_price: Decimal
    section: int
    
    # Источник цены (для аудита и обучения)
    estimation_method: str        # "auto_high", "auto_medium", "manual", "from_reference"
    confidence: float             # 0.0–1.0
    reference_item_ids: str       # JSON список ID прецедентов на которых основана цена
    estimation_reasoning: str     # объяснение от Claude почему такая цена
    
    # Подтверждение
    was_confirmed: bool
    was_modified: bool            # менеджер изменил предложенную цену
    original_suggested_price: Decimal | None  # что предлагал бот изначально


class EstimationLog(Base):
    """Лог каждой оценки (для анализа качества)"""
    __tablename__ = "estimation_logs"
    
    id: int (PK)
    invoice_item_id: int (FK)
    
    request_text: str
    references_used: str          # JSON
    llm_response: str
    confidence: float
    final_price: Decimal
    was_overridden: bool
    created_at: datetime
```

---

## ИМПОРТ ИСТОРИЧЕСКИХ КП (scripts/import_history.py)

Это критически важный одноразовый скрипт. Без него бот не работает.

```python
"""
Импорт 10 исторических КП в базу прецедентов.

ВХОД: data/reference_kp/*.pdf, *.xlsx, *.docx
ВЫХОД: записи в ReferenceProject + ReferenceItem с эмбеддингами

ЛОГИКА:
1. Для каждого файла в data/reference_kp/:
   a. Определить тип файла
   b. Извлечь текст
   c. Передать Claude с промптом "Извлеки все позиции с ценами в JSON"
   d. Распарсить JSON
   e. Сохранить в БД
   f. Сгенерировать эмбеддинги для каждой позиции
2. Сохранить промежуточные JSON в data/extracted/ для отладки

ВАЖНО: это ручной запуск, не автоматический.
Команда: python scripts/import_history.py
"""

import asyncio
from pathlib import Path

EXTRACTION_PROMPT = """
Ты анализируешь коммерческое предложение от компании ВИЛИНС (производитель навигации и металлических изделий).

Извлеки ВСЕ позиции из КП в структурированный JSON.

Для каждой позиции определи:
- name: краткое название (как в КП)
- description: полное описание включая материал, отделку, размеры
- material: материал (нерж сталь, металл, пластик и т.д.)
- coating: покрытие/цвет (нитрид титана, RAL, бронза)
- size_text: размер если указан (например "1505x2400" или "м2" если за квадратный метр)
- mounting: тип крепления (стойки, клеевое, фрезеровка)
- category: одна из: navigation, door_portal, panel, stand, service, other
- quantity: количество (число)
- unit: единица (шт., м2, компл., м)
- unit_price: цена за единицу (число без пробелов и валюты)
- total_price: общая сумма (число)
- section: 1 = изготовление изделий, 2 = подрядные услуги (доставка, упаковка, монтаж)

Также определи метаданные проекта:
- project_name: название объекта (ЖК ЭРА, БЦ Upside, ЗИЛ Технопарк и т.п.)
- client_name: заказчик
- object_type: residential, business_center, mixed, infrastructure
- project_date: дата КП в формате YYYY-MM-DD
- invoice_number: номер КП

Верни ТОЛЬКО валидный JSON в формате:
{
  "metadata": {...},
  "items": [...]
}

Без markdown-обёрток, без комментариев. Только JSON.

ТЕКСТ КП:
{kp_text}
"""

async def import_single_kp(file_path: Path):
    # 1. Определить формат и извлечь текст
    if file_path.suffix == '.pdf':
        text = extract_pdf_text(file_path)
    elif file_path.suffix == '.xlsx':
        text = extract_xlsx_text(file_path)
    elif file_path.suffix == '.docx':
        text = extract_docx_text(file_path)
    
    # 2. Вызвать Claude для извлечения структуры
    response = await llm_client.complete_json(
        system="...",
        user=EXTRACTION_PROMPT.format(kp_text=text),
        max_tokens=8000,
        temperature=0,
    )
    
    # 3. Сохранить промежуточный JSON для отладки
    save_json(f"data/extracted/{file_path.stem}.json", response)
    
    # 4. Создать ReferenceProject
    project = ReferenceProject(
        source_file=file_path.name,
        project_name=response['metadata']['project_name'],
        ...
    )
    
    # 5. Для каждой позиции:
    for item_data in response['items']:
        # Сгенерировать search_text
        search_text = build_search_text(item_data)
        
        # Сгенерировать эмбеддинг
        embedding = await embeddings_client.create(search_text)
        
        # Сохранить
        item = ReferenceItem(
            project_id=project.id,
            search_text=search_text,
            embedding=embedding.tobytes(),
            ...
        )
    
    log.info(f"Imported {file_path.name}: {len(items)} positions")


async def main():
    init_db()
    
    kp_files = list(Path("data/reference_kp").glob("*"))
    log.info(f"Found {len(kp_files)} files to import")
    
    for file_path in kp_files:
        try:
            await import_single_kp(file_path)
        except Exception as e:
            log.error(f"Failed to import {file_path}: {e}")
    
    log.info("Import complete")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## ПОИСК ПОХОЖИХ ПОЗИЦИЙ (core/reference_db/retriever.py)

```python
class ReferenceRetriever:
    """
    Находит похожие позиции в исторических КП по семантическому сходству.
    
    Использует cosine similarity на эмбеддингах.
    Для эффективности при росте базы — можно перейти на FAISS,
    но для до 1000 позиций numpy достаточно.
    """
    
    def __init__(self):
        # Загружаем все эмбеддинги в память при старте
        self._items: List[ReferenceItem] = []
        self._embeddings: np.ndarray = None  # shape (N, 1536)
    
    async def load_index(self):
        """Загружает все ReferenceItem.embedding в numpy матрицу"""
        items = await reference_repo.get_all_active()
        self._items = items
        self._embeddings = np.array([
            np.frombuffer(item.embedding, dtype=np.float32) 
            for item in items
        ])
    
    async def find_similar(
        self, 
        query_text: str, 
        top_k: int = 5,
        category_filter: str | None = None
    ) -> List[Tuple[ReferenceItem, float]]:
        """
        Находит top-k похожих позиций.
        
        Возвращает: список (ReferenceItem, similarity_score)
        score: 0–1, где 1 = идентичная позиция
        """
        # Генерируем эмбеддинг запроса
        query_emb = await embeddings_client.create(query_text)
        
        # Cosine similarity со всеми
        norms = np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(query_emb)
        scores = (self._embeddings @ query_emb) / norms
        
        # Фильтр по категории если задан
        if category_filter:
            mask = np.array([item.category == category_filter for item in self._items])
            scores = np.where(mask, scores, -1)
        
        # Top-k
        top_indices = np.argsort(-scores)[:top_k]
        return [(self._items[i], float(scores[i])) for i in top_indices]
    
    def confidence_level(self, score: float) -> str:
        """
        Классификация уверенности:
        - >= 0.85 → 'high' (почти идентичная позиция, можно автоматически предлагать цену)
        - >= 0.60 → 'medium' (похожая, но есть отличия — менеджер должен проверить)
        - < 0.60 → 'low' (нет хороших аналогов — ручная оценка)
        """
        if score >= 0.85:
            return "high"
        elif score >= 0.60:
            return "medium"
        else:
            return "low"
```

---

## ОЦЕНКА ЦЕН (core/estimator/price_estimator.py)

Главный модуль. Здесь происходит магия.

```python
class PriceEstimator:
    """
    Для каждой новой позиции:
    1. Найти top-5 похожих в исторических КП
    2. Передать Claude: новая позиция + 5 прецедентов
    3. Получить: предложенная цена + объяснение
    4. Классифицировать уверенность
    """
    
    async def estimate_batch(
        self, 
        new_items: List[ParsedItem]
    ) -> List[EstimationResult]:
        """
        Батч-оценка всех позиций нового запроса.
        Один вызов Claude на все позиции — экономия токенов.
        """
        # 1. Для каждой позиции находим прецеденты
        items_with_refs = []
        for item in new_items:
            references = await retriever.find_similar(
                item.description, 
                top_k=5
            )
            items_with_refs.append((item, references))
        
        # 2. Формируем промпт
        prompt_data = self._build_prompt_data(items_with_refs)
        
        # 3. Один вызов Claude с structured output
        response = await llm_client.complete_json(
            system=ESTIMATION_SYSTEM_PROMPT,
            user=ESTIMATION_USER_PROMPT.format(**prompt_data),
            max_tokens=4096,
            temperature=0,
        )
        
        # 4. Парсим и валидируем
        results = []
        for item_response in response['estimations']:
            result = EstimationResult(
                original_text=...,
                suggested_price=item_response['unit_price'],
                quantity=item_response['quantity'],
                unit=item_response['unit'],
                confidence=item_response['confidence'],
                reasoning=item_response['reasoning'],
                reference_ids=item_response['based_on_references'],
                method=self._classify_method(item_response['confidence']),
            )
            results.append(result)
        
        return results
    
    def _classify_method(self, confidence: float) -> str:
        if confidence >= 0.85:
            return "auto_high"
        elif confidence >= 0.60:
            return "auto_medium"
        else:
            return "needs_manual"
```

---

## ПРОМПТЫ (core/estimator/prompts.py)

```python
ESTIMATION_SYSTEM_PROMPT = """
Ты — система автоматизированной оценки коммерческих предложений компании ВИЛИНС.

ВИЛИНС производит навигационные системы и металлические изделия для жилых комплексов и бизнес-центров: номера этажей, квартир, таблички, дверные порталы, декоративные панели, стойки.

ТВОЯ ЗАДАЧА:
Для каждой новой позиции от клиента предложить цену на основе исторических прецедентов из похожих проектов.

ПРАВИЛА:

1. ТОЛЬКО на основе прецедентов
   Никогда не придумывай цены из общих знаний рынка. Используй ТОЛЬКО предоставленные исторические прецеденты ВИЛИНС.

2. Прозрачность
   Для каждой оценки укажи на каком прецеденте она основана и почему. Менеджер должен иметь возможность проверить.

3. Честность с уверенностью
   Confidence отражает реальное соответствие прецедентов:
   - 0.9–1.0: позиция почти идентична одному из прецедентов (тот же материал, размер, тип крепления)
   - 0.7–0.89: похожая позиция в прецедентах, но есть отличия (другой размер, другой материал)
   - 0.4–0.69: примерное соответствие — есть схожие позиции, но требуется ручная проверка
   - 0.0–0.39: нет хороших аналогов — обязательно нужна ручная оценка менеджером
   
   НЕ завышай confidence чтобы казаться полезным. Лучше честно сказать "не знаю".

4. Учёт масштабных факторов
   Если в прецеденте было 100 шт по X ₽, а сейчас запрашивают 1000 шт того же самого — цена за штуку обычно та же или чуть ниже. Большие объёмы того же изделия не делают цену радикально другой.
   
   Но если меняется размер (200мм vs 1500мм) — цена меняется радикально.

5. Раздел 2 (подрядные услуги)
   Доставка, упаковка, монтаж, такелаж — учитывай масштаб проекта:
   - Маленький проект (до 500к ₽): доставка 5–10к, упаковка 5–10к
   - Средний (500к–3млн): доставка 10–30к, упаковка 10–20к, монтаж по необходимости
   - Большой (3млн+): доставка 30к+, упаковка 30к+, монтаж/такелаж/накладные
   
   Если в запросе клиента нет позиций раздела 2 — добавь стандартный набор для масштаба проекта.

6. Группировка
   Если в запросе много мелких однотипных позиций (например 10 разных пиктограмм 200×200) — можно сгруппировать в одну строку "Пиктограмма 200×200 (10 типов)" с суммарным количеством.

ВЫХОД: ТОЛЬКО валидный JSON, без markdown.

Формат:
{
  "estimations": [
    {
      "item_index": 0,
      "name": "финальное название позиции для КП",
      "description": "полное описание включая материал и отделку",
      "quantity": число,
      "unit": "шт./м2/компл./м",
      "unit_price": число (без валюты),
      "section": 1 или 2,
      "confidence": 0.0-1.0,
      "based_on_references": [id1, id2, ...],
      "reasoning": "Краткое объяснение: на основе чего предложена цена. Например: 'Идентично позиции NAV1 из ЖК ЭРА (август 2025) — нерж 3мм, стойки, бронза, 200мм. Цена 4280 ₽/шт без изменений.'",
      "needs_manual_review": true/false
    }
  ]
}
"""


ESTIMATION_USER_PROMPT = """
КОНТЕКСТ ПРОЕКТА:
{project_context}

НОВЫЕ ПОЗИЦИИ ОТ КЛИЕНТА (нужно оценить):
{new_items_json}

ИСТОРИЧЕСКИЕ ПРЕЦЕДЕНТЫ (для каждой новой позиции — top-5 похожих случаев из прошлых КП):
{references_json}

Оцени каждую новую позицию.
"""


HISTORY_EXTRACTION_PROMPT = """
[уже описан в import_history.py — см. выше]
"""
```

---

## УНИВЕРСАЛЬНЫЙ ПАРСЕР (core/parsers/universal.py)

```python
class UniversalParser:
    """
    Определяет формат входящего файла и вызывает соответствующий парсер.
    
    Поддерживает:
    - Excel (.xlsx, .xls) → ExcelParser
    - PDF → PDFParser
    - Word (.docx) → DocxParser
    - Текст (свободный текст в Telegram) → TextParser
    
    Возвращает унифицированный список ParsedItem.
    """
    
    async def parse(self, source: ParseSource) -> ParseResult:
        """
        source: ParseSource с полями:
          - file_path: str | None
          - text: str | None
          - file_format: str  # auto-detect
        """
        if source.file_format == "xlsx":
            return await ExcelParser().parse(source.file_path)
        elif source.file_format == "pdf":
            return await PDFParser().parse(source.file_path)
        elif source.file_format == "docx":
            return await DocxParser().parse(source.file_path)
        elif source.file_format == "text":
            return await TextParser().parse(source.text)
        else:
            raise ValueError(f"Unsupported format: {source.file_format}")


@dataclass
class ParsedItem:
    """Универсальный формат позиции после парсинга"""
    original_text: str         # как написано в исходном файле
    suggested_name: str        # очищенное название
    suggested_description: str # очищенное описание
    quantity: Decimal | None   # None если не определилось
    unit: str | None           # None если не определилось
    raw_data: dict             # сырые данные для дебага


@dataclass
class ParseResult:
    items: List[ParsedItem]
    confidence: float          # уверенность парсера в правильности
    needs_manual_review: bool  # true если что-то не распарсилось
    parser_notes: List[str]    # сообщения для менеджера
    project_metadata: dict     # если удалось определить из файла
```

### ExcelParser

```python
class ExcelParser:
    """
    Парсит Excel.
    
    Стратегия:
    1. Если есть лист с понятной структурой (КП Форм, Спецификация, Смета) — берём оттуда
    2. Если нет — извлекаем весь текст всех листов и отдаём в Claude:
       "Найди в этом тексте позиции с количествами"
    """
    
    KNOWN_SHEET_NAMES = ["КП Форм", "Спецификация", "Смета", "Form", "Sheet"]
    
    async def parse(self, file_path: str) -> ParseResult:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        
        # Стратегия 1: ищем стандартный лист
        for sheet_name in wb.sheetnames:
            if any(known in sheet_name for known in self.KNOWN_SHEET_NAMES):
                items = self._parse_structured_sheet(wb[sheet_name])
                if items:
                    return ParseResult(items=items, confidence=0.95, ...)
        
        # Стратегия 2: первый лист по умолчанию + Claude
        all_text = self._extract_all_sheets_text(wb)
        return await self._parse_with_claude(all_text)
    
    def _parse_structured_sheet(self, ws) -> List[ParsedItem]:
        # Ищем строку заголовков (содержит "Описание" и "Количество")
        # Парсим строки ниже
        # Игнорируем строки-итоги (∑, Итого)
        ...
    
    async def _parse_with_claude(self, text: str) -> ParseResult:
        prompt = f"""
Извлеки позиции из этого документа в JSON.
Для каждой позиции: original_text, suggested_name, suggested_description, quantity, unit.
Если позиций не нашёл — верни пустой массив.

ТЕКСТ:
{text}
"""
        response = await llm_client.complete_json(...)
        return ParseResult(items=[ParsedItem(**i) for i in response['items']], ...)
```

### PDFParser

```python
class PDFParser:
    """
    Извлекает текст и таблицы из PDF.
    Использует pdfplumber для таблиц + текста.
    """
    
    async def parse(self, file_path: str) -> ParseResult:
        with pdfplumber.open(file_path) as pdf:
            full_text = ""
            tables = []
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
                tables.extend(page.extract_tables())
        
        # Если есть таблицы — пробуем структурный парсинг
        if tables:
            items = self._parse_tables(tables)
            if items:
                return ParseResult(items=items, confidence=0.85, ...)
        
        # Иначе через Claude
        return await self._parse_with_claude(full_text)
```

### TextParser

```python
class TextParser:
    """
    Парсит свободный текст (когда менеджер скопировал письмо клиента).
    Полностью полагается на Claude.
    """
    
    PARSE_PROMPT = """
Клиент прислал текстовое описание заказа. Извлеки список позиций.

ТЕКСТ КЛИЕНТА:
{text}

Верни JSON:
{{
  "items": [
    {{
      "original_text": "как было в тексте",
      "suggested_name": "краткое название",
      "suggested_description": "полное описание",
      "quantity": число или null,
      "unit": "шт./м2/компл."
    }}
  ],
  "project_hints": {{
    "object_name": "если упомянуто",
    "client_hints": "если упомянуто"
  }},
  "warnings": ["если что-то непонятно"]
}}
"""
```

---

## FSM СОСТОЯНИЯ (bot/states.py)

```python
class EstimationStates(StatesGroup):
    waiting_for_input = State()           # ждём файл или текст
    
    parsing = State()                      # обрабатываем файл
    
    confirming_position = State()          # просмотр позиции с предложенной ценой
    
    manual_price_entry = State()           # ввод ручной цены
    
    editing_quantity = State()             # изменение количества
    
    adding_position_name = State()         # ручное добавление позиции — название
    adding_position_qty = State()          # количество
    adding_position_price = State()        # цена
    
    entering_client_data = State()         # сбор данных клиента
    entering_object_name = State()
    entering_contact_name = State()
    
    final_review = State()                 # финальный просмотр перед PDF
```

---

## ОБРАБОТЧИК UPLOAD (bot/handlers/upload.py)

```python
"""
АЛГОРИТМ:

1. Пользователь отправляет файл или текст
2. Бот: "Обрабатываю запрос..."
3. UniversalParser.parse() → ParseResult
4. Если parser_notes — показываем менеджеру "Я смог распарсить N позиций. Несколько моментов: ..."
5. PriceEstimator.estimate_batch() → List[EstimationResult]
6. Сохраняем черновик Invoice со status="estimating"
7. Переходим в EstimationStates.confirming_position для первой позиции

ОБРАБОТКА ОШИБОК:
- Не удалось распарсить файл → "Не смог разобрать файл. Попробуй: пришли позиции текстом, либо используй /add чтобы добавить вручную"
- LLM не отвечает → "Сервис временно недоступен, попробуй через минуту. Можно пока добавить позиции вручную через /add"
"""

@router.message(F.document)
async def handle_document(message: Message, state: FSMContext, bot: Bot):
    await state.set_state(EstimationStates.parsing)
    await message.answer("⏳ Загружаю и анализирую файл...")
    
    # Скачиваем файл
    file_path = await download_to_temp(bot, message.document)
    file_format = detect_format(file_path)
    
    # Парсим
    try:
        parse_result = await UniversalParser().parse(
            ParseSource(file_path=file_path, file_format=file_format)
        )
    except Exception as e:
        await message.answer(f"❌ Не смог разобрать файл: {e}\n\n"
                            "Попробуй прислать позиции текстом или /add для ручного добавления")
        return
    
    if not parse_result.items:
        await message.answer("❌ В файле не нашёл позиций. "
                            "Пришли список текстом или используй /add")
        return
    
    await message.answer(f"✅ Нашёл {len(parse_result.items)} позиций. "
                         "Подбираю цены на основе прошлых КП...")
    
    # Оцениваем цены
    try:
        estimations = await PriceEstimator().estimate_batch(parse_result.items)
    except Exception as e:
        await message.answer("⚠️ Сервис оценки недоступен. "
                            "Перейдём в ручной режим — введи цены сам")
        # Fallback на ручной режим
        estimations = [empty_estimation(item) for item in parse_result.items]
    
    # Создаём черновик сметы
    invoice_draft = await create_draft_invoice(
        user_id=message.from_user.id,
        items=parse_result.items,
        estimations=estimations,
        source_format=file_format,
    )
    
    # Сохраняем в state
    await state.update_data(invoice_id=invoice_draft.id, current_index=0)
    
    # Переходим к первой позиции
    await state.set_state(EstimationStates.confirming_position)
    await show_position_card(message, invoice_draft.items[0], 0, len(invoice_draft.items))


@router.message(F.text, ~F.text.startswith("/"))
async def handle_text(message: Message, state: FSMContext):
    """Свободный текст → TextParser"""
    # Аналогично, но через TextParser
    ...
```

---

## КЛЮЧЕВОЙ UX: ПОДТВЕРЖДЕНИЕ ПОЗИЦИИ

Это самая важная часть UX. Менеджер проходит по позициям одну за другой.

```python
async def show_position_card(message_or_callback, item: InvoiceItem, index: int, total: int):
    """
    Показывает карточку позиции для подтверждения.
    
    Содержимое карточки зависит от метода оценки:
    - auto_high: чёткое предложение с одним прецедентом
    - auto_medium: предложение с пометкой "нужна проверка"
    - needs_manual: нет аналога, кнопка "Ввести цену"
    """
    confidence_emoji = {
        "auto_high": "🟢",
        "auto_medium": "🟡",
        "needs_manual": "🔴",
    }[item.estimation_method]
    
    # Загружаем прецеденты
    references = await reference_repo.get_by_ids(json.loads(item.reference_item_ids))
    
    # Формируем текст карточки
    text = f"""
{confidence_emoji} Позиция {index+1}/{total}

📋 {item.name}
📝 {item.description}

📦 Количество: {item.quantity} {item.unit}
"""
    
    if item.estimation_method != "needs_manual":
        text += f"""
💰 Предлагаемая цена: {format_money(item.unit_price)}/{item.unit}
💵 Итого по позиции: {format_money(item.total_price)}

🔍 На основе:
"""
        for ref in references[:3]:
            text += f"• {ref.project.project_name} ({ref.project.project_date}) — "
            text += f"{ref.name}: {format_money(ref.unit_price)}/{ref.unit}\n"
        
        text += f"\n💡 {item.estimation_reasoning}"
    else:
        text += "\n⚠️ Нет похожих позиций в истории. Введи цену вручную."
    
    keyboard = build_position_keyboard(item, index, total)
    
    await message.answer(text, reply_markup=keyboard)


def build_position_keyboard(item: InvoiceItem, index: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    
    if item.estimation_method != "needs_manual":
        rows.append([
            InlineKeyboardButton(
                text="✅ Подтвердить", 
                callback_data=f"confirm:{index}"
            ),
            InlineKeyboardButton(
                text="✏️ Изменить цену", 
                callback_data=f"edit_price:{index}"
            ),
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="💰 Ввести цену", 
                callback_data=f"manual_price:{index}"
            ),
        ])
    
    rows.append([
        InlineKeyboardButton(
            text="📊 Изменить количество", 
            callback_data=f"edit_qty:{index}"
        ),
        InlineKeyboardButton(
            text="🔍 Все аналоги", 
            callback_data=f"all_refs:{index}"
        ),
    ])
    
    rows.append([
        InlineKeyboardButton(
            text="❌ Удалить позицию", 
            callback_data=f"delete:{index}"
        ),
    ])
    
    nav_row = []
    if index > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"nav:{index-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{index+1}/{total}", callback_data="noop"))
    if index < total - 1:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"nav:{index+1}"))
    rows.append(nav_row)
    
    rows.append([
        InlineKeyboardButton(
            text="➕ Добавить позицию", 
            callback_data="add_position"
        ),
    ])
    
    # Кнопка "Завершить" доступна только если все позиции подтверждены
    all_confirmed = check_all_confirmed(item.invoice_id)
    if all_confirmed:
        rows.append([
            InlineKeyboardButton(
                text="✅ Сгенерировать смету", 
                callback_data="finalize"
            ),
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

---

## ОБРАБОТЧИК ESTIMATION (bot/handlers/estimation.py)

```python
@router.callback_query(F.data.startswith("confirm:"))
async def confirm_position(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    invoice_id = data['invoice_id']
    
    # Помечаем как подтверждённую
    await invoice_repo.confirm_item(invoice_id, index)
    
    await callback.answer("✅ Подтверждено")
    
    # Переход к следующей не-подтверждённой
    next_index = await find_next_unconfirmed(invoice_id, index)
    
    if next_index is not None:
        item = await invoice_repo.get_item(invoice_id, next_index)
        await show_position_card(callback.message, item, next_index, total)
    else:
        # Все подтверждены — переход к финалу
        await show_summary(callback.message, invoice_id, state)


@router.callback_query(F.data.startswith("edit_price:"))
async def edit_price_request(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.update_data(editing_index=index)
    await state.set_state(EstimationStates.manual_price_entry)
    await callback.message.answer("Введи новую цену за единицу (число в рублях):")


@router.message(EstimationStates.manual_price_entry)
async def edit_price_value(message: Message, state: FSMContext):
    try:
        new_price = Decimal(message.text.replace(',', '.').replace(' ', ''))
        if new_price <= 0:
            raise ValueError("Цена должна быть положительной")
    except (ValueError, InvalidOperation):
        await message.answer("❌ Не понял число. Пример: 4280 или 4280.50")
        return
    
    data = await state.get_data()
    invoice_id = data['invoice_id']
    index = data['editing_index']
    
    # Обновляем
    await invoice_repo.update_item_price(invoice_id, index, new_price, was_modified=True)
    
    # Возвращаемся к карточке
    await state.set_state(EstimationStates.confirming_position)
    item = await invoice_repo.get_item(invoice_id, index)
    await show_position_card(message, item, index, total)


@router.callback_query(F.data.startswith("all_refs:"))
async def show_all_references(callback: CallbackQuery, state: FSMContext):
    """Показать все 5 прецедентов для позиции"""
    index = int(callback.data.split(":")[1])
    item = await invoice_repo.get_item_by_index(invoice_id, index)
    references = await reference_repo.get_by_ids(json.loads(item.reference_item_ids))
    
    text = f"🔍 Все аналоги для «{item.name}»:\n\n"
    for i, ref in enumerate(references, 1):
        text += f"{i}. {ref.project.project_name} ({ref.project.project_date})\n"
        text += f"   {ref.name}\n"
        text += f"   {ref.description[:100]}...\n"
        text += f"   💰 {format_money(ref.unit_price)}/{ref.unit} × {ref.quantity} = {format_money(ref.total_price)}\n\n"
    
    await callback.message.answer(text)
```

---

## СБОР ДАННЫХ КЛИЕНТА И ФИНАЛИЗАЦИЯ

```python
async def show_summary(message: Message, invoice_id: int, state: FSMContext):
    """После подтверждения всех позиций — собираем данные клиента"""
    invoice = await invoice_repo.get_with_items(invoice_id)
    
    text = f"""✅ Все позиции подтверждены!

📋 Краткая сводка:
"""
    for item in invoice.items:
        text += f"• {item.name}: {item.quantity} {item.unit} × {format_money(item.unit_price)} = {format_money(item.total_price)}\n"
    
    text += f"""
━━━━━━━━━━━━━━
💰 Раздел 1: {format_money(invoice.total_section1)}
💰 Раздел 2: {format_money(invoice.total_section2)}
💰 ИТОГО: {format_money(invoice.total_amount)}

Теперь введи данные для шапки КП:
"""
    
    await state.set_state(EstimationStates.entering_client_data)
    await message.answer(text + "\nНазвание объекта (например 'ЖК ЭРА'):")


@router.message(EstimationStates.entering_client_data)
async def enter_object_name(message: Message, state: FSMContext):
    await invoice_repo.update_field(invoice_id, "object_name", message.text)
    await state.set_state(EstimationStates.entering_object_name)
    await message.answer("Имя заказчика (или /skip):")


# ... дальше по аналогии для contact_name


@router.callback_query(F.data == "finalize")
async def finalize_invoice(callback: CallbackQuery, state: FSMContext):
    """Генерация PDF и завершение"""
    data = await state.get_data()
    invoice_id = data['invoice_id']
    
    invoice = await invoice_repo.get_with_items(invoice_id)
    
    await callback.message.answer("📄 Генерирую PDF...")
    
    pdf_bytes = await PDFGenerator().generate(invoice)
    
    # Отправляем PDF
    pdf_file = BufferedInputFile(pdf_bytes, filename=f"КП_{invoice.invoice_number}.pdf")
    await callback.message.answer_document(
        document=pdf_file,
        caption=f"✅ Смета готова!\n\nКП № {invoice.invoice_number}\nИтого: {format_money(invoice.total_amount)}"
    )
    
    # Помечаем смету как готовую
    await invoice_repo.mark_completed(invoice_id)
    
    # ВАЖНО: добавляем эту смету в базу прецедентов для будущих расчётов
    await reference_repo.import_from_invoice(invoice_id)
    
    await state.clear()
```

---

## САМООБУЧЕНИЕ: НОВАЯ СМЕТА → НОВЫЕ ПРЕЦЕДЕНТЫ

Это ключевая фича для долгосрочного качества:

```python
async def import_from_invoice(invoice_id: int):
    """
    После генерации финального PDF —
    добавляем все позиции этой сметы в ReferenceItem
    для использования в будущих расчётах.
    """
    invoice = await invoice_repo.get_with_items(invoice_id)
    
    # Создаём ReferenceProject для этой сметы
    ref_project = ReferenceProject(
        source_file=f"invoice_{invoice.id}",
        project_name=invoice.object_name or f"Проект #{invoice.id}",
        client_name=invoice.client_name,
        project_date=invoice.created_at.date(),
        total_amount=invoice.total_amount,
        items_count=len(invoice.items),
        ...
    )
    
    # Каждую позицию — в ReferenceItem
    for item in invoice.items:
        if item.was_confirmed:  # только подтверждённые
            ref_item = ReferenceItem(
                project_id=ref_project.id,
                name=item.name,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total_price=item.total_price,
                section=item.section,
                category=detect_category(item.name, item.description),
                search_text=build_search_text(item),
                embedding=await embeddings_client.create(search_text).tobytes(),
            )
    
    log.info(f"Added {len(invoice.items)} new references from invoice {invoice_id}")
```

---

## LLM КЛИЕНТ (core/llm/client.py)

```python
class LLMClient:
    """
    Обёртка над Claude API через ProxyAPI.
    """
    
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY,
            base_url=config.ANTHROPIC_BASE_URL,
        )
    
    async def complete(
        self, system: str, user: str,
        max_tokens: int = 4096,
        temperature: float = 0,
        use_fallback: bool = False,
    ) -> str:
        model = config.FALLBACK_MODEL if use_fallback else config.PRIMARY_MODEL
        
        for attempt in range(3):
            try:
                response = await self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                
                # Логируем расход
                log.info(f"LLM call: model={model}, "
                         f"in={response.usage.input_tokens}, "
                         f"out={response.usage.output_tokens}")
                
                return response.content[0].text
                
            except anthropic.APIError as e:
                wait = 2 ** attempt
                log.warning(f"API error attempt {attempt+1}: {e}, retry in {wait}s")
                await asyncio.sleep(wait)
        
        # Все попытки primary failed → fallback
        if not use_fallback:
            log.warning(f"Switching to fallback model {config.FALLBACK_MODEL}")
            return await self.complete(system, user, max_tokens, temperature, use_fallback=True)
        
        raise RuntimeError("LLM unavailable after all retries")
    
    async def complete_json(self, system: str, user: str, **kwargs) -> dict:
        text = await self.complete(system, user, **kwargs)
        # Очищаем от markdown
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
```

---

## EMBEDDINGS CLIENT (core/llm/embeddings_client.py)

```python
class EmbeddingsClient:
    """
    OpenAI text-embedding-3-small через ProxyAPI.
    1536 dimensions, $0.02 / 1M tokens.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
    
    async def create(self, text: str) -> np.ndarray:
        """Генерирует один эмбеддинг"""
        response = await self.client.embeddings.create(
            model=config.EMBEDDINGS_MODEL,
            input=text[:8000],  # обрезаем
        )
        return np.array(response.data[0].embedding, dtype=np.float32)
    
    async def create_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Батч для эффективности"""
        response = await self.client.embeddings.create(
            model=config.EMBEDDINGS_MODEL,
            input=[t[:8000] for t in texts],
        )
        return [np.array(d.embedding, dtype=np.float32) for d in response.data]
```

---

## ГЕНЕРАЦИЯ PDF

См. предыдущую версию ТЗ — структура шаблона та же, но данные теперь из Invoice + InvoiceItem.

Главное:
- Использовать Jinja2 + WeasyPrint
- Шаблон invoice.html копирует фирменный стиль ВИЛИНС из существующих PDF
- Логотип в углу, чёрно-белый стиль таблиц, бронзовые акценты
- Сумма прописью через num2words

---

## ПОРЯДОК РЕАЛИЗАЦИИ ДЛЯ CLAUDE CODE

### Этап 1 — Инфраструктура (день 1-2)
1. `requirements.txt`, `.env.example`, `config.py`
2. `db/models.py` — все модели
3. `db/database.py` — инициализация SQLAlchemy async
4. `db/reference_repo.py`, `db/invoice_repo.py` — CRUD
5. `main.py` — заглушка с polling

### Этап 2 — LLM-клиенты (день 2)
6. `core/llm/client.py` — Claude через ProxyAPI
7. `core/llm/embeddings_client.py` — OpenAI embeddings через ProxyAPI

### Этап 3 — Импорт исторических КП (день 3-4) ⭐ КРИТИЧНО
8. `core/parsers/pdf_parser.py` — извлечение текста PDF
9. `core/parsers/excel_parser.py` — Excel
10. `core/parsers/docx_parser.py` — Word
11. `scripts/import_history.py` — импорт 10 КП
12. **Запустить импорт, проверить результат в БД**

### Этап 4 — Поиск похожих (день 4)
13. `core/reference_db/embeddings.py` — генерация эмбеддингов
14. `core/reference_db/retriever.py` — поиск по similarity
15. **Тест: для тестовой позиции получить top-5 похожих, проверить логику**

### Этап 5 — Оценка цен (день 5)
16. `core/estimator/prompts.py` — все промпты
17. `core/estimator/price_estimator.py` — главный модуль оценки
18. **Тест на реальном Excel: получить смету с предложенными ценами**

### Этап 6 — Генерация PDF (день 6)
19. `core/pdf/templates/invoice.html` + `invoice.css`
20. `core/pdf/generator.py`
21. **Тест: сгенерировать PDF из тестового Invoice**

### Этап 7 — Telegram бот (день 7-9)
22. `bot/states.py` — FSM
23. `bot/keyboards/inline.py` — клавиатуры
24. `bot/handlers/start.py`
25. `bot/handlers/upload.py`
26. `bot/handlers/estimation.py` — самый сложный, пошаговое подтверждение
27. `bot/handlers/manual.py` — ручной ввод
28. `bot/handlers/confirm.py` — финал и PDF
29. `bot/handlers/admin.py`
30. `bot/router.py`

### Этап 8 — Самообучение (день 9)
31. После генерации финального PDF — автоматически добавлять Invoice в ReferenceProject
32. **Тест: создать смету, проверить что её позиции появились в reference_items**

### Этап 9 — Тестирование и деплой (день 10-12)
33. Прогон 5–10 реальных запросов от менеджеров
34. Калибровка промптов и порогов
35. Деплой на VPS через systemd
36. README с инструкцией

---

## КРИТИЧЕСКИЕ ЗАМЕЧАНИЯ ДЛЯ CLAUDE CODE

### 1. Импорт истории — это самый важный шаг
Без качественного импорта 10 КП бот работать не будет. После импорта:
- Проверь количество ReferenceItem в БД (ожидаемо 50-150)
- Проверь что у каждой есть embedding
- Запусти тест: для текста "номер этажа из нержавейки" должны находиться NAV1/NAV1.1 из ЖК ЭРА с высоким score

### 2. Структурированный вывод Claude
Везде где LLM возвращает JSON:
- `temperature=0`
- `system_prompt` с явным "ТОЛЬКО JSON, без markdown"
- В `complete_json` обязательная очистка от ```json``` обёрток
- Pydantic-валидация результата

### 3. Никаких цен из общих знаний
В промпте оценки:
> "Используй ТОЛЬКО предоставленные исторические прецеденты ВИЛИНС. Не используй знания о рынке."

### 4. Confidence — честный
Бот должен признавать что не знает, а не угадывать:
- Если top-1 score < 0.6 → method = "needs_manual"
- Если запрос радикально отличается от всех прецедентов → честно сказать

### 5. UX подтверждения
Менеджер должен:
- Видеть предложение
- Видеть на чём оно основано
- Иметь возможность поправить одной кнопкой
- Видеть прогресс (5/12)

### 6. Самообучение — после подтверждения, не до
В ReferenceItem попадают только полностью подтверждённые менеджером позиции. Черновики и отменённые сметы — нет.

### 7. Графцулная деградация
Если Claude API недоступен:
- Парсинг ещё может работать (структурный Excel)
- Оценка цен → fallback на ручной ввод
- Менеджер должен иметь возможность создать смету вообще без Claude через /add

### 8. Категория позиции
В ReferenceItem.category — одна из:
- `navigation` — все номера, таблички, пиктограммы
- `door_portal` — дверные порталы
- `panel` — декоративные панели
- `stand` — стойки (ресепшн, барные)
- `service` — раздел 2 (доставка, упаковка, монтаж)
- `other` — всё остальное

При поиске прецедентов можно фильтровать по категории для повышения точности.
