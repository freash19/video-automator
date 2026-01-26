import asyncio
import pandas as pd
import random
from playwright.async_api import async_playwright, Page
import os

class HeyGenAutomation:
    def __init__(self, csv_path: str):
        """
        Инициализация автоматизации HeyGen
        
        Args:
            csv_path: Путь к CSV файлу со сценариями
        """
        self.csv_path = csv_path
        self.df = None
        
    def load_data(self):
        """Загрузить данные из CSV"""
        print(f"📁 Загружаю данные из {self.csv_path}...")
        self.df = pd.read_csv(self.csv_path, encoding='utf-8')
        print(f"✅ Загружено {len(self.df)} строк")
        print(f"Колонки: {list(self.df.columns)}")
        return self.df
    
    def get_all_episode_parts(self, episode_id: str):
        """
        Получить все части конкретного эпизода
        
        Args:
            episode_id: ID эпизода (например, 'ep_1')
            
        Returns:
            list: Список номеров частей
        """
        episode_data = self.df[self.df['episode_id'] == episode_id]
        
        if episode_data.empty:
            return []
        
        parts = sorted(episode_data['part_idx'].unique())
        return parts
    
    def get_episode_data(self, episode_id: str, part_idx: int):
        """
        Получить данные для конкретного эпизода и части
        
        Args:
            episode_id: ID эпизода (например, 'ep_1')
            part_idx: Номер части (например, 1)
            
        Returns:
            tuple: (template_url, list of scenes)
        """
        # Фильтруем данные по episode_id и part_idx
        episode_data = self.df[
            (self.df['episode_id'] == episode_id) & 
            (self.df['part_idx'] == part_idx)
        ].copy()
        
        if episode_data.empty:
            print(f"⚠️ Нет данных для {episode_id}, часть {part_idx}")
            return None, []
        
        # Получаем URL шаблона из ЛЮБОЙ строки этого эпизода (они одинаковые для всех частей)
        episode_rows = self.df[self.df['episode_id'] == episode_id]
        template_url = episode_rows.iloc[0]['template_url'] if 'template_url' in episode_rows.columns else None
        
        # Сортируем по scene_idx
        episode_data = episode_data.sort_values('scene_idx')
        
        # Формируем список сцен
        scenes = []
        for _, row in episode_data.iterrows():
            scenes.append({
                'scene_idx': int(row['scene_idx']),
                'speaker': row['speaker'],
                'text': row['text'],
                'title': row.get('title', f"{episode_id}_part_{part_idx}")
            })
        
        print(f"📋 Эпизод: {episode_id}, Часть: {part_idx}")
        print(f"🔗 URL шаблона: {template_url}")
        print(f"🎬 Сцен для заполнения: {len(scenes)}")
        
        return template_url, scenes
    
    async def fill_scene(self, page: Page, scene_number: int, text: str):
        """
        Заполнить конкретную сцену текстом
        
        Args:
            page: Playwright страница
            scene_number: Номер сцены (1, 2, 3, ...)
            text: Текст для вставки
        """
        text_label = f"text_{scene_number}"
        print(f"  ✏️  Заполняю сцену {scene_number}: {text_label}")
        
        try:
            # Ищем span с текстом text_X
            span_locator = page.locator(f'span[data-node-view-content-react]:has-text("{text_label}")')
            
            # Проверяем существование
            count = await span_locator.count()
            if count == 0:
                print(f"  ⚠️  Не найдено поле {text_label}")
                return False
            
            # Кликаем на span
            await span_locator.first.click()
            await asyncio.sleep(random.uniform(0.2, 0.4))
            
            # Очищаем содержимое
            await page.keyboard.press('Meta+A')
            await asyncio.sleep(0.1)
            await page.keyboard.press('Backspace')
            await asyncio.sleep(random.uniform(0.1, 0.2))
            
            # Вставляем текст через буфер обмена (быстрее)
            await page.keyboard.insert_text(text)
            
            print(f"  ✅ Сцена {scene_number} заполнена")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            return True
            
        except Exception as e:
            print(f"  ❌ Ошибка при заполнении сцены {scene_number}: {e}")
            return False
    
    async def delete_empty_scenes(self, page: Page, filled_scenes_count: int, max_scenes: int = 15):
        """
        Удалить все пустые сцены после заполненных
        
        Args:
            page: Playwright страница
            filled_scenes_count: Количество заполненных сцен
            max_scenes: Максимальное количество сцен в шаблоне
        """
        empty_scenes = list(range(filled_scenes_count + 1, max_scenes + 1))
        
        if not empty_scenes:
            print("✅ Все сцены заполнены, удаление не требуется")
            return
        
        print(f"\n🗑️  Удаляю пустые сцены: {empty_scenes}")
        
        for scene_num in empty_scenes:
            try:
                text_label = f"text_{scene_num}"
                print(f"  🗑️  Удаляю сцену {scene_num}: {text_label}")
                
                # Находим span с текстом text_X
                span_locator = page.locator(f'span[data-node-view-content-react]:has-text("{text_label}")')
                
                # Проверяем существование
                count = await span_locator.count()
                if count == 0:
                    print(f"  ⚠️  Сцена {text_label} не найдена, пропускаю")
                    continue
                
                # Кликаем на span, чтобы выделить сцену
                await span_locator.first.click()
                await asyncio.sleep(random.uniform(0.3, 0.5))
                
                # Ищем кнопку с тремя точками (more-level)
                more_button = page.locator('button:has(iconpark-icon[name="more-level"])')
                
                # Проверяем существование кнопки
                button_count = await more_button.count()
                if button_count == 0:
                    print(f"  ⚠️  Кнопка меню не найдена для {text_label}")
                    continue
                
                # Кликаем на кнопку с тремя точками (берем последнюю видимую)
                await more_button.last.click()
                await asyncio.sleep(random.uniform(0.3, 0.5))
                
                # Ждем появления меню и ищем пункт "Удалить сцену"
                delete_item = page.locator('div[role="menuitem"]:has(iconpark-icon[name="delete"]):has-text("Удалить сцену")')
                
                # Проверяем существование пункта меню
                delete_count = await delete_item.count()
                if delete_count == 0:
                    print(f"  ⚠️  Пункт 'Удалить сцену' не найден")
                    continue
                
                # Кликаем на "Удалить сцену"
                await delete_item.first.click()
                await asyncio.sleep(random.uniform(0.5, 0.8))
                
                print(f"  ✅ Сцена {scene_num} удалена")
                
            except Exception as e:
                print(f"  ❌ Ошибка при удалении сцены {scene_num}: {e}")
                continue
        
        print("✅ Удаление пустых сцен завершено")
    
    async def click_generate_button(self, page: Page):
        """
        Нажать кнопку "Сгенерировать"
        
        Args:
            page: Playwright страница
        """
        print("\n🔘 Нажимаю кнопку 'Сгенерировать'...")
        
        try:
            # Ищем кнопку по тексту
            button = page.locator('button:has-text("Сгенерировать")')
            
            # Проверяем существование
            count = await button.count()
            if count == 0:
                print("❌ Кнопка 'Сгенерировать' не найдена")
                return False
            
            # Скроллим к кнопке
            await button.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.3, 0.5))
            
            # Кликаем
            await button.click()
            print("✅ Кнопка 'Сгенерировать' нажата")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при нажатии кнопки: {e}")
            return False
    
    async def fill_and_submit_final_window(self, page: Page, title: str):
        """
        Заполнить название видео и нажать "Отправить" в финальном окне
        
        Args:
            page: Playwright страница
            title: Название видео
        """
        print(f"\n📝 Заполняю финальное окно с названием: {title}")
        
        try:
            # Ждем появления попап окна с заголовком "Сгенерировать видео"
            print("  ⏳ Жду появления окна генерации...")
            await page.wait_for_selector('div:has-text("Сгенерировать видео")', timeout=10000)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Находим поле ввода по placeholder
            input_field = page.locator('input[placeholder="Без названия — видео"]')
            
            # Проверяем существование
            count = await input_field.count()
            if count == 0:
                print("  ❌ Поле ввода названия не найдено")
                return False
            
            # В попапе может быть несколько таких полей, берем последний (в попапе)
            print(f"  ✏️  Ввожу название: {title}")
            
            # Кликаем на поле
            await input_field.last.click()
            await asyncio.sleep(random.uniform(0.2, 0.3))
            
            # Очищаем поле
            await page.keyboard.press('Meta+A')
            await asyncio.sleep(0.1)
            await page.keyboard.press('Backspace')
            await asyncio.sleep(random.uniform(0.1, 0.2))
            
            # Вводим название
            await page.keyboard.insert_text(title)
            await asyncio.sleep(random.uniform(0.3, 0.5))
            
            print("  ✅ Название введено")
            
            # Находим кнопку "Отправить" в попапе
            submit_button = page.locator('button:has-text("Отправить")')
            
            # Проверяем существование
            button_count = await submit_button.count()
            if button_count == 0:
                print("  ❌ Кнопка 'Отправить' не найдена")
                return False
            
            print("  🚀 Нажимаю кнопку 'Отправить'...")
            
            # Кликаем на кнопку
            await submit_button.last.click()
            
            print("  ✅ Видео отправлено на генерацию!")
            print("  ⏳ Жду редиректа на страницу проектов...")
            
            # Ждем редиректа на страницу projects (до 60 секунд)
            try:
                await page.wait_for_url("**/projects**", timeout=60000)
                print("  ✅ Редирект выполнен, видео в процессе генерации!")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"  ⚠️ Таймаут ожидания редиректа, но продолжаю: {e}")
                await asyncio.sleep(3)
            
            return True
            
        except Exception as e:
            print(f"  ❌ Ошибка при заполнении финального окна: {e}")
            return False
    
    async def process_episode_part(self, episode_id: str, part_idx: int):
        """
        Обработать одну часть эпизода
        
        Args:
            episode_id: ID эпизода
            part_idx: Номер части
        """
        # Получаем данные
        template_url, scenes = self.get_episode_data(episode_id, part_idx)
        
        if not template_url or not scenes:
            print(f"❌ Нет данных для обработки")
            return False
        
        async with async_playwright() as p:
            print("\n🌐 Подключаюсь к твоему Chrome через CDP...")
            
            try:
                # Подключаемся к уже запущенному Chrome
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                print("✅ Подключился к Chrome!")
                
                # Получаем первый контекст (окно браузера)
                contexts = browser.contexts
                if not contexts:
                    print("❌ Нет открытых окон в Chrome")
                    return False
                
                context = contexts[0]
                
                # Создаем новую вкладку
                page = await context.new_page()
                
            except Exception as e:
                print(f"❌ Не могу подключиться к Chrome: {e}")
                print("\n💡 Убедись, что Chrome запущен с командой:")
                print('   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 --user-data-dir=~/chrome_automation')
                return False
            
            # Переходим на страницу шаблона
            print(f"📄 Открываю шаблон: {template_url}")
            await page.goto(template_url, wait_until='domcontentloaded', timeout=120000)
            
            # Ждем загрузки страницы и появления первого поля text_1
            print("⏳ Жду загрузки страницы и элементов...")
            try:
                # Ждем появления первого текстового поля (до 30 секунд)
                await page.wait_for_selector('span[data-node-view-content-react]', timeout=30000)
                print("✅ Элементы загрузились!")
            except Exception as e:
                print(f"⚠️ Timeout при ожидании элементов, но продолжаю: {e}")
            
            # Дополнительная пауза для стабильности
            await asyncio.sleep(3)
            
            # Заполняем сцены
            print(f"\n📝 Начинаю заполнение {len(scenes)} сцен...")
            success_count = 0
            
            for scene in scenes:
                success = await self.fill_scene(
                    page, 
                    scene['scene_idx'], 
                    scene['text']
                )
                if success:
                    success_count += 1
            
            print(f"\n📊 Заполнено сцен: {success_count}/{len(scenes)}")
            
            # Удаляем пустые сцены
            await self.delete_empty_scenes(page, len(scenes))
            
            # Нажимаем кнопку "Сгенерировать"
            await self.click_generate_button(page)
            
            # Заполняем финальное окно и отправляем
            title = scenes[0]['title']
            await self.fill_and_submit_final_window(page, title)
            
            # Вкладка автоматически закроется после обработки
            print(f"\n✅ Часть {part_idx} обработана и отправлена на генерацию!")
            
            # Закрываем вкладку
            await page.close()
            print(f"🔒 Вкладка закрыта\n")
            
            return True
    
    async def process_full_episode(self, episode_id: str):
        """
        Обработать все части эпизода автоматически
        
        Args:
            episode_id: ID эпизода (например, 'ep_1')
        """
        # Получаем все части эпизода
        parts = self.get_all_episode_parts(episode_id)
        
        if not parts:
            print(f"❌ Нет частей для эпизода {episode_id}")
            return False
        
        print(f"\n{'='*60}")
        print(f"📺 Обработка эпизода: {episode_id}")
        print(f"📋 Найдено частей: {len(parts)} - {parts}")
        print(f"{'='*60}\n")
        
        # Обрабатываем каждую часть
        for i, part_idx in enumerate(parts, 1):
            print(f"\n{'='*60}")
            print(f"🎬 Обрабатываю {episode_id}, часть {part_idx} ({i}/{len(parts)})")
            print(f"{'='*60}\n")
            
            success = await self.process_episode_part(episode_id, part_idx)
            
            if not success:
                print(f"❌ Ошибка при обработке части {part_idx}, останавливаюсь")
                return False
            
            print(f"✅ Часть {part_idx} успешно обработана и отправлена на генерацию!")
            
            # Пауза между частями (кроме последней)
            if i < len(parts):
                wait_time = 5
                print(f"\n⏳ Пауза {wait_time} секунд перед следующей частью...")
                await asyncio.sleep(wait_time)
        
        print(f"\n{'='*60}")
        print(f"🎉 ВСЕ ЧАСТИ ЭПИЗОДА {episode_id} ОБРАБОТАНЫ!")
        print(f"{'='*60}\n")
        
        return True


async def main():
    """
    Основная функция для тестирования
    """
    print("=" * 60)
    print("🎬 HeyGen Automation Script (CDP Mode)")
    print("=" * 60)
    
    # Путь к CSV файлу (должен быть в той же папке)
    csv_path = "scenarios.csv"
    
    # Проверяем существование файла
    if not os.path.exists(csv_path):
        print(f"❌ Файл {csv_path} не найден!")
        print(f"   Положи файл scenarios.csv в папку: {os.getcwd()}")
        return
    
    # Создаем объект автоматизации
    automation = HeyGenAutomation(csv_path)
    
    # Загружаем данные
    automation.load_data()
    
    # Обрабатываем весь эпизод со всеми частями
    print("\n" + "=" * 60)
    print("🚀 РЕЖИМ: Обработка всех частей эпизода ep_1")
    print("=" * 60 + "\n")
    
    await automation.process_full_episode('ep_1')


if __name__ == "__main__":
    asyncio.run(main())