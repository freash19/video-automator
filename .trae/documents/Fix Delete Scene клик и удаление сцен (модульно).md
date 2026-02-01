## Наблюдение по текущей проблеме
- Сейчас удаление пустых сцен кликает «…» как `more_button.last`, из‑за этого часто открывается меню не той сцены и пункт `Delete Scene` (желтым на скрине) не нажимается.
- Вы подтвердили, что **доп. диалога подтверждения нет**, значит нужно чинить именно привязку кликов к правильной строке сцены и валидацию факта удаления.

## UI‑исследование (обязательное по правилам)
- Запустить `tools/inspector.py` на тестовом шаблоне: `https://app.heygen.com/create-v4/draft?template_id=0344d8614d484b16a7ab0531560bae91&private=1`.
- В `debug/inspection/annotated.png` и `report.json` зафиксировать стабильные селекторы:
  - контейнера строки сцены (в которой есть `text_N`),
  - кнопки `…` внутри **этой** строки,
  - пункта меню `Delete Scene` (как menuitem/role=menuitem).

## Правки (модульно, без “всё в одном”) — core/scenes.py
- В [core/scenes.py](file:///Users/ilya/Projects/heygen_automation_V2/core/scenes.py) добавить устойчивую функцию удаления именно через меню:
  - найти строку сцены по `text_N`,
  - подняться к контейнеру строки,
  - кликнуть `…` **внутри контейнера** (не global `.last`),
  - кликнуть `Delete Scene` в появившемся меню,
  - провалидировать удаление: дождаться исчезновения `text_N`.
- Все клики делать через существующие хелперы из [core/browser.py](file:///Users/ilya/Projects/heygen_automation_V2/core/browser.py) с визуализацией красной точкой (human_coordinate_click/_show_click_marker), чтобы было видно куда попали.
- Обернуть новую логику в `@step(...)`, чтобы при сбое автоматически сохранялся скриншот (см. [ui/step_wrapper.py](file:///Users/ilya/Projects/heygen_automation_V2/ui/step_wrapper.py)).

## Интеграция — минимально в heygen_automation.py
- В [heygen_automation.py](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L1089-L1201) заменить тело `delete_empty_scenes` на делегирование в `core.scenes.delete_empty_scenes(...)`, чтобы логика жила в модуле и не дублировалась.

## Проверка результата
- На указанном шаблоне удаляются все сцены после `filled_count`.
- В `automation.log` видно: выбор `text_N` → клик `…` в правильной строке → клик `Delete Scene` → исчезновение `text_N`.
- Если после 2 попыток на одном шаге не получается — останавливаемся по правилу Anti‑Looping и сохраняем артефакты.

План готов. Одобряете логику для перехода к работе? (ответьте “Go”)