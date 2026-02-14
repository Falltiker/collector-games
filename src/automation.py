import asyncio
from src.utils.chrome_manager import ChromeManager
from src.utils.chrome_manager import HumanBehavior as HB
from loguru import logger
import json
import os



@logger.catch
async def check_auth(page):
    is_auth = page.locator("#header_wallet_ctn").first
    return await is_auth.is_visible()


@logger.catch
async def run_manual_auth(manager, page):
    btn_login = page.locator('a.global_action_link').first
    logger.debug('Нашли кнопку авторизации.')

    await HB.move(page, element=btn_login, click=True)
    logger.debug("Нажали на кнопку авторизации.")
    await HB.sleep()

    await manager.show()
    logger.debug("Вывели браузер.")

    await ChromeManager().system_message(title="Authorization Required",
                                        message="Please log in to your account in the browser window.", 
                                        use_topmost=True,
                                        use_systemmodal=True,
                                        use_foreground=True
                                        )
    
    HB.sleep("long")

    await page.wait_for_selector("#header_wallet_ctn", timeout=999*1000)
    await manager.hide()
    logger.debug("Скрыли браузер.")
    await HB.sleep()


@logger.catch
async def one_started_run_manual_auth():
    """Запускаем 1 раз при первом запуске скрипта для авторизации.
    Запускается если не находит папку профиля браузера.
    """

    profile_dir = "profile"

    if not os.path.isdir(profile_dir):
        logger.info("Нету папки профиля, запукаем авторизацию.")
        async with ChromeManager() as manager:
            page = manager.page

            await page.goto("https://store.steampowered.com/", wait_until="domcontentloaded")
            logger.debug("Перешли на Steam.")
            await HB.sleep("long")

            if not await check_auth(page):
                await run_manual_auth(manager, page)

            await HB.sleep()

            await page.goto("https://store.steampowered.com/search?term=", wait_until="domcontentloaded")
            await HB.sleep()


@logger.catch
async def collect_game(page, app_id, info):
    await page.goto(info["url"], wait_until="domcontentloaded")
    await HB.sleep("long")
    logger.debug(f'Перешли на страницу игры {info["name"]}, app_id: {app_id}.')

    btn  = page.locator('a[href*="javascript:addToCart"]').first
    btn2 = page.locator('div.btn_addtocart btn_packageinfo').first
    if await btn.is_visible():
        logger.debug("Нашли кнопку забрать в библиотеку.")
        await HB.move(page, element=btn, click=True, scroll=True)

        logger.info(f"Забрали игру {info['name']} app_id: {app_id}.")
        await HB.sleep("long")

    elif await btn2.is_visible():
        logger.debug("Нашли кнопку забрать в библиотеку.")
        await HB.move(page, element=btn2, click=True, scroll=True)

        logger.debug("Нажали на кнопку и переходим к следующей по списку.")
        await HB.sleep()

    else:
        logger.debug("Игра уже в библиотеке, помечаем как забранная.")



@logger.catch
async def collect_games(games_list):
    async with ChromeManager() as manager:
        page = manager.page

        await page.goto("https://store.steampowered.com/", wait_until="domcontentloaded")
        logger.debug("Перешли на Steam.")
        await HB.sleep("long")

        if not await check_auth(page):
            await run_manual_auth(manager, page)

        for app_id, info in games_list.items():
            if info["status"] != "new":
                continue
            dlc = info["dlc"]

            try:
                if dlc:
                    await collect_game(page, dlc["app_id"], dlc)
                    logger.info(f"Забрали игру {dlc['name']} к которой пренадлежит ДЛС {info['name']}.")
                    await collect_game(page, app_id, info)
                else:
                    await collect_game(page, app_id, info)
                games_list[app_id]["status"] = "collected"

            except Exception as e:
                games_list[app_id]["status"] = "new"
                logger.error(f"Сбой на {app_id}: {e}")

        return games_list



if __name__ == "__main__":
    with open("data/games.json", "r", encoding="utf-8") as f:
        games_list = json.load(f)

    games_list = asyncio.run(collect_games(games_list))

    with open("data/games.json", "w", encoding="utf-8") as f:
        json.dump(games_list, f, indent=4, ensure_ascii=False)


