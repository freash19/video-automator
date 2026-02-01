## Контекст теста (фиксируем в плане)
- Шаблон: https://app.heygen.com/create-v4/draft?template_id=a108ce76c12244e8bfc63ba1fe7152d8&private=1
- CSV: `WAT - 44.csv` в корне проекта.
- Критерий успеха: **все 70 сцен заполнены и остаются заполненными после 2 обновлений страницы**.

## Гипотезы причины (исходим из того, что Save работает)
1) **Ввод идёт не в “источник правды” редактора**: `span[data-node-view-content-react]` может быть view/плейсхолдером, а реальные данные живут в другом `contenteditable` (ProseMirror/TipTap-подобный редактор). Тогда визуально текст есть, но после reload исчезает.
2) **Нет корректного commit/blur** после ввода: HeyGen может требовать blur/click-out/enter для фиксации в модели, а текущий `Tab` может переводить фокус так, что commit не происходит.
3) **Пост-проверка делается по неправильному сигналу**: сейчас в `heygen_automation.py` нет реальной `verify_scene_after_insert` (ветка пустая), поэтому “текст не приклеился” обнаруживается слишком поздно и без точной диагностики.

## Задача для `docs/PLAN.md` (что именно добавить)
Добавить в `docs/PLAN.md` новую активную задачу (выше/рядом с текущей Active Task), в формате текущего файла:

### Active Task: Fix — Scene text persists after 2 reload (WAT-44)
**Goal**: Автозаполнение 70 сцен из `WAT - 44.csv` в указанном draft-шаблоне; после **двух** `page.reload()` тексты всех 70 сцен присутствуют.

**Specs (по .traerules)**
- `ui-researcher`:
  - Запустить `tools/inspector.py` на странице draft.
  - Найти **реальный editable** текста сцены (приоритет: `data-testid` > `aria-label` > `role` > `text`).
  - Зафиксировать: селектор editable + селектор/метод commit (что нажать/куда кликнуть) + `debug/inspection/annotated.png`.
- `automation-engineer`:
  - Обновить ввод текста сцены: фокус по сцене → фокус по найденному editable → replace text → commit (клик по безопасной области). Любые клики по координатам — с красной точкой.
  - Реализовать `verify_scene_after_insert` (read-back из editable + 1–2 retry), логируя через `perform_step/@step`.
  - Обновить `refresh_and_validate`: сделать **двойной reload** по сценарию теста и финальную проверку 70/70.
- `qa-tester`:
  - Прогнать dry-run на WAT-44: собрать выжимку из `automation.log` и подтвердить наличие/отсутствие `debug/screenshots/` при ошибках.

**Acceptance Criteria**
- AC1: На шаблоне из ссылки выше после заполнения и **2 reload** все 70 сцен заполнены (нет `text_N` и нет пустых).
- AC2: В `automation.log` есть шаги вида `fill_scene`, `verify_after_insert`, `refresh_and_validate_reload_1`, `refresh_and_validate_reload_2` в формате `[TIMESTAMP] [LEVEL] [StepName] ...`.
- AC3: При несовпадении текста сцены создаётся скриншот в `debug/screenshots/` и фиксируется причина (mismatch/не найден editable/commit failed).
- AC4: Селекторы подтверждены инспектором; динамические классы не используются.

## План выполнения (после вашего "Go")
### 1) Исследование DOM редактора (обязательно)
- Через `tools/inspector.py` определить точный editable узел для текста сцены и стабильные атрибуты.

### 2) Перевод ввода на editable + commit
- Реализовать ввод не по `span[data-node-view-content-react]`, а по найденному editable.
- Добавить явный commit/blur.

### 3) Верификация после вставки
- Включить `verify_scene_after_insert` по умолчанию для теста WAT-44.
- При mismatch: retry 1 — повтор replace; retry 2 — “human-like” (typing delay/paste) + commit.

### 4) Двойной reload и финальная проверка 70/70
- В `refresh_and_validate` выполнить reload дважды и после каждого прохода проверить отсутствие `text_N` и присутствие всех 70 текстов.

### 5) QA-артефакты
- Приложить итог: `automation.log`-фрагменты + список созданных скриншотов (если были).

План готов. Одобряете логику для перехода к работе? (ответьте "Go")