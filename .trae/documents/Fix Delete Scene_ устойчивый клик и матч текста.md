## Ответ на вопрос “ты уверен?”
- В коде действительно используется `more_button.last` при клике по «…»: [scenes.py](file:///Users/ilya/Projects/heygen_automation_V2/core/scenes.py#L523-L530) и [heygen_automation.py](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L1160-L1167). Это **не гарантирует** промах всегда: если на экране видима одна кнопка «…», `.last` попадает в неё, меню будет открываться (как вы и наблюдаете).
- Но даже при корректном открытии меню сейчас есть более вероятная причина, почему не нажимается `Delete Scene`: матч текста в коде **строго** `Delete scene` (маленькая `s`), а в UI на скрине — `Delete Scene` (большая `S`). Regex без `re.I`, поэтому пункт может не находиться вовсе: [scenes.py](file:///Users/ilya/Projects/heygen_automation_V2/core/scenes.py#L532-L535), [heygen_automation.py](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L1169-L1171).

## Исследование UI (обязательное)
- Запустить `tools/inspector.py` на шаблоне `https://app.heygen.com/create-v4/draft?template_id=0344d8614d484b16a7ab0531560bae91&private=1`.
- Подтвердить в DOM:
  - как именно называется menuitem (accessible name) — `Delete Scene`/варианты,
  - где рендерится меню (портал в body) и что у него за роли.

## Исправление (модульно)
- Править модуль [core/scenes.py](file:///Users/ilya/Projects/heygen_automation_V2/core/scenes.py) как основной источник логики:
  - заменить матч меню на регэксп, который покрывает `Delete Scene` (и RU), и сделать его case-insensitive: например `re.compile(r"delete\s*scene|удалить\s*сцену", re.I)`;
  - клик по пункту меню делать после ожидания видимости `role=menuitem`.
  - (опционально) усилить привязку клика по «…»: искать кнопку «…» в контексте выбранной сцены (контейнер строки), а не `.last`.
- В [heygen_automation.py](file:///Users/ilya/Projects/heygen_automation_V2/heygen_automation.py#L1089-L1201) минимально: либо делегировать на `core.scenes.delete_empty_scenes`, либо синхронно применить тот же case-insensitive матч (чтобы не было рассинхрона).
- Все клики проводить через существующие хелперы кликов с красной точкой (у вас уже есть `_show_click_marker` в [browser.py](file:///Users/ilya/Projects/heygen_automation_V2/core/browser.py#L189-L219)).

## Валидация
- После клика `Delete Scene` ждать исчезновения `text_N` в списке сцен (таймаут), иначе считать шаг неуспешным и сохранять скриншот через step-wrapper.

План готов. Одобряете логику для перехода к работе? (ответьте “Go”)