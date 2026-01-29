## Текущий статус (по коду)
- **Определение Nano Banana в сценарии**: реализовано в [clipboard.py](file:///Users/ilya/Projects/heygen_automation_V2/utils/clipboard.py#L22-L45). Поддерживает варианты `NANO_BANANO`, `NANO_BANANA`, `NANA_BANANA`, `NANA_BANANO` (разделитель `_` или пробел; после — `:` или пробел).
- **Вставка B-roll с проверкой/ретраями**: реализовано в [handle_broll_for_scene](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L2534-L2810). После вставки происходит клик по канве и проверка состояния (Set as BG / BG Color / Detach/Change BG) через [_detect_broll_state_after_canvas_click](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L2424-L2487), с ретраями до 3 попыток.
- **Вставка Nano Banana с такой же проверкой**: сейчас **не доведена до паритета**. Ветка Nano в [handle_broll_for_scene](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L2534-L2570) делает генерацию/вставку через `core.broll.handle_nano_banano`, но **не выполняет пост-валидацию** (empty_canvas/needs_set_bg) и не делает ретраи на уровне `HeyGenAutomation`.
- **Настраиваемая задержка (4 секунды) перед проверкой**: в текущем `heygen_automation.py` проверка использует фиксированные `await asyncio.sleep(2.0)` внутри `_detect_broll_state_after_canvas_click` (см. [heygen_automation.py](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L2424-L2429)). То есть параметр `broll_validation_wait_sec` из smoke-скриптов сейчас на поведение основной автоматики не влияет.

## Что нужно сделать, чтобы «всё работало как договаривались»
1. **Подключить `broll_validation_wait_sec`** в `_detect_broll_state_after_canvas_click` (и логировать фактическое ожидание).
2. **Добавить пост-валидацию и ретраи для Nano Banana** прямо в ветку `nano_prompt` внутри `handle_broll_for_scene`, по той же схеме, что и для обычного B-roll:
   - после вставки: wait → клик по канве → определить состояние;
   - если `needs_set_bg`: нажать “Set as BG”, подождать и перепроверить;
   - если `empty_canvas`: считать неуспехом и повторить попытку вставки (до 3 раз);
   - сохранять скриншоты и причины, как в B-roll ветке.
3. **Синхронизировать smoke-тесты** (B-roll и Nano) с реальным параметром ожидания и подготовить сценарий для ручного удаления/изменения.
4. **Проверка в UI**: прогнать запуск через UI (в т.ч. `/run-workflow`) и убедиться, что сообщения о валидации видны в консоли и что ретраи реально происходят.

## Верификация
- Авто: smoke-скрипты на 1 сцену для B-roll и Nano.
- Ручной тест: вставка → пауза 4с → вручную удалить/изменить фон → убедиться, что автоматика детектит и делает ожидаемое действие (Set as BG или повторная вставка).

Если подтвердите, внесу изменения и сразу прогоню проверки.