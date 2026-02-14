import requests
import time
import re
from bs4 import BeautifulSoup as BS
from fake_useragent import UserAgent
from loguru import logger



@logger.catch
def processing_game(headers, all_games:list = []):
    

    return games_list


@logger.catch
def get_games():
    headers = {
        'Referer': 'https://store.steampowered.com/search/?force_infinite=1&maxprice=free&specials=1&ndl=1',
        'User-Agent': UserAgent(browsers="chrome", platforms="desktop").random,
        'Accept': '*/*',
    }

    # В запросе уже есть параметры фильтрации
    response = requests.get(
        'https://store.steampowered.com/search/results?force_infinite=1&maxprice=free&specials=1&ndl=1&snr=1_7_7_230_7', 
        headers=headers,
        timeout=10
        )
    soup = BS(response.text, "lxml")
    logger.debug(f"Ответ {response.status_code}")

    try:
        all_games = soup.find("div", id="search_resultsRows")
        all_games = all_games.find_all("a", recursive=False)
    except Exception as e:
        logger.info(f"Сейчас нету бесплатных игр! {e}")
        return

    logger.info(f"Получено {len(all_games)} игр из ответа.")
    if not all_games:
        logger.warning("Список игр пуст.")
        return 

    games_list = dict()
    for game in all_games:
        app_id = game["data-ds-appid"]

        title = game.find("span", class_="title").text

        discounted_price_tag = game.find("div", class_="discount_final_price")
        discounted_price = 0
        currency_symbol = "?"
        if discounted_price_tag:
            price_text = discounted_price_tag.text.strip()
            if price_text and len(price_text) > 1:
                currency_symbol = price_text[-1]
                try:
                    discounted_price = re.search(r'[\d,.]+', price_text).group()
                    discounted_price = float(discounted_price.replace(",", ".").replace(" ", ""))
                except ValueError:
                    logger.warning(f"Не удалось распарсить цену: {price_text}")
        logger.debug(f"Цена: {discounted_price}{currency_symbol}")

        # Проверяем, что цена нулевая. Не знаю почему, но иногда игра может быть не со 100% скидкой, хотя фильтр не должен показывать такие игры
        # Мне кажется, что это я забыл убрать после исправления какой то части кода.
        if discounted_price != 0:
            logger.warning(f"Игра {title} не бесплатна, цена: {discounted_price}{currency_symbol}")
            continue

        url = game.get("href")

        image = game.find("div", class_="search_capsule").find("img").get("src")

        orig_price_tag = game.find("div", class_="discount_original_price")
        original_price = orig_price_tag.text.strip() if orig_price_tag else None
        if not original_price:
            logger.warning(f"У {title} оригинальная цена не найдена.")

        res = requests.get(
            url,
            headers=headers,
            timeout=10
            )
        logger.debug(f'Ответ {res.status_code}')
        soup = BS(res.text, "lxml")

        desc_tag = soup.find("div", class_="game_description_snippet")
        description = desc_tag.text.strip() if desc_tag else None
        if not description:
            logger.warning(f"Описание {title} не найдено.")

        # Просто перешли в удобный блок для дальнейшей разборки
        mini_div_info = soup.find("div", class_="glance_ctn_responsive_left")

        user_reviews = mini_div_info.find("div", id="userReviews") # блок с впечатлениями и отзывами
        review_summary = None
        review_count = None
        if user_reviews:
            recent_reviews_row = user_reviews.find("div", class_="summary column")
            review = recent_reviews_row.find_all("span")

            if review:
                review_summary = review[0].text.strip()

                try:
                    review_count_text = review[1].text.strip()
                    review_count = int(review_count_text.strip("()").replace(",", "").replace(" ", ""))
                except Exception as e:
                    review_count = None
                    logger.debug(f"Недостаточно обзоров для расчета рейтинга: Ошибка: {e}")

        else:
            logger.warning(f"Отзывы {title} не найдены.")


        release_date_tag = mini_div_info.find("div", class_="date")
        release_date = release_date_tag.text.strip() if release_date_tag else None
        if not release_date:
            logger.warning(f"Дата выхода {title} не найдена.")

        # Здесь я не уверен, может быть что, в Steam не указываться разработчик и издатель?.
        developer_div = mini_div_info.find("div", id="developers_list")
        developer_link = developer_div.find("a") if developer_div else None

        if developer_link:
            developer = {
                "name": developer_link.text.strip(),
                "url": developer_link.get("href", "")
            }
        else:
            developer = {"name": "Не указан", "url": ""}
            logger.warning(f"Разработчик {title} не найден.")

        publisher_tag = mini_div_info.find_all("div", class_="dev_row")[-1]
        publisher_name = None
        publisher_url = None
        if publisher_tag:
            publisher_link = publisher_tag.find("a")
            publisher_name = publisher_link.text.strip() if publisher_link else None
            publisher_url = publisher_link["href"] if publisher_link and publisher_link.has_attr("href") else None

        publisher = {
            "name": publisher_name,
            "url": publisher_url
        }


        # Я думаю полностью скипать DLC к платным играм, так как стим уведомит о скидке что в желаемом.
        # Если что позже можно будет добавить такую функциональность
        dlc_tag = soup.find("div", class_="game_area_bubble game_area_dlc_bubble")
        dlc = dict()
        if dlc_tag:
            dlc_url = dlc_tag.find("a")["href"]
            dlc_app_id = dlc_url.split("/")[-2]

            dlc_name_tag = dlc_tag.find("a")
            dlc_name = dlc_name_tag.text.strip()

            logger.debug(f"{title} DLC к игре {dlc_name}")

            res = requests.get(
                dlc_url, 
                headers=headers,
                timeout=10)
            logger.debug(f'Ответ {res.status_code}')
            soup = BS(res.text, "lxml")

            price_tag = soup.find("div", class_="game_purchase_price price")
            price = price_tag.text.strip() if price_tag else None

            btn = soup.find("div", id="freeGameBtn")

            if btn:
                price = 0
            elif price:
                price = re.search(r'[\d,.]+', price).group()
                price = float(price.replace(",", ".").replace(" ", ""))

            if price > 0:
                logger.debug(f"Цена игры {title} к которой прикреплен DLC: {price}")
                continue

            dlc = {
            "app_id": dlc_app_id,
            "name": dlc_name,
            "url": dlc_url,
            "price": price
            }

        else:
            dlc = None

        games_list[app_id] = {
            "name": title,
            "url": url,
            "image": image,
            "description": description,
            "discounted_price": discounted_price,
            "currency_symbol": currency_symbol,
            "original_price": original_price,
            "developer": developer,
            "publisher": publisher,
            "release_date": release_date,
            "recent_reviews": review_count,
            "recent_summary": review_summary,
            "dlc": dlc,
            "status": "new"
        }

        time.sleep(2)

        logger.info(f"✅ Обработана: {title} | Рейтинг: {review_summary} ({review_count} отз.)")
        logger.debug(f"Информация о игре: {games_list[app_id]}\n{"="*100}")


    return games_list


if __name__ == "__main__":
    games_list = get_games()
    print(games_list)