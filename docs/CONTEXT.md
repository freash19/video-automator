# Project Context: HeyGen Automation Hub

## Architecture Overview

**Frontend**: React (Vite), TypeScript, TailwindCSS, Radix UI, Lucide React.

**Backend**: Python 3.14+, FastAPI, Playwright для автоматизации браузера.

**Agent Intelligence**: Cursor Custom Agents (Architect, Coder, Reviewer).

**Discovery Layer**: tools/inspector.py — автономный модуль исследования DOM и генерации визуальных отчетов.

**Data Flow**: Frontend -> API (FastAPI) -> Playwright -> HeyGen Website.

---

## Key Files Map

### Frontend (genmaster-hub-main/src/)

- `pages/Workflow.tsx`: Основная страница управления файлами воркфлоу.
- `components/workflow/WorkflowBuilder.tsx`: Визуальный редактор шагов автоматизации.

### Core Modules (core/)

- `core/config.py`: Pydantic Settings для API-ключей и секретов (.env).
- `core/types.py`: Общие модели данных (TaskStatus, AutomationStep, Metrics, StepStatus).
- `core/browser.py`: Утилиты браузера (safe_click, scroll, screenshot).
- `core/scenes.py`: Логика заполнения и валидации сцен.
- `core/broll.py`: Поиск и вставка B-roll, поддержка Nano Banano.
- `core/workflow.py`: Исполнение шагов воркфлоу.

### Utils (utils/)

- `utils/helpers.py`: Функции нормализации данных, парсинга.
- `utils/csv_parser.py`: Загрузка и валидация CSV-файлов сценариев.
- `utils/clipboard.py`: Операции с буфером обмена (macOS), генерация изображений Nano Banano.

### Backend & Automation (/)

- `heygen_automation.py`: Координатор системы. Класс HeyGenAutomation, _run_workflow, импорты из core/.
- `automation_models.py`: Pydantic-модели (TaskStatus, AutomationStep) — backward compatibility.
- `ui/api.py`: FastAPI эндпоинты.
- `ui/runner.py`: Логика запуска автоматизации.
- `ui/step_wrapper.py`: Декоратор @step для логирования и скриншотов.
- `ui/logger.py`: Настройка логгера (automation.log).

### Tools (tools/)

- `tools/inspector.py`: "Глаза" системы — парсинг селекторов, аннотированные скриншоты.
- `tools/healthcheck.py`: Проверка доступности браузера/сервиса.

### Configuration

- `.env`: API-ключи (GOOGLE_API_KEY, TELEGRAM_BOT_TOKEN, и др.).
- `config.json`: Настройки автоматизации (CSV, профили браузера, таймауты).
- `.cursorrules`: Глобальная "Конституция" проекта, стандарты кода и селекторов.

---

## Debug & Logs

- `automation.log`: Единый файл для записи событий в формате `[TIMESTAMP] [LEVEL] [StepName] Message`.
- `debug/inspection/`: Результаты инспектора (report.json, annotated.png).
- `debug/screenshots/`: Скриншоты при ошибках.
- `debug/auth_state.json`: Сохраненное состояние сессии браузера.

---

## Data Structures

### Workflow Step (JSON)

```json
{
  "id": "uuid",
  "type": "navigate | wait_for | click | fill | fill_scene | handle_broll | ...",
  "params": {
    "url": "...",
    "selector": "...",
    "value": "..."
  },
  "name": "Step Name"
}
```

### Settings (core/config.py)

```python
class Settings(BaseSettings):
    google_api_key: str = ""          # Nano Banano
    telegram_bot_token: str = ""
    nano_banano_model: str = "nano-banano-pro"
    # ...
```

---

## Conventions & Agentic Standards

### Selector Strategy (Strict)

1. `data-testid`: Приоритет №1. Если отсутствует в нашем UI — агент обязан его добавить.
2. Stable Attributes: Для HeyGen использовать aria-label, role или стабильный текст.
3. **Forbidden**: Динамические CSS-классы (например, `.css-1x2y3z`) строго запрещены.

### Error Handling & Reporting

- **Step Wrapper**: Каждое действие должно использовать декоратор `@step` или `perform_step`.
- **Non-blocking Failures**: Некритичные ошибки логируются, но не останавливают процесс.
- **Observability**: Все сбои сопровождаются скриншотом и записью в automation.log.

### Secret Management

- Все API-ключи загружаются через `core/config.py` (Pydantic Settings).
- Запрещены `os.getenv()` в бизнес-логике — только через `get_settings()`.
- Секреты документированы в `.env.example`.

---

## Agent Workflow (SOP)

1. **Read**: Проверить docs/PLAN.md и docs/CONTEXT.md перед началом работы.
2. **Research**: Если селекторы неизвестны — использовать tools/inspector.py.
3. **Implement**: Следовать .cursorrules (Async, Type Hints, Step Wrapper).
4. **Report**: Обновить статус задачи в PLAN.md.

---

## Domain Context

Проект автоматизирует создание видео для YouTube-каналов о здоровье:
- **Тематики**: долголетие, питание, мужское здоровье
- **ИИ-персонажи**: Dr. Peter (Medical), Michael (Nutrition), Hiroshi (Longevity)
- **Локации**: студия "STUDIO"
- **Визуальная консистентность** этих элементов критически важна.

### Nano Banano Integration

Генерация изображений через Google AI Studio API:
- Префикс в broll_query: `NANO_BANANO: <prompt>`
- Изображение генерируется, сохраняется в project_dir, копируется в буфер, вставляется в сцену.
