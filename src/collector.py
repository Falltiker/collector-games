import requests
from bs4 import BeautifulSoup as BS
from fake_useragent import UserAgent
from loguru import logger



@logger.catch
def get_games():
    headers = {
        'Referer': 'https://store.steampowered.com/search/?force_infinite=1&maxprice=free&specials=1&ndl=1',
        'User-Agent': UserAgent(browsers="chrome", platforms="desktop").random,
        'Accept': '*/*',
    }

    # В запросе уже есть параметры фильтрации
    response = requests.get('https://store.steampowered.com/search/results?force_infinite=1&maxprice=free&specials=1&ndl=1&snr=1_7_7_230_7', headers=headers)
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
        logger.debug(f"ID игры: {app_id}")
        title = game.find("span", class_="title").text
        logger.debug(f"Название {title}")
        discounted_price_tag = game.find("div", class_="discount_final_price")
        discounted_price = discounted_price_tag.text.strip() if discounted_price_tag else 0
        currency_symbol = discounted_price[-1]
        logger.debug(f"Символ валюты: {currency_symbol}")
        discounted_price = str(discounted_price).replace(",", ".")[:-1]  # Убираем знак валюты, меняем запятую на точку для преобразования в float
        discounted_price = float(discounted_price)
        logger.debug(f"Цена: {discounted_price}{currency_symbol}")
        # Проверяем, что цена нулевая. Не знаю почему, но иногда игра может быть не со 100% скидкой, хотя фильтр не должен показывать такие игры
        # Мне кажется, что это я забыл убрать плсле испрвления какой то части кода.
        if discounted_price != 0:
            logger.debug(f"Не бесплатна, цена: {discounted_price}")
            continue

        url = game.get("href")
        logger.debug(f"URL: {url}")
        image = game.find("div", class_="search_capsule").find("img").get("src")
        logger.debug(f"Изображение: {image}")
        original_price = game.find("div", class_="discount_original_price")
        logger.debug(f"Цена без скидки: {original_price.text.strip() if original_price else 'Нет оригинальной цены'}")

        res = requests.get(url)
        soup = BS(res.text, "lxml")
        logger.debug(f"Получен HTML-код страницы, для детальой информации: {url}.")

        desc_tag = soup.find("div", class_="game_description_snippet")
        description = desc_tag.text.strip() if desc_tag else "Описание не найдено"
        logger.debug(f"Описание: {description}")

        mini_div_info = soup.find("div", class_="glance_ctn_responsive_left")

        user_reviews = mini_div_info.find("div", id="userReviews")
        logger.debug("Получен div id=userReviews")
        recent_reviews_row = user_reviews.find("div", class_="summary column")
        logger.debug("Получен div class=summary column")
        review_summary = recent_reviews_row.find_all("span")[0].text.strip()
        logger.debug(f"Общее впечатление {review_summary}")
        try:
            review_count_text = recent_reviews_row.find_all("span")[1].text.strip()
            review_count = int(review_count_text.strip("()").replace(",", "").replace(" ", ""))
        except Exception as e:
            review_count = review_count_text
            logger.debug(f" Недостаточно обзоров для расчета рейтинга: Ошибка: {e}")

        logger.debug(f"Недавние отзывы: {review_count} отзывов, общее впечатление: {review_summary}")

        all_reviews = user_reviews.find_all("a", class_="user_reviews_summary_row")[-1]["data-tooltip-html"]
        logger.debug(f"Все отзывы {all_reviews}")

        release_date_tag = mini_div_info.find("div", class_="date")
        release_date = release_date_tag.text.strip() if release_date_tag else "Дата выпуска не указана"
        logger.debug(f"Дата выпуска: {release_date}")

        # Здесь я не уверен, может быть что, в стиме не указываться разработчик и издатель?.
        developer_url = mini_div_info.find("div", id="developers_list").find("a")["href"]
        developer_name_tag = mini_div_info.find("div", id="developers_list").find("a")
        developer_name = developer_name_tag.text.strip() if developer_name_tag else "Разработчик не указан"
        developer = {
            "name": developer_name,
            "url": developer_url
        }
        logger.debug(f"Разработчик {developer_name} ({developer_url})")

        publisher_tag = mini_div_info.find_all("div", class_="dev_row")[-1]
        if publisher_tag:
            publisher_link = publisher_tag.find("a")
            publisher_name = publisher_link.text.strip() if publisher_link else "Издатель не указан"
            publisher_url = publisher_link["href"] if publisher_link and publisher_link.has_attr("href") else "Издатель не указан"
        else:
            publisher_name = "Издатель не указан"
            publisher_url = "Издатель не указан"

        publisher = {
            "name": publisher_name,
            "url": publisher_url
        }
        logger.debug(f"Издатель {publisher_name} ({publisher_url})")

        dlc = soup.find("div", class_="game_area_bubble game_area_dlc_bubble")
        if dlc:
            dlc_url = dlc.find("a")["href"]
            dlc_name_tag = dlc.find("a")
            dlc_name = dlc_name_tag.text.strip()
            dlc = {
                "name": dlc_name,
                "url": dlc_url
            }
            logger.debug(f"DLC {dlc_name} ({dlc_url})")
        else:
            dlc = None
        
        games_list[app_id] = {
            "name": title,
            "url": url,
            "image": image,
            "description": description,
            "discounted_price": discounted_price,
            "currency_symbol": currency_symbol,
            "original_price": original_price.text.strip() if original_price else "Нет оригинальной цены",
            "developer": developer,
            "publisher": publisher,
            "release_date": release_date,
            "recent_reviews": review_count,
            "all_reviews": all_reviews,
            "dlc": dlc,
            "status": "new"
        }

        logger.info(f"Обработка {title} завершена.")

    logger.info("👏 Все игры успешно обработано.")
    return games_list


if __name__ == "__main__":
    games_list = get_games()
    print(games_list)