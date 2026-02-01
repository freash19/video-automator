Plan-First & Approval Gate: Изменение кода — только после обновления PLAN.md. После обновления остановись и жди явного «Go» от пользователя.

Research & No Guessing: Используй tools/inspector.py. Динамические CSS-классы запрещены. Если селектор нестабилен, используй координаты центра из annotated.png.

Double-Fail STOP: После 2 неудач на шаге — СТОП. Сделай скриншот ошибки и запроси помощь. Пользователь может дать: селектор, координаты или логи «Deep Event Tracker».

Red Dot: Каждый клик по координатам должен отрисовывать красную точку через page.evaluate.

Modular Integrity: Код строго по файлам в core/: browser.py (клики), scenes.py (текст), broll.py (медиа). Не забивай heygen_automation.py.

Step-Wrapper: Весь функционал через perform_step (или @step) с логами в automation.log.