## Цель
- Сделать Nano Banana (NANO_BANANO:) воркфлоу строго по заданной последовательности без дополнительных кликов/повторов.

## Текущее состояние (что мешает)
- Сейчас Nano Banana вставка использует `try_delete_foreground()` и `click_make_background()` с фолбэками (правый клик, повторные попытки, дополнительные клики) — это нарушает требование “строго по шагам”.

## Изменения в коде
### 1) core/broll.py
- Переписать `handle_nano_banano()` (или выделить новый `handle_nano_banano_strict()` и перевести вызов на него), чтобы он выполнял только:
  1. Генерация изображения: `generate_image(prompt, output_dir, ...)`.
  2. Сохранение файла (уже делает `generate_image`) + копирование в буфер: `copy_image_to_clipboard(path, mime)`.
  3. Один клик по канве: `click_canvas_center(page)`.
  4. Удаление верхнего слоя: только `keyboard.press("Delete")` и `keyboard.press("Backspace")` (без поиска кнопок Remove, без правого клика).
  5. Один клик по канве: `click_canvas_center(page)`.
  6. Вставка изображения: `keyboard.press("Meta+V")`.
  7. Ожидание кнопки “Set as BG/Сделать фоном” (без кликов):
     - `btn = page.get_by_role('button', name=/Set as BG|Set as Background|Make background|Сделать фоном|Сделать фон/i)` или `page.locator('button').filter(has_text=...)`.
     - `await btn.first.wait_for(state='visible', timeout=6000)`.
     - Если таймаут/ошибка локатора — `await asyncio.sleep(5)`.
  8. Один клик по кнопке “Set as BG/Сделать фоном”: `await btn.first.click(force=True)` (без фолбэков/циклов).
- Удалить/не использовать любые дополнительные действия внутри Nano Banana пути: циклы, `random_delay`, повторные клики, контекстные меню.

### 2) heygen_automation.py
- В `handle_broll_for_scene()` оставить ветку распознавания префикса `NANO_BANANO:` и вызывать обновлённый strict-метод из `core/broll.py`.
- Важно: остальные кнопки/панели/обычный b-roll путь не менять.

### 3) (Опционально) Логи/артефакты
- Оставить только “неинтерактивные” артефакты: один скрин `nano_banano_done_{scene}` по завершению и `nano_banano_fail_{scene}` при ошибке.

## Верификация
- Прогон `python run_nano_banano_e2e.py` (уже есть runner + test CSV).
- Проверка:
  - В логах отсутствуют сообщения про right-click/context menu и отсутствуют дополнительные клики/повторы внутри nano шага.
  - Файл изображения появляется в `storage/nano_banano/`.
  - Скрин “done” появляется в `debug/screenshots/`.

## Результат
- Nano Banana выполняется строго по указанным шагам, без лишних кликов/фолбэков, и после этого пайплайн продолжает следующую сцену.