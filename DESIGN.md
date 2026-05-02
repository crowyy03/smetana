# Design

## Theme

**Bicameral.** Две полноценных темы, не «светлая по умолчанию + dark-mode-overlay».

- **День** — бумага архитектора. Тёплый off-white с лёгким графитовым подтоном, ink-чёрный с тёплым уклоном. Чувство — лист ватмана на чертёжной доске под мягким северным светом.
- **Ночь** — тушь и металл. Глубокий ink с прохладным синим уклоном, серебристые нейтрали, та же акцентная семья, но в нижней части тоновой шкалы. Чувство — открытый редактор макета в 2 ночи в студии.

Переключение — не мгновенное и не fade. **Shadow-loom**: при клике на toggle от точки клика расходится радиальная тень, накрывает интерфейс целиком (~700ms, ease-out-expo), под ней проступает новая тема. Технически: `document.startViewTransition()` + `clip-path: circle()` от координат toggle, плюс наложение полупрозрачной тёмной/светлой пелены поверх. При `prefers-reduced-motion: reduce` — обычный мгновенный swap.

Начальная тема — по `prefers-color-scheme`, с пользовательским override в localStorage и серверным cookie для предотвращения FOUC.

## Color

Стратегия: **Restrained** (тонированные нейтрали + один сдержанный акцент ≤10% поверхности). Допустимо переходить в **Committed** на одиночных «brand-моментах» — экран входа, hero на дашборде.

Все значения в OKLCH. Хрома уменьшается у крайних значений lightness — никаких ярких цветов в самых тёмных и самых светлых тонах.

### Light (День)

```
--surface-page:    oklch(98.5% 0.004 80)   /* тёплая бумага */
--surface-card:    oklch(99.5% 0.003 80)   /* почти-белый, чуть теплее page */
--surface-sunken:  oklch(96.5% 0.005 80)   /* фон таблиц, кодовых блоков */
--ink-strong:      oklch(18%   0.012 60)   /* основной текст, ink с тёплым уклоном */
--ink-default:     oklch(28%   0.010 60)
--ink-muted:       oklch(48%   0.008 60)
--ink-subtle:      oklch(65%   0.006 60)
--line-strong:     oklch(82%   0.006 60)
--line-default:    oklch(90%   0.005 60)
--line-subtle:     oklch(94%   0.004 60)
--accent:          oklch(38%   0.058 240) /* холодный графитово-синий, ink-grade */
--accent-hover:    oklch(32%   0.062 240)
--accent-bg:       oklch(94%   0.020 240) /* фон для tag/selected */
--success:         oklch(48%   0.055 155)
--warn:            oklch(58%   0.080 70)
--danger:          oklch(48%   0.090 25)
```

### Dark (Ночь)

```
--surface-page:    oklch(15%   0.012 250)  /* deep ink, прохладный уклон */
--surface-card:    oklch(19%   0.013 250)
--surface-sunken:  oklch(12%   0.010 250)
--ink-strong:      oklch(96%   0.005 80)   /* тёплый off-white, не чисто белый */
--ink-default:     oklch(86%   0.006 80)
--ink-muted:       oklch(64%   0.008 80)
--ink-subtle:      oklch(48%   0.008 80)
--line-strong:     oklch(35%   0.012 250)
--line-default:    oklch(28%   0.011 250)
--line-subtle:     oklch(22%   0.010 250)
--accent:          oklch(75%   0.080 240) /* тот же холодный синий, поднят по lightness */
--accent-hover:    oklch(82%   0.085 240)
--accent-bg:       oklch(28%   0.040 240)
--success:         oklch(72%   0.090 155)
--warn:            oklch(78%   0.110 70)
--danger:          oklch(70%   0.130 25)
```

Ровно один акцентный hue (≈240) в обеих темах. Никаких разноцветных «лотерейных» статусов: success/warn/danger используются **только** для системных индикаторов (ошибка валидации, успех импорта, удаление). Внутри сметы статусы (auto / review / manual) различаются типографикой, иконкой и плотностью линии — не цветом.

## Typography

### Семейства

- **Display** — `Fraunces` (Google Fonts, variable, OFL). Используется в крупных заголовках, hero, итоговых суммах. Включён `opsz` axis (динамический optical size) и `SOFT` axis (90 — мягче формы).
- **UI / Body** — `Geist Sans` (variable, OFL via Vercel CDN или self-hosted). Без жирности выше 600 в UI; 700 только в display-моментах в редкой связке с Fraunces.
- **Mono / numeric** — `Geist Mono` (variable, OFL). Используется для сумм, идентификаторов смет, embeddings-метрик, debug-блоков.

Запрет на Inter и системные стеки, кроме fallback-цепочки.

### Шкала

Modular scale 1.250 (major third), базовый `1rem = 16px`:

```
text-2xs   11.5px   /* подписи под колонками */
text-xs    12.8px   /* meta, breadcrumb */
text-sm    14px     /* плотные таблицы, форма */
text-base  16px     /* body */
text-lg    20px     /* акцентный body, lead */
text-xl    25px     /* sub-heading */
text-2xl   31px     /* page heading */
text-3xl   39px     /* section heading */
text-4xl   49px     /* hero / итоговая сумма */
text-5xl   61px     /* display heading (login, главная) */
text-6xl   76px     /* one-shot heroes */
```

### Числа

Везде, где встречаются цифры (цены, количества, итоги, % уверенности, даты, ID), включён `font-variant-numeric: tabular-nums slashed-zero`. В Geist это поддерживается нативно, в Fraunces — через variable axes.

В таблице цен:
- Названия позиций — Geist Sans 14/20.
- Цены и суммы — Geist Mono 14/20, выровнены по правому краю, разряды разделены ` ` (NARROW NO-BREAK SPACE) — НЕ пробелом и не точкой.
- Итог сметы — Fraunces 39px display, тоже tabular.

### Микро-правила

- Line-height в body: 1.55. В таблицах: 1.4. В display: 1.05–1.15.
- Letter-spacing: 0 для body, −0.012em для display 31px+, +0.04em uppercase для micro-labels (например, «РАЗДЕЛ 1»).
- **Тире (—) в ru-RU копи разрешено и обязательно** там, где этого требует русская типографика: между подлежащим и сказуемым при опущенной связке («Каждая смета — точная»), при пояснении («ВИЛИНС — производитель навигационных систем»), при противопоставлении. Это **переписывает** дефолтное правило impeccable «no em-dashes» — оно writted для английского, где тире чаще всего декоративная пауза.
  - **Что по-прежнему запрещено:** декоративный em-dash в стиле «делает X — быстро — точно», когда тире только заменяет запятую ради эффекта; тире вместо двоеточия перед списком; тире там, где напрашивается период.
  - В коде, токенах, JSON, ID — никаких тире (только дефис `-`).
  - `--` (двойной дефис) запрещён везде — это маркер опечатки.

## Layout

### Сетка

12-колоночная только в content-страницах (логин, дашборд hero). Все продуктовые экраны — **гибкая колонка с max-width**:

- `--content-narrow: 720px` — формы, авторизация
- `--content-default: 1080px` — таблицы, списки
- `--content-wide: 1320px` — построчное подтверждение сметы (нужен горизонтальный простор)
- `--content-bleed: 100%` — страницы PDF-просмотра

### Spacing

База 4px. Шкала 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64 / 80 / 96 / 128.

Принцип ритма: вертикальные расстояния между блоками **не одинаковые**. Между подзаголовком и его контентом — 16, между блоком и следующим блоком — 48–64. Это создаёт пульс, а не равномерный сетеподобный пол.

### App shell

Двух-режимный, в зависимости от страницы:

- **Editorial-режим** — `/`, `/login`, `/profile`, главная сметы. Узкая фиксированная шапка (`64px`), без sidebar, контент центрирован, generous spacing. Это «лицо» инструмента.
- **Workhorse-режим** — `/estimates`, `/references`, страница построчного подтверждения. Та же шапка, но появляется компактная боковая колонка с фильтрами и быстрой навигацией. Boundary между секциями — `1px` линии `--line-default`, не `box-shadow`.

Cards — только когда плитка действительно нужна (карточка проекта в `/references`). Списки и таблицы — без cards. Никаких card-in-card.

## Components

### Buttons

Три уровня + один link-вариант:

- **Primary** — solid `accent`, текст `surface-page`, без border. Hover: `accent-hover`. Активное действие на странице, ровно одна штука.
- **Secondary** — `1px` border `line-strong`, текст `ink-strong`, transparent fill. Hover: fill = `surface-sunken`.
- **Ghost** — text-only, без border. Используется в плотных таблицах для inline-действий.
- **Link** — `accent`, `text-underline-offset: 4px`, decoration-thickness 1px. Underline появляется только на hover/focus.

Высоты: 32 (sm) / 40 (default) / 48 (lg). Радиус — `6px` везде. Никакого `pill` (rounded-full) кроме аватаров.

### Input fields

`1px` border `line-strong`, фон `surface-card` (день) / `surface-sunken` (ночь), padding `12px 14px`, текст 14px. Focus: border `accent`, тень `0 0 0 3px accent-bg`, без glow. Лейбл всегда **над** полем (top-aligned, 13px, `ink-muted`), не floating, не placeholder-as-label.

### Tables

Сердце продукта. На странице построчного подтверждения смет — стол на 100% ширины content-wide.

- Заголовки — uppercase 11.5px, `ink-muted`, letter-spacing +0.04em.
- Строки — 56px высота (плотный режим — 44px). Vertical separator только под заголовками.
- Hover-row — фон `surface-sunken`, без анимации.
- Selected/active row — `2px` бордер слева цвета `accent`, фон `accent-bg` с альфой 0.4.
- Цена и кол-во — Geist Mono, текст-align right.
- Колонка «обоснование» (reference) — отдельная зона с микро-чипом «kp_2025-01_zil_technopark» в моноспейс + кликабельный линк.

### Status & confidence

Уверенность LLM — главная семантика в позиции. Не делаем светофор. Делаем:

- `≥ 0.85` (high) — без декорации, просто строка.
- `0.6 – 0.85` (medium) — слева от цены ставится `· ·` (две точки `ink-muted`), tooltip «требует проверки».
- `< 0.6` (low / manual) — placeholder вместо цены: `— требуется ручная оценка` курсивом, `ink-muted`.

В мобайле всё то же, плюс плашки выделяются толщиной линии слева, не цветом.

### Cards (только где они нужны)

Карточка прецедента (`/references`):
- Радиус 8px, border `1px line-default`, фон `surface-card`.
- Padding `24px 24px 20px`.
- Hover: border → `line-strong`, поднятие на 1px (`translateY(-1px)`).
- Внутри: project_name display 20px Fraunces, ниже client + дата micro 12px ink-muted, далее 1-line summary, в углу — items_count и total_amount.

### Modals

Допустимы только для деструктивных действий и multi-step мастеров (импорт KP). Для обычных диалогов — inline-раскрытие или drawer справа.

Backdrop: `surface-page` с альфой 0.55, blur запрещён.

### Dialogs (drawer)

Слайдер справа (`max-width: 480px`), фон `surface-card`, тень `0 24px 48px -16px oklch(0% 0 0 / 0.18)` в день / `0 24px 48px -16px oklch(0% 0 0 / 0.6)` в ночь.

## Motion

### Easing

Стандарт — `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out-expo). Для очень коротких микро-движений — `cubic-bezier(0.4, 0, 0.2, 1)` (ease-out-quart).

### Длительность

- Hover/focus state change: 120ms
- Inline reveal (drawer accordion раздел): 240ms
- Page transitions (View Transitions API): 320ms
- Shadow-loom (theme switch): 700ms ease-out-expo
- Toast in/out: 200ms / 160ms

### Запреты

- Нет `transition: all`. Только конкретные свойства (`background-color`, `border-color`, `transform`, `opacity`, `clip-path`).
- Не анимировать `width`, `height`, `top`, `left`, `margin`, `padding`. Только `transform`, `opacity`, `clip-path`, `filter`.
- Никаких bounce / elastic / spring-overshoot.

### Сигнатурные моменты

1. **Shadow-loom theme switch** — описан выше. Реализуется через `::view-transition-old(root)` + `::view-transition-new(root)` с `clip-path: circle()` от точки клика, плюс короткое наложение dim-слоя на пик анимации.

2. **Estimate-row commit** — при подтверждении строки в таблице сметы строка делает мягкое «осаждение»: `transform: translateY(0)` со старта `translateY(-2px)`, opacity 0.85 → 1, 240ms ease-out-expo. Без вспышки цвета.

3. **Login-screen entrance** — заголовок (Fraunces 76px) собирается из вертикали: `clip-path: inset(100% 0 0 0)` → `inset(0 0 0 0)`, 600ms, с задержкой 80ms между двумя строчками.

## Iconography

`Lucide` icons (variable stroke), 1.5px stroke в день / 1.25px в ночь (тоньше, потому что тёмный фон визуально утолщает). Размер по умолчанию 16px. В таблицах — 14px.

Никаких emoji в UI. В формах сообщений к КП — допустимо (текст пользователя).

## Imagery

- Логотип ВИЛИНС — на странице PDF preview и на login. Везде остальное — без декоративных изображений.
- Если нужны иллюстрации (404, empty states), используется монохромный line-art, тонкий stroke, цвет — `ink-muted`. Никаких 3D-рендеров и стоков.

## Anti-patterns (project-specific)

В дополнение к глобальным запретам impeccable:

- **Цветной статус-бейдж** в таблице сметы. Status передаётся типографикой и иконкой.
- **Карточки с одинаковыми скруглёнными углами и тенями** в дашборде. Дашборд — это типографика и числа, не grid карточек.
- **Sidebar шириной 240px+** на узких экранах. Sidebar — компактный (200px max), сворачивается на ≤1100px.
- **Гладкий цельно-цветной фон в hero** (`bg-blue-600 text-white`). Hero на главной — это типографика на бумажном фоне с одной осмысленной цветной деталью.
- **Toast в углу с цветной полоской слева.** Toasts — `surface-card` + 1px line-strong + типографика.
