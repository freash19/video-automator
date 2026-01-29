# Project Plan: HeyGen Automation Hub

## Current Status
- **Backend**: Python/FastAPI (running on port 8000).
- **Frontend**: React/Vite (running on port 5173).
- **Core Features**:
  - Workflow Builder (Visual Step Editor).
  - Locator Library (API & UI).
  - Automa Import (Partial).

## Completed Tasks (Sprint 1)
- [x] **JSON Step Editor**: Implemented in `WorkflowBuilder.tsx`. Users can edit raw JSON for any step.
- [x] **Workflow File JSON Editor**: Implemented in `Workflow.tsx`. Users can edit the entire workflow file.
- [x] **Episode Selection Workflow**: Created `workflows/select_episode_parts.json` template.
- [x] **Advanced Step UI**: Added UI support for `select_episode_parts` in `WorkflowBuilder.tsx`.
- [x] **Multi-Agent Setup**: Defined `docs/AGENTS.md` and `docs/CONTEXT.md`.
- [x] **UI Inspector Tool**: Created `tools/inspector.py` for autonomous UI exploration.
- [x] **Step Wrapper + TaskStatus**: Updated Step Wrapper behavior and speaker-aware scene steps in `heygen_automation.py`.
- [x] **Open Browser Button**: Added API endpoint and UI button on runner page.
- [x] **Task Error Report**: Added per-task error report summary in Runner tasks list.
- [x] **Task Report Details**: Added scene/B-roll details and step skip/failure lists in tasks.
- [x] **Part Title Before Scenes**: Inserted part title into “Без названия — видео” field before scenes.
- [x] **Project Status Badge**: Moved status to bottom-right badge with color states.
- [x] **Generation Toggle**: Added config setting to skip generation and save only.
- [x] **Scripts Section Removed**: Removed “Сценарии” section from navigation/routes.
- [x] **Telegram Task Notifications**: Added Telegram updates for task status and report summary.

## Completed: Project Sanitation & Architecture Refactoring (Sprint 2)

**Date**: January 2026

### Files Deleted
- `old/` folder (legacy code, instructions)
- `heygen_automation_alpha.py` (superseded)
- `heygen_automation_mac.zip` (archive)
- `automa.json`, `canva.html`, `scens.html`, `settings.html` (dev artifacts)
- `sleep_diabetes.csv`, `scenarios.csv` (test data)
- `state/run_projects_*.csv` (historical run files)
- `.trae/` folder (TRAE docs)

### New Modular Architecture
Created `core/` and `utils/` packages:
- `core/config.py` - Pydantic Settings for API keys (.env)
- `core/types.py` - Shared models (TaskStatus, AutomationStep, Metrics)
- `core/browser.py` - Browser utilities (safe_click, screenshot)
- `core/scenes.py` - Scene filling and validation
- `core/broll.py` - B-roll search, Nano Banano integration
- `core/workflow.py` - Workflow step execution
- `utils/helpers.py` - Data normalization functions
- `utils/csv_parser.py` - CSV loading and validation
- `utils/clipboard.py` - Clipboard operations (macOS)

### Code Quality Improvements
- Replaced 147/148 `print()` statements with `logger` calls
- Added `@step` decorators to critical methods
- Verified no circular imports between modules
- Updated imports in `heygen_automation.py` to use new modules

### Documentation Updated
- `docs/CONTEXT.md` - New architecture documented
- `docs/PLAN.md` - Audit task marked complete

---

## Active Task: Automa Import Fix
**Goal**: The current Automa import maps many steps to generic or "unknown" types. We need to map "blockbasic" and other Automa specific types to our `navigate`, `click`, `fill` steps.

**Specs**:
- Analyze `automaToSteps` function in `Workflow.tsx`.
- Add mappings for common Automa blocks.
- Ensure parameters (selectors, values) are extracted correctly.

## Pending Tasks
- [] по нажатию кнопки Открыть браузер загружать страницу app.heygen.com
- [] при остановке процесса выполнения, закрывать браузер, убивая процесс. На текущий момент почему даже если закрыть браузер, процесс остается висеть в фоне.
- [] сделать нажатие на поле с текстом сцены таким же, как нажатие на канву с поиском центральной точки и эмитация реального клика по этой точке.
- [] Добавить валидацию вставки бирола в сцену. Методология такая: после вставки, нужно нажать повторно на центр канвы и если появится кнопка <button class="prism:tw-rounded-[100px] tw-inline-flex tw-items-center tw-justify-center tw-whitespace-nowrap tw-rounded-md tw-text-[14px] tw-font-primary tw-font-semibold tw-leading-[20px] tw-tracking-normal focus-visible:tw-outline-none focus-visible:tw-ring-1 focus-visible:tw-ring-ring disabled:tw-pointer-events-none disabled:tw-opacity-50 [&amp;_svg]:tw-pointer-events-none [&amp;_svg]:tw-text-current hover:tw-cursor-pointer hover:tw-bg-ux-hover active:tw-bg-ux-active disabled:tw-opacity-disabled prism:tw-text-textTitle prism:hover:tw-bg-ux-hover prism:active:tw-bg-ux-active prism:disabled:tw-text-textDisable prism:disabled:tw-opacity-disabled tw-h-btn-md tw-px-btn-md tw-gap-[6px] tw-text-textTitle tw-p-0" type="button" aria-haspopup="dialog" aria-expanded="false" aria-controls="radix-:r8r:" data-state="closed"><div class="tw-size-4 tw-rounded-full tw-border tw-border-line" style="background-color: rgb(255, 255, 255);"></div><span class="tw-text-xs tw-font-medium tw-text-textTitle">BG Color</span></button> то повторить вставку бирола. Если после 3 попыток результата нет, перейти к следующей сцене и в отчете указать об ошибке и номере сцены. 
- [] создать базу доступных шаблонов со страницы https://app.heygen.com/templates Чтобы увидеть все шаблоны, нужно нажать на блок "See All". Вот html блока <div class="tw-relative tw-aspect-video tw-w-full tw-overflow-hidden tw-rounded tw-border tw-border-line tw-bg-fill-block tw-text-textTitle tw-flex tw-items-center tw-justify-center tw-gap-1 tw-font-semibold tw-text-sm tw-transition-all tw-duration-200 tw-ease-in-out tw-cursor-pointer hover:tw-text-textTitleRev hover:tw-bg-brand active:tw-text-textTitleRev active:tw-bg-ux-brandActive">See All <iconpark-icon class="iconpark-icon" name="down" theme="filled" size="18" icon-id=""></iconpark-icon></div> Появляется весь список шаблонов и нужно собрать ссылки на все шаблоны внутри #root > div > div > div:nth-child(3) > div > div.tw-flex.tw-min-h-0.tw-w-full.tw-min-w-0.tw-flex-1.tw-flex-col > div.tw-relative.tw-flex.tw-w-full.tw-min-w-0.tw-flex-1.tw-flex-col.tw-overflow-hidden > div.tw-pb-25.tw-relative.tw-h-full.tw-flex-1.tw-overflow-y-auto.tw-overflow-x-hidden.tw-bg-fill-general > div.tw-flex.tw-size-full.tw-flex-col.tw-px-3.sm\:tw-pl-12.sm\:tw-pr-9 > div > div:nth-child(1) или блока class="tw-flex tw-flex-col tw-gap-0 внутри которого есть текст "My Templates". Как собрать список? Находишь первый элемент в гриде и нажимаешь в центр этого блока эмитируя реальный клик. Далее появится всплывающее окно. Там есть примерно такая строка с названием шаблона <h2 id="radix-:r88:" class="tw-text-textTitle tw-text-lg tw-font-bold tw-leading-none tw-tracking-tight dialogTitle">Название шаблона</h2> Сохраняешь его название. Далее нужно полуить ссылку. По нажатию кнопки "Create with" откроется страница шаблона и в адресной строке будет ссылка типа https://app.heygen.com/create-v4/draft?vt=l&template_id=0344d8614d484b16a7ab0531560bae91&private=1&fromCreateButton=true это и будет ссылка для шаблона с названием, которое ты уже сохранил. Возвращаемся на предыдущую страницу и повторяем для следующего шаблона, пока они не закончаться. Для ориентира, на данный момент последний шаблон будет с названием "Крайний шаблон". Это будет последний. Весь список щаблонов добавь в интерфейс и возможность для каждого сценария выбирать один из шаблонов. Это будет вместо ссылки в таблице  template_url. 
- [x] Наладить работу добавления бирола (выбор видео, установка как фон, удаление переднего слоя).
- [x] Внедрить систему скачивания и монтажа готовых видео. реализовать сбор всех сгенерированных частей в раздел Результаты. Добавить возможность скачивания и склеики выбранных эпизодов. 
- [x] фильтр со статусами проектов на странице запуска перенсти из верхней части в блок Проекты к запуску. 
- [x] на странице Воркфлоу добавить запуск  playwrite инспектора
- [x] Добавить в раздел "настройки" для каждой проверки настройки (включение, отключение, количество попыток, интервал между попытками)
- [x] Если браузер закрыт пользователем, останавливать процесс выполнения. 
- [x] Если все задачи остановлены, закончили выполнение или завершились с ошибкой, общий процесс тоже должен остановиться. А то бывало, когда задача работала, я ее остановил или она завершилась, а большая кнопка запуска не работает, так как оно продолжает что-то делать, хотя все задачи завершились. 
- [x] Добавить на 5 секунд возможность отмены удаления проекта. Чтобы всплывала плашка проект удален с кнопкой Отменить удаление.     
- [x] перед тем как выбирать источник бирола (точнее вообще начинать процесс добавления бирола) обязательно нажимать на вкладку Видео.
- [x] окно редактирования таблицы сделать по высоте меньше на 15%, т.к. не видно кнопку под таблицей и нужно менять маштаб, чтобы ее найти. И сделай таблицу менее грамоздкой, чтобы она на экране была более компактной (строки сделать уже как минимум)
- [x] перевести весь интерфейс на русский
- [x] провести аудит всего кода и всех файлов. Оптимизировать структуру кода, избавиться от дублирования, вынести повторяющиеся функции в отдельные файлы, удалить неиспользуемые файлы и код, который больше не нужен. Найти и устранить критические ошибки и ошибки логики. Проверить все на работоспособность. 
- [x] реализовать генерацию изображений через Google ai studio api и модель nano banano pro по промтам из таблицы, если значение в ячейке broll_query	начинается с "NANO_BANANO:". После двоеточий идет промт, который нужно передать в модель. После завершения генерации изображения, нужно сохранить их в папку проекта, которая указана в настройках. И этот файл скопировать в буфер обмена. После чего (если уже активна нужная сцена) нажимаем на облость как мы это делаем при выборе добавленного бирола или удаления аватара, чтобы активировать область работы с картинкой сцены и вставляем изображение из буфера обмена, после чего делаем все ровно так же, как после добавление бирола из вкладки медиа, когда он попадает в область с изображением. API лежит в .env файле. 
- [x] Дерево настроек по умолчанию скрыто
- [x] В разделе Проекты к запуску цвет текста Спикер: сделать белым.
- [x] По-умолчанию все проекты в разделе Проекты к запуску стоят с пустыми чекбоксами.
