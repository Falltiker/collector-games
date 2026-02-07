from loguru import logger
import sys
from src import collector
from src import automation
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
import json
import os


logger.remove()
logger.add(
    sys.stderr, 
    level="INFO",
    backtrace=True, 
    diagnose=True,
    )
logger.add(
    "logs/DEBUG_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="10 MB",
    retention=5,
    backtrace=True, 
    diagnose=True
    )
logger.add(
    "logs/ERROR_{time:YYYY-MM-DD}.log",
    level="ERROR",
    rotation="10 MB",
    retention=5,
    backtrace=True, 
    diagnose=True
    )


@logger.catch
def games_list_update(games_list):
    """Обновляет список игр, сохраняя статусы из старого файла"""
    file_path = "data/games.json"
    
    if games_list is None:
        logger.error("games_list is None, используем пустой словарь")
        games_list = {}
    
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                old_games = json.load(f)
            except json.JSONDecodeError:
                old_games = {}
                logger.error("Файл games.json поврежден или пустой.")
    else:
        old_games = {}
        logger.debug("Файл games.json не существует, создаем новый")
    
    for app_id, new_info in games_list.items():
        if app_id in old_games:
            new_info["status"] = old_games[app_id].get("status", "new")
        else:
            new_info["status"] = "new"
    
    for app_id, old_info in old_games.items():
        if app_id not in games_list:
            games_list[app_id] = old_info
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(games_list, f, ensure_ascii=False, indent=4)
    
    new_count = sum(1 for g in games_list.values() if g.get("status") == "new")
    logger.debug(f"Обновлен список игр: всего {len(games_list)}, новых: {new_count}")
    
    return games_list


@logger.catch
async def auto_collector():
    new_games_list = collector.get_games()
    
    # ✅ Проверка что коллектор вернул данные
    if new_games_list is None:
        logger.error("collector.get_games() вернул None!")
        new_games_list = {}
    
    if not isinstance(new_games_list, dict):
        logger.error(f"collector.get_games() вернул не словарь: {type(new_games_list)}")
        new_games_list = {}
    
    logger.info(f"Получено игр от коллектора: {len(new_games_list)}")
    
    games_list = games_list_update(new_games_list)
    
    new_games = sum(1 for g in games_list.values() if g.get("status") == "new")
    
    if new_games > 0:
        logger.info(f"Запускаем сбор для {new_games} новых игр")
        games_list = await automation.collect_games(games_list)
        
        if games_list:
            with open("data/games.json", "w", encoding="utf-8") as f:
                json.dump(games_list, f, indent=4, ensure_ascii=False)
            logger.success("Сбор завершен, данные сохранены")
    else:
        logger.info("Новых игр нет, пропускаем автоматизацию")
    
    logger.info("Ждем следующего запуска функции.")


@logger.catch
async def main():
    await automation.one_started_run_manual_auth()

    await auto_collector()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_collector, 'interval', hours=5, max_instances=1) 
    scheduler.start()
    logger.info("Планировщик запущен (каждые 5 часов)")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.warning("Скрипт остановлен пользователем")


if __name__ == "__main__":
    asyncio.run(main())
