import json
from datetime import datetime
import requests
import xml.etree.ElementTree as ET


SAVE_FILE = "last_calculation.json"


def get_usd_rate():
    response = requests.get("https://www.cbr.ru/scripts/XML_daily.asp")
    response.raise_for_status()

    root = ET.fromstring(response.content)

    for valute in root.findall("Valute"):
        if valute.find("CharCode").text == "USD":
            return float(valute.find("Value").text.replace(",", "."))

    raise ValueError("Не удалось найти курс USD.")


def get_crypto_rates():
    response = requests.get(
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
    )
    response.raise_for_status()

    data = response.json()
    btc_usd = data["bitcoin"]["usd"]
    eth_usd = data["ethereum"]["usd"]

    return btc_usd, eth_usd


def get_rates():
    usd_rate = get_usd_rate()
    btc_usd, eth_usd = get_crypto_rates()

    btc_rub = btc_usd * usd_rate
    eth_rub = eth_usd * usd_rate

    rates = {
        "RUB": 1,
        "USD": usd_rate,
        "BTC": btc_rub,
        "ETH": eth_rub
    }

    return rates


def wait_back_to_menu():
    input("\nНажмите Enter, чтобы вернуться в главное меню...")


def save_last_calculation(calculation_data):
    with open(SAVE_FILE, "w", encoding="utf-8") as file:
        json.dump(calculation_data, file, ensure_ascii=False, indent=4)


def load_last_calculation():
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError("Ошибка: сохранённый расчёт не найден.")


def print_calculation(calculation_data):
    print("\n= ПОСЛЕДНИЙ СОХРАНЁННЫЙ РАСЧЁТ =")
    print(f"Дата: {calculation_data['date']}")
    print(
        f"Расчёт: {calculation_data['amount']} {calculation_data['from_currency']} "
        f"= {calculation_data['result']:.2f} {calculation_data['to_currency']}"
    )


def convert_currency():
    last_calculation = None

    while True:
        print("\n= КОНВЕРТАЦИЯ ВАЛЮТ =")
        print("Доступные валюты: USD, RUB, BTC, ETH")
        print("Введите 0 в любой момент для возврата в главное меню.")
        print("9. Загрузить последний сохранённый расчёт")

        choice = input("Выберите действие или нажмите Enter для новой конвертации: ").strip()

        if choice == "0":
            return
        elif choice == "9":
            try:
                saved_data = load_last_calculation()
                print_calculation(saved_data)
            except Exception as e:
                print(e)
            continue

        try:
            rates = get_rates()
        except Exception as e:
            print(f"Ошибка при получении курсов: {e}")
            wait_back_to_menu()
            return

        from_currency = input("Из какой валюты переводить: ").upper()
        if from_currency == "0":
            return

        to_currency = input("В какую валюту переводить: ").upper()
        if to_currency == "0":
            return

        if from_currency not in rates or to_currency not in rates:
            print("Ошибка: введена неподдерживаемая валюта.")
            continue

        amount_input = input("Введите сумму: ")
        if amount_input == "0":
            return

        try:
            amount = float(amount_input)
            if amount <= 0:
                print("Ошибка: сумма должна быть больше нуля.")
                continue
        except ValueError:
            print("Ошибка: сумма должна быть числом.")
            continue

        rub = amount * rates[from_currency]
        result = rub / rates[to_currency]
        current_date = datetime.now().strftime("%d.%m.%Y")

        last_calculation = {
            "date": current_date,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount,
            "result": result
        }

        print("\nРезультат:")
        print(f"{amount} {from_currency} = {result:.2f} {to_currency}")

        print("\n1. Выполнить ещё одну конвертацию")
        print("2. Сохранить последний расчёт")
        print("3. Загрузить последний сохранённый расчёт")
        print("4. Вернуться в главное меню")
        action = input("Выберите действие: ").strip()

        if action == "2":
            try:
                save_last_calculation(last_calculation)
                print("Последний расчёт успешно сохранён.")
            except Exception as e:
                print(f"Ошибка при сохранении: {e}")
        elif action == "3":
            try:
                saved_data = load_last_calculation()
                print_calculation(saved_data)
            except Exception as e:
                print(e)
        elif action == "4":
            return


def favorites_menu():
    while True:
        print("\n= ИЗБРАННЫЕ =")
        print("Здесь будет возможность добавлять валюты в избранное.")
        print("\n1. Вернуться в главное меню")

        choice = input("Выберите действие: ")
        if choice == "1":
            return
        else:
            print("Неверный выбор. Попробуйте снова.")


def help_menu():
    while True:
        print("\n= ПОМОЩЬ =")
        print("Здесь будет написано, как работает программа.")
        print("Программа получает:")
        print("- курс доллара с сайта ЦБ РФ")
        print("- курс Bitcoin и Ethereum через CoinGecko")
        print("После этого выполняется конвертация между RUB, USD, BTC и ETH.")
        print("Также можно сохранить и загрузить последний расчёт в JSON.")
        print("\n1. Вернуться в главное меню")

        choice = input("Выберите действие: ")
        if choice == "1":
            return
        else:
            print("Неверный выбор. Попробуйте снова.")


def main_menu():
    while True:
        print("\n= ГЛАВНОЕ МЕНЮ =")
        print("1. Конвертировать валюту")
        print("2. Избранные")
        print("3. Помощь")
        print("4. Выход")

        choice = input("Выберите пункт меню: ")

        if choice == "1":
            convert_currency()
        elif choice == "2":
            favorites_menu()
        elif choice == "3":
            help_menu()
        elif choice == "4":
            print("Выход из программы.")
            break
        else:
            print("Неверный выбор. Попробуйте снова.")


if __name__ == "__main__":
    main_menu()