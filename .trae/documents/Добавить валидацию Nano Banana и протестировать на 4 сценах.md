## Цель
- Добавить **только** пост-валидацию для Nano Banana (ветка `NANO/NANA_*`) в двух режимах:
  - канва пустая (видна кнопка BG Color)
  - не установилось фоном (видна кнопка Set as BG)
- Протестировать это на **тестовых 4 сценах**.

## Что поменяю в коде
- В [heygen_automation.py](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py) внутри `handle_broll_for_scene()` в ветке `if nano_prompt:`:
  - Добавлю цикл до 3 попыток (как у B-roll).
  - После `handle_nano_banano(...)` выполню детект состояния через уже существующий `_detect_broll_state_after_canvas_click()`.
  - Если `needs_set_bg` → нажму `_click_set_as_bg_if_present()` и перепроверю.
  - Если `empty_canvas` → зафиксирую причину и сделаю повторную попытку вставки Nano.
  - На каждой неуспешной попытке буду делать debug-скриншот и лог `nano_banano_validate: ...` + `nano_banano_retry_validation: ...`.
  - При успехе (`ok` или `unknown`) — завершу как успешную вставку.

## Тест на 4 сценах
- Добавлю тестовый CSV на 4 сцены (Nano Banana в `broll_query`) и отдельный smoke-скрипт запуска.
- В конфиге smoke-скрипта выставлю ожидание перед проверкой `broll_validation_wait_sec = 4.0`, чтобы ты мог вручную:
  - Сцена A: удалить вставленный Nano → должны увидеть `empty_canvas` и сделать повторную вставку.
  - Сцена B: открепить от BG/сделать не-фоном → должны увидеть `needs_set_bg`, нажать Set as BG, перепроверить.
  - Сцены C/D: оставить как есть, чтобы убедиться, что «нормальный» кейс не ломается.

## Верификация результата
- В логе должны появляться маркеры:
  - `nano_banano_validate: empty_canvas` / `nano_banano_validate: needs_set_bg`
  - `nano_banano_retry_validation: X/3 reason=...`
  - `nano_banano_done: scene=...`
- В `debug/screenshots/` должны появиться скрины для validate_fail и done.

Подтверди этот план — и я внесу изменения и запущу прогон на 4 сценах.