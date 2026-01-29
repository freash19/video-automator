## Требования (из PLAN.md + уточнения)
- Telegram:
  - ✅ если всё прошло без ошибок.
  - ⚠️ если есть ошибки.
  - ❌ если выполнено < 80% сцен, а также при раннем фейле (шаблон не открылся/страница не загрузилась/процесс фактически не начался).
  - В сообщении всегда указывать список сцен с ошибками и тип ошибки по каждой сцене.
  - Формат заголовка:
    - `Название эпизода: (жирным)`
    - `Часть: N`
- UI (Runner → список задач): показывать ошибки по сценам с расшифровкой.
- UI (Редактировать проект): убрать блок «Задачи проекта».
- После внедрения: отправить тестовое уведомление в Telegram-бот.

## Причина бага «Сцены: 87/70»
- `scene_done` увеличивается на каждый `finish_scene ok=True`.
- `refresh_and_validate()` при автоисправлениях повторно вызывает `fill_scene()`, что снова эмитит `finish_scene ok=True` → переполнение.

## План изменений
### 1) Backend: корректный подсчет сцен (без переполнения)
- В `ui/api.py` добавить per-task набор засчитанных сцен (set по `scene`/`scene_idx`).
- На `start_part` сбрасывать набор.
- На `finish_scene ok=True` увеличивать `scene_done` только если эта сцена ещё не засчитана.

### 2) Backend: нормализация `report_details` и добавление Nano Banana ошибок
- Расширить `_compact_report_entries()` (ui/api.py), чтобы переносить дополнительные поля (`kind`, `prompt`, `attempt`, `screenshot`, и т.п.), а не терять их.
- В `_run_one()` включить в `tinfo["report_details"]` категорию `nano_banano_errors` (сейчас она накапливается в `auto.report`, но не уходит в API/Telegram/UI).
- Обновить `_format_task_report_line()` и вспомогательные функции так, чтобы учитывались новые категории.

### 3) Backend: единый агрегатор ошибок по сценам + расчет “заполнено успешно”
- В `ui/api.py` добавить helper (например `_compute_scene_health(t)`), который строит:
  - `errors_by_scene: {scene_idx: [ {label, kind, detail} ]}` на базе `report_details`.
  - `scene_total`.
  - `scene_ok` = `scene_total - len(unique scenes with errors)`.
  - `ok_ratio`.
- Маппинг типов ошибок (минимально необходимый):
  - `validation_missing` → «не заполнен текст сцены»
  - `broll_no_results` → «не вставлен бирол (нет результатов)»
  - `broll_errors`:
    - `kind=validation_failed` и `reason` содержит `set_as_bg` → «бирол не установлен на фон»
    - `reason=bg_color_visible_after_insert`/`empty_canvas` → «не вставлен бирол»
    - `kind=nano_validation_failed` → «Nano Banana: не установлено на фон/валидация не прошла»
    - иначе → «ошибка b-roll» + короткая деталь
  - `nano_banano_errors` → «нано банано не сгенерировало изображение»
- `broll_skipped` не считать ошибкой (это “не требуется”); оставить в summary как info при необходимости.

### 4) Telegram: новый формат + emoji-логика + безопасное форматирование
- В `ui/notify.py` добавить `parse_mode="HTML"` и `disable_web_page_preview=True`.
- В `ui/api.py::_send_task_telegram()`:
  - Заголовок:
    - `Название эпизода: <b>...</b>`
    - `Часть: ...`
  - `Статус: {emoji} {status}`
  - `Сцены: {scene_ok}/{scene_total}` (использовать вычисления из п.3, а не сырое `scene_done`).
  - `Ошибки:` → список строк вида `• Сцена 12: ...; ...`.
  - HTML-экранирование всех динамических полей.
- Emoji-правила (приоритет сверху вниз):
  1) ❌ если ранний фейл: `status in (failed, stopped)` и `scene_total==0` или `scene_ok==0` (не началось/не открылся шаблон/не загрузилась страница).
  2) ❌ если `scene_total>0` и `scene_ok/scene_total < 0.8`.
  3) ⚠️ если есть ошибки по сценам или `status != success`.
  4) ✅ если ошибок нет и `status == success`.

### 5) Frontend: улучшить отчет об ошибках в списке задач (Runner)
- В `genmaster-hub-main/src/components/runner/RunnerControls.tsx`:
  - Обновить `renderReportDetails()` так, чтобы выводить “Сцена N: причины” (не только номера).
  - В `summarizeReport()` учитывать `nano_banano_errors`.

### 6) Frontend: убрать блок «Задачи проекта» из окна «Редактировать проект»
- В `genmaster-hub-main/src/components/projects/ProjectEditorDialog.tsx` удалить секцию, начинающуюся с заголовка `Задачи проекта` (и связанный polling `/tasks?episode=...`, если больше не нужен).

## Верификация и финальный шаг
- Проверить на мок-данных (без HeyGen):
  - `scene_ok` не превышает `scene_total`.
  - Формат Telegram-сообщения соответствует требованиям.
  - UI Runner показывает расшифровку ошибок.
  - В ProjectEditorDialog больше нет блока «Задачи проекта».
- После завершения правок: отправить тестовое сообщение в Telegram-бот через текущие настройки токена/чат_id (используя `send_telegram()`), чтобы подтвердить parse_mode/emoji/формат.

## Файлы
- `ui/api.py`
- `ui/notify.py`
- `genmaster-hub-main/src/components/runner/RunnerControls.tsx`
- `genmaster-hub-main/src/components/projects/ProjectEditorDialog.tsx`