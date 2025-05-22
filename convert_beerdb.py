from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time

# URL страницы с пивом на сайте Метро
url = 'https://online.metro-cc.ru/category/alkogolnaya-produkciya/pivo-sidr?from=under_search'

# Настройка ChromeDriver
chrome_options = Options()
# НЕ используем headless, чтобы пользователь мог вручную нажать кнопку
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# Запускаем браузер в обычном режиме
driver = webdriver.Chrome(options=chrome_options)

try:
    driver.get(url)
    print("Страница открыта в браузере. Пожалуйста, вручную нажмите кнопку 'Подтвердить возраст'.")
    input("После подтверждения возраста нажмите Enter в консоли для продолжения парсинга...")

    # Ждём загрузки карточек товаров
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '.product-card'))
    )
    print("Карточки товаров загружены.")

    items = driver.find_elements(By.CSS_SELECTOR, '.product-card')
    print(f"Найдено карточек товаров: {len(items)}")

    # Список для хранения данных о пиве
    beers = []

    # Обрабатываем каждую карточку
    for idx, item in enumerate(items):
        try:
            name_elem = item.find_element(By.CSS_SELECTOR, '.product-card-name__text')
            name = name_elem.text.strip()
            # Получаем ссылку на карточку товара
            link_elem = name_elem.find_element(By.XPATH, '..')
            link = link_elem.get_attribute('href')
            if not link:
                print(f"Пропущено: {name} (нет ссылки)")
                continue
        except Exception as e:
            print(f"Ошибка при получении ссылки для товара: {e}")
            continue

        # Открываем карточку товара в новой вкладке
        driver.execute_script("window.open(arguments[0]);", link)
        driver.switch_to.window(driver.window_handles[1])

        # Ждём загрузки блока с атрибутами
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.product-attributes__list'))
            )
            attrs = driver.find_elements(By.CSS_SELECTOR, '.product-attributes__list-item')
            beer_info = {'name': name}
            for attr in attrs:
                try:
                    key = attr.find_element(By.CSS_SELECTOR, '.product-attributes__list-item-name-text').text.strip()
                    value = attr.find_element(By.CSS_SELECTOR, '.product-attributes__list-item-link').text.strip()
                    # Маппинг ключей
                    if key == 'Бренд':
                        beer_info['brand'] = value
                    elif key == 'Страна-производитель':
                        beer_info['country'] = value
                    elif key == 'Вес, объем':
                        beer_info['volume'] = value
                    elif key == 'Крепость, %':
                        beer_info['abv'] = value
                    elif key == 'Сорт':
                        beer_info['style'] = value
                    elif key == 'Плотность, %':
                        beer_info['density'] = value
                    elif key == 'Цвет':
                        beer_info['color'] = value
                    elif key == 'Тип упаковки':
                        beer_info['package'] = value
                    elif key == 'Фильтрация':
                        beer_info['filtration'] = value
                    elif key == 'Импорт':
                        beer_info['imported'] = value
                    elif key == 'Вкусовое':
                        beer_info['flavored'] = value
                except Exception as e:
                    continue
            # Парсим описание, если оно есть
            try:
                # В первую очередь ищем .product-text-description__content-text
                desc_elem = driver.find_element(By.CSS_SELECTOR, '.product-text-description__content-text')
                beer_info['description'] = desc_elem.text.strip()
            except Exception:
                try:
                    desc_elem = driver.find_element(By.CSS_SELECTOR, '.product-about, .product-description__text')
                    beer_info['description'] = desc_elem.text.strip()
                except Exception:
                    beer_info['description'] = ''
            beers.append(beer_info)
        except Exception as e:
            print(f"Ошибка при парсинге карточки {name}: {e}")
        finally:
            # Закрываем вкладку и возвращаемся к списку
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        time.sleep(1)  # чтобы не перегружать сайт

    # Добавляем поля 'description' и 'rating' (пустые) для каждого объекта пива, чтобы бот не падал с ошибкой
    for beer in beers:
        beer['description'] = ''
        beer['rating'] = ''

    # Сохраняем в JSON
    with open('beer_db.json', 'w', encoding='utf-8') as f:
        json.dump(beers, f, ensure_ascii=False, indent=2)

    print(f'Готово! Сохранено {len(beers)} сортов в beer_db.json')

finally:
    # Закрываем браузер
    driver.quit() 