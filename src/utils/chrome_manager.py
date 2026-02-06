import asyncio
import subprocess
import psutil
import socket
import random
import json
import math
import platform
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger
import os 
import ctypes

class ChromeManager:
    """Управление Chrome через Playwright с возможностью имитации человеческого поведения"""

    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path("config") / "chrome_config.json"
        else:
            config_path = Path(config_path)
        self.config_path = config_path
        self.config = self._load_config()
        self.unique_key = self.config.get('unique_key', '--my-unique-chrome-key')
        self.process = None
        self.port = None
        self.pw = None
        self.browser = None
        self.page = None
        self.is_windows = platform.system() == "Windows"

    def _load_config(self):
        """Загружаем конфиг или создаём дефолтный"""
        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if not config_path.exists():
            self._create_default_config()

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _create_default_config(self):
        """Создаём дефолтный конфиг"""
        config_path = Path(self.config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        if system == "Windows":
            chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
        elif system == "Darwin":
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            chrome_path = "/usr/bin/google-chrome"

        user_data_dir = str(Path(".") / "profile")

        default_config = {
            "chrome_path": chrome_path,
            "user_data_dir": user_data_dir,
            "unique_key": "--my-unique-chrome-key-PFXQDuEar6vvacpf40A9",
            "port_range": {
                "min": 49152,
                "max": 65535
            },
            "args": [
                "--start-maximized",
                "--no-first-run"
            ],
            "my_args": {
                "headless": "windowed"
            }
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

        logger.debug(f"📝 Создан конфиг: {config_path}")
        return default_config

    def _find_free_port(self):
        """Находим свободный порт в заданном диапазоне"""
        port_min = self.config['port_range']['min']
        port_max = self.config['port_range']['max']

        for _ in range(100):
            port = random.randint(port_min, port_max)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) != 0:
                    return port

        raise RuntimeError("Не найден свободный порт")

    def _kill_by_unique_key(self):
        """Убиваем процесс по уникальному ключу"""
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any(self.unique_key in str(arg) for arg in cmdline):
                        pid = proc.info['pid']
                        logger.debug(f"🔪 Убиваем старый Chrome (PID: {pid})")
                        
                        # ✅ Кроссплатформенная проверка
                        if self.is_windows:
                            try:
                                subprocess.run(['taskkill', '/PID', str(pid), '/F', '/T'], 
                                            stdout=subprocess.DEVNULL, 
                                            stderr=subprocess.DEVNULL,
                                            timeout=5)
                                killed_count += 1
                            except Exception as e:
                                logger.warning(f"Ошибка taskkill: {e}")
                        else:
                            # Для Linux/macOS
                            try:
                                proc.kill()
                                proc.wait(timeout=2)
                                killed_count += 1
                            except Exception as e:
                                logger.warning(f"Ошибка kill: {e}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass

        if killed_count > 0:
            logger.debug(f"🛑 Убито процессов: {killed_count}")
            import time
            time.sleep(1)

            # Чистка префов
            pref_path = os.path.join(self.config['user_data_dir'], "Default", "Preferences")
            if not os.path.exists(pref_path):
                logger.warning(f"🚫 Не удалось найти префы: {pref_path}")
                return

            try:
                with open(pref_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                logger.debug(f"Поправили префы: {pref_path}")

                if "profile" in data:
                    data["profile"]["exit_type"] = "Normal"

                if "sessions" in data:
                    data["sessions"]["event_log"] = []

                with open(pref_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка парсинга JSON: {e}")
            except Exception as e:
                logger.error(f"Ошибка при работе с префами: {e}")

        return killed_count > 0


    def _build_args(self):
        """Собираем аргументы запуска"""
        args = []

        # Уникальный ключ из конфига
        args.append(self.unique_key)

        # Порт
        self.port = self._find_free_port()
        args.append(f"--remote-debugging-port={self.port}")

        # User data dir - создаём если не существует
        user_data_dir = Path(self.config['user_data_dir']).absolute()
        user_data_dir.mkdir(parents=True, exist_ok=True)
        args.append(f"--user-data-dir={user_data_dir}")

        try:
            # Дополнительные аргументы из конфига
            args.extend(self.config.get('args'))
            # Дополнительные аргументы из конфига
            my_args = self.config.get('my_args')
        except Exception as e:
            logger.error(f"Не удалось собрать аргументы запуска: {e}")
            raise RuntimeError(f"Запуск невозможен без корректных аргументов: {e}")

        try:
            headless = my_args["headless"]
            if headless == "windowed":
                args.append("--window-position=-44444,-44444")
            elif headless == True:
                args.append("--headless=True")
            elif headless == False:
                args.append("--window-position=0,100")
        except Exception as e:
            logger.error(f"Не удалось собрать аргументы запуска: {e}")
            raise RuntimeError(f"Запуск невозможен без точного указания headless: {e}")

        return args


    async def start(self):
        """Запускаем Chrome и подключаем Playwright"""

        # Убиваем старые процессы с этим ключом, если они почемуто остались
        self._kill_by_unique_key()

        await asyncio.sleep(0.5)

        # Собираем команду
        chrome_path = self.config['chrome_path']
        args = self._build_args()

        cmd = [chrome_path] + args

        # Запускаем процесс
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        await asyncio.sleep(2)

        # Подключаем Playwright с повторными попытками
        self.pw = await async_playwright().start()

        max_retries = 5
        for attempt in range(max_retries):
            try:
                self.browser = await self.pw.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{self.port}"
                )

                # Получаем контекст и страницу
                if self.browser.contexts:
                    context = self.browser.contexts[0]
                else:
                    context = await self.browser.new_context()

                if context.pages:
                    self.page = context.pages[0]
                else:
                    self.page = await context.new_page()

                await asyncio.sleep(0.5)

                logger.success(f"✅ Chrome запущен (порт: {self.port})")
                return self.page

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"⚠️ Попытка подключения {attempt + 1}/{max_retries} не удалась: {e}")
                    await asyncio.sleep(2)  # Ждём перед следующей попыткой
                else:
                    logger.error(f"❌ Ошибка после {max_retries} попыток: {e}")
                    self.cleanup()
                    raise

    async def cleanup(self):
        if self.browser:
            try:
                await self.browser.close()
                logger.debug("Browser closed")
            except Exception as e:
                logger.debug(f"Error closing browser: {e}")
        
        if self.pw:
            try:
                await self.pw.stop()
                logger.debug("Playwright stopped")
            except Exception as e:
                logger.debug(f"Error stopping Playwright: {e}")
        
        self._kill_by_unique_key()


    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.cleanup()


    async def show(self):
        """Выводит окно браузера на передний план"""
        client = await self.page.context.new_cdp_session(self.page)
        window_info = await client.send("Browser.getWindowForTarget")
        window_id = window_info['windowId']

        await client.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {
                "left": 0,
                "top": 40,
                "windowState": "normal" 
            }
        })

        await self.page.bring_to_front()

        # Костыль для Windows: кратковременный Fullscreen 
        await client.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {"windowState": "maximized"}
        })
        
        title = await self.page.title()
        logger.debug(f"Окно {title} выведено на экран.")

    async def hide(self):
        """Скрывает окно браузера"""
        client = await self.page.context.new_cdp_session(self.page)

        window_info = await client.send("Browser.getWindowForTarget")
        window_id = window_info['windowId']

        await client.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {
                "windowState": "normal" 
            }
        })

        await asyncio.sleep(0.2)

        await client.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {
                "left": -44444,
                "top": -44444,
            }
        })

        title = await self.page.title()
        logger.debug(f"Окно {title} скрыто.")

    @staticmethod
    async def system_message(title="Title", message="Message", flags=0x40, 
                        use_topmost=False, use_systemmodal=False, use_foreground=False):
        """
        Выводит системное сообщение c текстом.
        
        Windows flags:
        0x10 - MB_ICONERROR (красный крестик)
        0x30 - MB_ICONWARNING (Желтый треугольник с восклицательным знаком)
        0x40 - MB_ICONINFORMATION (Синий кружок с буквой "i")
        0x40000   - MB_TOPMOST (поверх окон)
        0x01000   - MB_SYSTEMMODAL (блокирует взаимодействие, пока не закроешь)
        0x10000   - MB_SETFOREGROUND (захват фокуса)
        """
        
        system = platform.system()
        loop = asyncio.get_event_loop()
        
        if system == "Windows":
            final_flags = flags
            if use_topmost:
                final_flags |= 0x40000
            if use_systemmodal:
                final_flags |= 0x01000
            if use_foreground:
                final_flags |= 0x10000
            
            await loop.run_in_executor(
                None, 
                ctypes.windll.user32.MessageBoxW, 
                0, message, title, final_flags
            )
        
        elif system == "Linux":
            # Определяем тип иконки для Linux
            icon_map = {
                0x10: "error",      # MB_ICONERROR
                0x30: "warning",    # MB_ICONWARNING
                0x40: "info"        # MB_ICONINFORMATION
            }
            icon = icon_map.get(flags, "info")
            
            # Определяем urgency (срочность) для Linux
            urgency = "critical" if use_systemmodal else "normal"
            
            def show_linux_notification():
                try:
                    # Попытка использовать notify-send
                    cmd = ['notify-send', title, message, f'--icon={icon}', f'--urgency={urgency}']
                    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    # Если notify-send не найден, пробуем zenity
                    try:
                        zenity_type = "error" if flags == 0x10 else "warning" if flags == 0x30 else "info"
                        cmd = ['zenity', f'--{zenity_type}', f'--title={title}', f'--text={message}']
                        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        # Если ничего не работает, просто логируем
                        logger.warning(f"[SYSTEM MESSAGE] {title}: {message}")
                        logger.warning("Установите notify-send или zenity для системных уведомлений")
            
            await loop.run_in_executor(None, show_linux_notification)
        
        elif system == "Darwin":  # macOS
            # Определяем тип иконки для macOS
            icon_map = {
                0x10: "stop",       # MB_ICONERROR
                0x30: "caution",    # MB_ICONWARNING
                0x40: "note"        # MB_ICONINFORMATION
            }
            icon = icon_map.get(flags, "note")
            
            def show_macos_notification():
                try:
                    # Для macOS используем osascript (AppleScript)
                    # Если нужно модальное окно (use_systemmodal), используем dialog
                    if use_systemmodal:
                        script = f'display dialog "{message}" with title "{title}" with icon {icon} buttons {{"OK"}} default button "OK"'
                    else:
                        # Обычное уведомление
                        script = f'display notification "{message}" with title "{title}"'
                    
                    subprocess.run(
                        ['osascript', '-e', script],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except FileNotFoundError:
                    logger.warning(f"[SYSTEM MESSAGE] {title}: {message}")
                    logger.warning("osascript недоступен на вашей системе")
            
            await loop.run_in_executor(None, show_macos_notification)
        
        else:
            # Неизвестная ОС - просто логируем
            logger.warning(f"[SYSTEM MESSAGE] {title}: {message}")
            logger.warning(f"Системные уведомления не поддерживаются для {system}")


class HumanBehavior:
    """Методы для имитации человеческого поведения"""

    @staticmethod
    async def write(page, text, chance=0.03):
        """Печатает текст как человек с естественными задержками и опечатками
        Поле нужно выделить в фокус перед вызовом этой функции.
        """

        # Клавиатурная раскладка для реалистичных опечаток
        keyboard_layout = {
            'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sfe', 'e': 'wrs',
            'f': 'drgd', 'g': 'fhtr', 'h': 'gjuy', 'i': 'uoj', 'j': 'hkui',
            'k': 'jloi', 'l': 'kop', 'm': 'nm', 'n': 'bm', 'o': 'ipl', 'p': 'ol',
            'q': 'aw', 'r': 'etes', 's': 'awdx', 't': 'rgyf', 'u': 'yijk', 'v': 'cbb',
            'w': 'qse', 'x': 'czs', 'y': 'tguh', 'z': 'xas'
        }
        
        # Начальная задержка перед печатью
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        i = 0
        while i < len(text):
            char = text[i]
            
            # Случайные задержки "думания" посередине
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # Имитируем опечатку
            if random.random() < chance and char.isalpha():
                # Получаем похожую клавишу с клавиатуры
                wrong_chars = keyboard_layout.get(char.lower(), char)
                wrong_char = random.choice(wrong_chars)
                
                # Печатаем неправильный символ
                await page.keyboard.type(wrong_char, delay=random.randint(30, 100))
                await asyncio.sleep(random.uniform(0.3, 0.8))
                
                # Замечаем опечатку и исправляем
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(1, 3))
                
                # Иногда после исправления небольшая пауза
                if random.random() < 0.3:
                    await asyncio.sleep(random.uniform(0.5, 2))
            
            # Печатаем правильный символ
            await page.keyboard.type(char, delay=random.randint(25, 120))
            
            # Естественная задержка между символами (не линейная)
            base_delay = random.uniform(0.08, 0.35)
            
            # Иногда быстрее, иногда медленнее
            if random.random() < 0.15:
                base_delay *= random.uniform(0.3, 0.7)  # Ускорение
            elif random.random() < 0.1:
                base_delay *= random.uniform(1.5, 2.5)  # Замедление
            
            await asyncio.sleep(base_delay)
            
            # Иногда делаем более длинные паузы (как человек может отвлечься)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(1.0, 3.0))
            
            i += 1
        
        # Финальная пауза после печати
        await asyncio.sleep(random.uniform(0.2, 0.5))
    
    @staticmethod
    async def move(page, element=None, click=False, scroll=False):
        """Двигаем мышь как человек с естественной траекторией. Автоматически скроллит к элементу если он не видим на экране."""
        try:
            if scroll:
                await HumanBehavior.scroll(page, element=element)
                await asyncio.sleep(random.uniform(1, 2))

            box = await element.bounding_box()
            if not box:
                return

            # Получаем текущую позицию мыши
            try:
                current_pos = await page.evaluate("() => ({x: window.lastMouseX || 0, y: window.lastMouseY || 0})")
                start_x, start_y = current_pos['x'], current_pos['y']
            except:
                start_x, start_y = random.randint(50, 200), random.randint(50, 200)

            # Случайная точка внутри элемента
            end_x = box["x"] + box["width"] * random.uniform(0.25, 0.75)
            end_y = box["y"] + box["height"] * random.uniform(0.25, 0.75)

            # Расстояние между точками
            distance = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
            
            # Количество шагов зависит от расстояния (как у человека)
            steps = max(random.randint(15, 25), int(distance / random.uniform(5, 15)))
            
            # Контрольные точки для более естественной кривой (Bezier-подобно)
            cp1_x = start_x + (end_x - start_x) * random.uniform(0.2, 0.4)
            cp1_y = start_y + (end_y - start_y) * random.uniform(0.1, 0.3) + random.randint(-50, 50)
            
            cp2_x = start_x + (end_x - start_x) * random.uniform(0.6, 0.8)
            cp2_y = start_y + (end_y - start_y) * random.uniform(0.7, 0.9) + random.randint(-50, 50)

            # Отслеживание времени для ускорения/замедления
            for i in range(steps):
                # Нормализованное время (0 до 1)
                t = i / steps
                
                # Кубическая кривая Безье
                mt = 1 - t
                x = (mt ** 3) * start_x + 3 * (mt ** 2) * t * cp1_x + 3 * mt * (t ** 2) * cp2_x + (t ** 3) * end_x
                y = (mt ** 3) * start_y + 3 * (mt ** 2) * t * cp1_y + 3 * mt * (t ** 2) * cp2_y + (t ** 3) * end_y
                
                # Добавляем небольшой шум для более естественного вида
                x += random.uniform(-1.5, 1.5)
                y += random.uniform(-1.5, 1.5)

                await page.mouse.move(x, y)
                
                # Переменная скорость (человек не движется с одинаковой скоростью)
                delay = random.uniform(0.005, 0.02)
                
                # Иногда небольшие паузы (как у человека)
                if random.random() < 0.05:
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                
                await asyncio.sleep(delay)

            # Финальное движение к точке
            await page.mouse.move(end_x, end_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

            if click:
                await asyncio.sleep(random.uniform(0.05, 0.2))
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.mouse.up()

        except Exception as e:
            logger.error(f"Ошибка при движении мыши: {e}")
    
    @staticmethod
    async def scroll(page, element=None, direction="down", distance=None):
        """Скроллинг как человек - естественный и реалистичный"""
        
        # Если указан элемент или селектор, скроллим к элементу пока он не станет видимым
        if element:
            try:
                # Начальная пауза
                await asyncio.sleep(random.uniform(0.2, 0.5))
                
                # Скроллим пока элемент не станет видимым
                max_attempts = 20  # Максимум попыток скролла
                attempt = 0
                
                while attempt < max_attempts:
                    try:
                        box = await element.bounding_box()
                        
                        if not box:
                            attempt += 1
                            await asyncio.sleep(random.uniform(0.3, 0.6))
                            continue
                        
                        # Проверяем в пределах ли элемент экрана
                        viewport_height = await page.evaluate("() => window.innerHeight")
                        
                        if box["y"] >= 0 and box["y"] <= viewport_height:
                            logger.debug(f"✓ Элемент видим на экране")
                            await asyncio.sleep(random.uniform(0.3, 0.8))
                            return
                        
                        # Вычисляем расстояние для скролла
                        if box["y"] < 0:
                            # Элемент выше экрана - скроллим вверх
                            scroll_distance = box["y"] - random.uniform(50, 150)
                        else:
                            # Элемент ниже экрана - скроллим вниз
                            scroll_distance = box["y"] + box["height"] - viewport_height + random.uniform(50, 150)
                        
                        # Скроллим с естественным поведением
                        # Разбиваем на части
                        num_portions = random.randint(2, 4)
                        portions = []
                        remaining = scroll_distance
                        
                        for i in range(num_portions - 1):
                            portion = remaining * random.uniform(0.2, 0.5)
                            portions.append(portion)
                            remaining -= portion
                        portions.append(remaining)
                        
                        # Скроллим каждую порцию
                        for portion in portions:
                            await page.evaluate(f"window.scrollBy(0, {portion})")
                            
                            # Переменная задержка
                            base_delay = random.uniform(0.2, 0.8)
                            if random.random() < 0.1:
                                base_delay *= random.uniform(0.5, 1.0)
                            elif random.random() < 0.1:
                                base_delay *= random.uniform(1.5, 2.5)
                            
                            await asyncio.sleep(base_delay)
                            
                            # Иногда микро-прокрутки
                            if random.random() < 0.1:
                                micro_scroll = portion * random.uniform(-0.2, -0.05)
                                await page.evaluate(f"window.scrollBy(0, {micro_scroll})")
                                await asyncio.sleep(random.uniform(0.15, 0.3))
                                await page.evaluate(f"window.scrollBy(0, {-micro_scroll})")
                                await asyncio.sleep(random.uniform(0.2, 0.4))
                    
                    except Exception as e:
                        logger.debug(f"Попытка {attempt + 1}: {e}")
                    
                    attempt += 1
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                
                logger.warning(f"Не удалось скроллить к элементу за {max_attempts} попыток")
                
            except Exception as e:
                logger.error(f"Ошибка при скролле к элементу: {e}")
            return
        
        # Обычный скролл на расстояние (если селектор не указан)
        
        # Получаем размер viewport из браузера
        if distance is None:
            viewport_height = await page.evaluate("() => window.innerHeight")
            distance = viewport_height
        
        # Определяем направление
        if direction == "up":
            distance = -distance
        
        # Начальная пауза перед скроллом
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        # Делим расстояние на несколько частей с вариацией
        num_portions = random.randint(2, 5)
        
        # Создаём непредсказуемые размеры порций
        portions = []
        remaining = distance
        for i in range(num_portions - 1):
            portion = remaining * random.uniform(0.15, 0.45)
            portions.append(portion)
            remaining -= portion
        portions.append(remaining)
        
        # Скроллим каждую порцию
        for i, portion in enumerate(portions):
            # Основная прокрутка
            await page.evaluate(f"window.scrollBy(0, {portion})")
            
            # Переменная задержка (человек по-разному скроллит)
            base_delay = random.uniform(0.3, 1.2)
            
            # Иногда очень быстро
            if random.random() < 0.1:
                base_delay *= random.uniform(0.3, 0.6)
            # Иногда медленно "разглядывает"
            elif random.random() < 0.15:
                base_delay *= random.uniform(1.8, 3.0)
            
            await asyncio.sleep(base_delay)
            
            # Иногда человек скроллит туда-сюда (делает микро-прокрутки)
            if random.random() < 0.12 and i < len(portions) - 1:
                micro_scroll = portion * random.uniform(-0.3, -0.1)
                await page.evaluate(f"window.scrollBy(0, {micro_scroll})")
                await asyncio.sleep(random.uniform(0.15, 0.4))
                # Возвращается обратно
                await page.evaluate(f"window.scrollBy(0, {-micro_scroll})")
                await asyncio.sleep(random.uniform(0.2, 0.5))
            
            # Иногда делает длинную паузу (как думает, что-то читает)
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(1.5, 4.0))
        
        # Финальная пауза после скролла
        await asyncio.sleep(random.uniform(0.3, 0.9))


    @staticmethod
    async def sleep(preset="medium", custom_range: tuple = None):
        """
        Универсальная человеческая задержка.
        Presets: 'micro', 'small', 'medium', 'long', 'afk'
        """
        if custom_range:
            await asyncio.sleep(random.uniform(*custom_range))
            return

        presets = {
            "micro": (0.1, 0.5),  # Быстрая реакция, микродвижения
            "small": (0.3, 1),  # Короткая пауза между кликами
            "medium": (1, 2), # Обычное ожидание
            "long": (2, 5),   # Чтение короткого текста
            "afk": (8, 20)    # Имитация "отошел от ПК" или чтение страницы
        }

        wait_time = random.uniform(*presets.get(preset, presets["medium"]))
        await asyncio.sleep(wait_time)


# Пример использования
async def main():
    async with ChromeManager() as manager:
        page = manager.page

        await page.goto('https://example.com/')

        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())