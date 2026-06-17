import json
import sys
from datetime import datetime
import xml.etree.ElementTree as ET

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

SAVE_FILE = "last_calculation.json"
FAVORITES_FILE = "favorites.json"
CBR_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
)

SUPPORTED_CURRENCIES = [
    "RUB", "USD", "EUR", "CNY", "TRY", "AED", "KZT", "BYN", "UZS",
    "AMD", "GEL", "KGS", "JPY", "AZN", "INR", "THB", "EGP", "CHF",
    "BTC", "ETH"
]

CURRENCY_NAMES = {
    "RUB": "Российский рубль",
    "USD": "Доллар США",
    "EUR": "Евро",
    "CNY": "Китайский юань",
    "TRY": "Турецкая лира",
    "AED": "Дирхам ОАЭ",
    "KZT": "Казахстанский тенге",
    "BYN": "Белорусский рубль",
    "UZS": "Узбекский сум",
    "AMD": "Армянский драм",
    "GEL": "Грузинский лари",
    "KGS": "Киргизский сом",
    "JPY": "Японская иена",
    "AZN": "Азербайджанский манат",
    "INR": "Индийская рупия",
    "THB": "Таиландский бат",
    "EGP": "Египетский фунт",
    "CHF": "Швейцарский франк",
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
}


class RateService:
    FIAT_CURRENCIES = [
        "USD", "EUR", "CNY", "TRY", "AED", "KZT", "BYN", "UZS",
        "AMD", "GEL", "KGS", "JPY", "AZN", "INR", "THB", "EGP", "CHF"
    ]

    @staticmethod
    def get_cbr_rates() -> dict[str, float]:
        response = requests.get(CBR_URL, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        rates = {"RUB": 1.0}

        for valute in root.findall("Valute"):
            char_code = valute.find("CharCode")
            value = valute.find("Value")
            nominal = valute.find("Nominal")

            if char_code is None or value is None or nominal is None:
                continue

            code = char_code.text
            if code not in RateService.FIAT_CURRENCIES:
                continue

            value_rub = float(value.text.replace(",", "."))
            nominal_value = float(nominal.text.replace(",", "."))

            rates[code] = value_rub / nominal_value

        missing = [code for code in RateService.FIAT_CURRENCIES if code not in rates]
        if missing:
            raise ValueError(f"Не удалось найти курсы валют ЦБ РФ: {', '.join(missing)}")

        return rates

    @staticmethod
    def get_crypto_rates() -> tuple[float, float]:
        response = requests.get(COINGECKO_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
        btc_usd = data["bitcoin"]["usd"]
        eth_usd = data["ethereum"]["usd"]
        return float(btc_usd), float(eth_usd)

    @classmethod
    def get_rates(cls) -> dict[str, float]:
        rates = cls.get_cbr_rates()

        usd_rate = rates["USD"]
        btc_usd, eth_usd = cls.get_crypto_rates()

        rates["BTC"] = btc_usd * usd_rate
        rates["ETH"] = eth_usd * usd_rate

        return rates


class StorageService:
    @staticmethod
    def save_last_calculation(calculation_data: dict) -> None:
        with open(SAVE_FILE, "w", encoding="utf-8") as file:
            json.dump(calculation_data, file, ensure_ascii=False, indent=4)

    @staticmethod
    def load_last_calculation() -> dict:
        with open(SAVE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def save_favorites(favorites: list[str]) -> None:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as file:
            json.dump(favorites, file, ensure_ascii=False, indent=4)

    @staticmethod
    def load_favorites() -> list[str]:
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return [currency for currency in data if currency in SUPPORTED_CURRENCIES]
        except FileNotFoundError:
            return []
        except Exception:
            return []
        return []


class CurrencyMixin:
    @staticmethod
    def get_currency_name(currency_code: str) -> str:
        return CURRENCY_NAMES.get(currency_code, currency_code)

    @classmethod
    def format_currency_display(cls, currency_code: str, with_star: bool = False) -> str:
        prefix = "★ " if with_star else ""
        return f"{prefix}{currency_code} — {cls.get_currency_name(currency_code)}"


class MenuPage(QWidget):
    def __init__(self, open_converter, open_help, open_favorites, exit_app):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(18)
        layout.setContentsMargins(80, 40, 80, 40)

        title = QLabel("Меню")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("pageTitle")
        title.setFixedSize(220, 86)
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(24)

        buttons = [
            ("Начать\nконвертацию", open_converter),
            ("Избранные\nвалюты", open_favorites),
            ("Помощь", open_help),
            ("Выход", exit_app),
        ]

        for text, handler in buttons:
            btn = QPushButton(text)
            btn.setFixedSize(220, 86)
            btn.clicked.connect(handler)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()


class ConversionPage(QWidget, CurrencyMixin):
    def __init__(self, go_back):
        super().__init__()
        self.go_back = go_back
        self.current_rates: dict[str, float] | None = None
        self.last_calculation_data: dict | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(80, 40, 80, 40)
        root.setSpacing(18)

        header = QGridLayout()
        header.setContentsMargins(-12, 0, 0, 0)
        header.setHorizontalSpacing(0)
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 1)
        header.setColumnStretch(2, 1)

        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.save_current_calculation)
        self.save_button.setFixedSize(140, 50)
        header.addWidget(
            self.save_button,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        title = QLabel("Конвертация")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("pageTitle")
        title.setFixedSize(220, 86)
        header.addWidget(title, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.go_back)
        back_button.setFixedSize(140, 50)
        header.addWidget(
            back_button,
            0,
            2,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )

        root.addLayout(header)
        root.addSpacing(18)

        center_grid = QGridLayout()
        center_grid.setHorizontalSpacing(40)
        center_grid.setVerticalSpacing(16)

        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("Введите сумму")
        self.amount_edit.textChanged.connect(self.update_conversion)
        self.amount_edit.setMinimumHeight(52)

        self.from_combo = QComboBox()
        self.from_combo.currentTextChanged.connect(self.update_conversion)
        self.from_combo.setMinimumHeight(52)
        self.from_combo.setFixedWidth(115)
        self.from_combo.view().setMinimumWidth(115)
        self.from_combo.setMaxVisibleItems(12)

        self.result_label = QLabel("Результат появится здесь")
        self.result_label.setObjectName("boxedLabel")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setMinimumHeight(52)

        self.to_combo = QComboBox()
        self.to_combo.currentTextChanged.connect(self.update_conversion)
        self.to_combo.setMinimumHeight(52)
        self.to_combo.setFixedWidth(115)
        self.to_combo.view().setMinimumWidth(115)
        self.to_combo.setMaxVisibleItems(12)

        center_grid.addWidget(self._numbered_box(self.amount_edit), 0, 0)
        center_grid.addWidget(self._numbered_box(self.from_combo, label_text="Из"), 0, 1)
        center_grid.addWidget(self._numbered_box(self.result_label), 1, 0)
        center_grid.addWidget(self._numbered_box(self.to_combo, label_text="В"), 1, 1)
        root.addLayout(center_grid)

        bottom = QHBoxLayout()

        self.load_last_button = QPushButton("Последний\nрасчёт")
        self.load_last_button.clicked.connect(self.load_last_calculation_into_form)
        self.load_last_button.setFixedSize(170, 90)
        bottom.addWidget(self.load_last_button, alignment=Qt.AlignmentFlag.AlignLeft)

        bottom.addStretch()

        self.saved_info_label = QLabel(
            "Дата и курс последнего\nсохранённого расчёта\nбудут показаны здесь"
        )
        self.saved_info_label.setObjectName("boxedLabel")
        self.saved_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.saved_info_label.setMinimumSize(360, 120)
        bottom.addWidget(self.saved_info_label)

        root.addLayout(bottom)

        self.refresh_currency_combos()

    def format_number(self, value: float) -> str:
        if abs(value) >= 1_000_000_000:
            return f"{value:.10g}"

        text = f"{value:.10f}"
        text = text.rstrip("0").rstrip(".")

        if text == "-0":
            text = "0"

        return text

    def _numbered_box(self, widget: QWidget, label_text: str | None = None) -> QWidget:
        container = QFrame()
        container.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if label_text:
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

        layout.addWidget(widget)
        return container

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_currency_combos()
        self.fetch_rates()
        self.update_conversion()

    def get_sorted_currencies(self) -> list[str]:
        favorites = set(StorageService.load_favorites())
        favorite_currencies = [code for code in SUPPORTED_CURRENCIES if code in favorites]
        other_currencies = [code for code in SUPPORTED_CURRENCIES if code not in favorites]
        return favorite_currencies + other_currencies

    def format_currency_label(self, currency_code: str) -> str:
        favorites = set(StorageService.load_favorites())
        prefix = "★ " if currency_code in favorites else ""
        return f"{prefix}{currency_code}"

    def refresh_currency_combos(self) -> None:
        current_from = self.from_combo.currentData() if self.from_combo.count() else "RUB"
        current_to = self.to_combo.currentData() if self.to_combo.count() else "USD"

        currencies = self.get_sorted_currencies()

        self.from_combo.blockSignals(True)
        self.to_combo.blockSignals(True)

        self.from_combo.clear()
        self.to_combo.clear()

        for code in currencies:
            label = self.format_currency_label(code)
            self.from_combo.addItem(label, code)
            self.to_combo.addItem(label, code)

        from_index = self.from_combo.findData(current_from)
        to_index = self.to_combo.findData(current_to)

        if from_index >= 0:
            self.from_combo.setCurrentIndex(from_index)
        else:
            default_from_index = self.from_combo.findData("RUB")
            if default_from_index >= 0:
                self.from_combo.setCurrentIndex(default_from_index)

        if to_index >= 0:
            self.to_combo.setCurrentIndex(to_index)
        else:
            default_to_index = self.to_combo.findData("USD")
            if default_to_index >= 0:
                self.to_combo.setCurrentIndex(default_to_index)

        self.from_combo.blockSignals(False)
        self.to_combo.blockSignals(False)

    def fetch_rates(self) -> None:
        try:
            self.current_rates = RateService.get_rates()
        except Exception as error:
            self.current_rates = None
            QMessageBox.warning(self, "Ошибка", f"Не удалось получить курсы:\n{error}")

    def update_conversion(self) -> None:
        if not self.current_rates:
            self.result_label.setText("Нет данных о курсах")
            return

        amount_text = self.amount_edit.text().strip().replace(",", ".")

        if not amount_text:
            self.result_label.setText("Результат появится здесь")
            return

        try:
            amount = float(amount_text)
            if amount <= 0:
                self.result_label.setText("Сумма должна быть больше 0")
                return
        except ValueError:
            self.result_label.setText("Введите корректное число")
            return

        from_currency = self.from_combo.currentData()
        to_currency = self.to_combo.currentData()

        if not from_currency or not to_currency:
            self.result_label.setText("Выберите валюты")
            return

        rub_value = amount * self.current_rates[from_currency]
        result = rub_value / self.current_rates[to_currency]

        self.last_calculation_data = {
            "date": datetime.now().strftime("%d.%m.%Y"),
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount,
            "result": result,
            "rate_snapshot": self.current_rates[from_currency] / self.current_rates[to_currency],
        }

        amount_display = self.format_number(amount)
        result_display = self.format_number(result)

        self.result_label.setText(
            f"{amount_display} {from_currency} = {result_display} {to_currency}"
        )

    def save_current_calculation(self) -> None:
        if not self.last_calculation_data:
            QMessageBox.information(self, "Сохранение", "Сначала выполните конвертацию.")
            return

        try:
            StorageService.save_last_calculation(self.last_calculation_data)
            QMessageBox.information(self, "Сохранение", "Последний расчёт сохранён.")
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить расчёт:\n{error}")

    def load_last_calculation_into_form(self) -> None:
        try:
            data = StorageService.load_last_calculation()
        except FileNotFoundError:
            QMessageBox.information(self, "Последний расчёт", "Сохранённый расчёт пока не найден.")
            return
        except Exception as error:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить расчёт:\n{error}")
            return

        self.amount_edit.setText(str(data.get("amount", "")))
        self.refresh_currency_combos()

        from_currency = data.get("from_currency", "RUB")
        to_currency = data.get("to_currency", "USD")

        from_index = self.from_combo.findData(from_currency)
        to_index = self.to_combo.findData(to_currency)

        if from_index >= 0:
            self.from_combo.setCurrentIndex(from_index)

        if to_index >= 0:
            self.to_combo.setCurrentIndex(to_index)

        saved_result = data.get("result")
        amount = data.get("amount", "")
        date = data.get("date", "")
        rate_snapshot = data.get("rate_snapshot")

        rate_text = (
            f"Курс: 1 {from_currency} = "
            f"{self.format_number(rate_snapshot)} {to_currency}"
            if isinstance(rate_snapshot, (int, float))
            else "Курс при сохранении: нет данных"
        )

        amount_text = (
            self.format_number(amount) if isinstance(amount, (int, float)) else str(amount)
        )

        saved_result_text = (
            self.format_number(saved_result)
            if isinstance(saved_result, (int, float))
            else str(saved_result)
        )

        self.result_label.setText(
            f"{amount_text} {from_currency} = {saved_result_text} {to_currency}"
        )

        self.saved_info_label.setText(
            f"Дата сохранения: {date}\n"
            f"Введено: {amount_text} {from_currency}\n"
            f"Получено: {saved_result_text} {to_currency}\n"
            f"{rate_text}"
        )

    def refresh_saved_info_box(self) -> None:
        try:
            data = StorageService.load_last_calculation()
        except FileNotFoundError:
            self.saved_info_label.setText("Сохранённый расчёт пока отсутствует")
            return
        except Exception as error:
            self.saved_info_label.setText(f"Ошибка чтения:\n{error}")
            return

        date = data.get("date", "неизвестно")
        from_currency = data.get("from_currency", "?")
        to_currency = data.get("to_currency", "?")
        amount = data.get("amount", "?")
        result = data.get("result", "?")

        amount_text = (
            self.format_number(amount) if isinstance(amount, (int, float)) else str(amount)
        )

        result_text = (
            self.format_number(result) if isinstance(result, (int, float)) else str(result)
        )

        self.saved_info_label.setText(
            f"Дата: {date}\n{amount_text} {from_currency} = {result_text} {to_currency}"
        )


class HelpPage(QWidget):
    def __init__(self, go_back):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(80, 40, 80, 40)
        root.setSpacing(18)

        header = QGridLayout()
        header.setHorizontalSpacing(0)
        header.setContentsMargins(0, 0, 0, 0)
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 1)
        header.setColumnStretch(2, 1)

        title = QLabel("Помощь")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("pageTitle")
        title.setFixedSize(220, 86)
        header.addWidget(title, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(go_back)
        back_button.setFixedSize(140, 50)
        header.addWidget(
            back_button,
            0,
            2,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )

        root.addLayout(header)
        root.addSpacing(18)

        info = QLabel(
            "Как пользоваться конвертером\n\n"
            "1. Нажмите «Начать конвертацию».\n"
            "2. Введите сумму для перевода.\n"
            "3. Выберите валюту, из которой нужно перевести.\n"
            "4. Выберите валюту, в которую нужно перевести.\n"
            "5. Результат появится автоматически.\n"
            "6. При необходимости сохраните расчёт или загрузите последний сохранённый расчёт.\n"
            "7. В разделе «Избранные валюты» можно отметить нужные валюты звёздочкой."
        )

        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        info.setFrameShape(QFrame.Shape.Box)
        info.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(info)


class FavoritesPage(QWidget, CurrencyMixin):
    def __init__(self, go_back):
        super().__init__()
        self.go_back = go_back
        self.favorites = set(StorageService.load_favorites())

        root = QVBoxLayout(self)
        root.setContentsMargins(80, 40, 80, 40)
        root.setSpacing(18)

        header = QGridLayout()
        header.setContentsMargins(-12, 0, 0, 0)
        header.setHorizontalSpacing(0)
        header.setColumnStretch(0, 1)
        header.setColumnStretch(1, 1)
        header.setColumnStretch(2, 1)

        title = QLabel("Избранное")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("pageTitle")
        title.setFixedSize(220, 86)
        header.addWidget(title, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(go_back)
        back_button.setFixedSize(140, 50)
        header.addWidget(
            back_button,
            0,
            2,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )

        root.addLayout(header)
        root.addSpacing(18)

        self.info_label = QLabel("Выберите валюту и отметьте её звёздочкой")
        self.info_label.setObjectName("boxedLabel")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setFrameShape(QFrame.Shape.Box)
        self.info_label.setFixedHeight(70)
        self.info_label.setMaximumWidth(520)
        root.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        selector_layout = QHBoxLayout()
        selector_layout.setSpacing(16)

        self.currency_combo = QComboBox()
        self.currency_combo.setMinimumHeight(56)
        self.currency_combo.setMinimumWidth(340)
        self.currency_combo.currentIndexChanged.connect(self.update_star_state)
        selector_layout.addWidget(self.currency_combo)

        self.star_button = QPushButton("★")
        self.star_button.setCheckable(True)
        self.star_button.setFixedSize(70, 56)
        self.star_button.clicked.connect(self.toggle_favorite)
        selector_layout.addWidget(self.star_button)

        selector_container = QWidget()
        selector_container.setLayout(selector_layout)
        root.addWidget(selector_container, alignment=Qt.AlignmentFlag.AlignHCenter)

        favorites_title = QLabel("Избранные валюты:")
        favorites_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(favorites_title, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.favorites_list = QListWidget()
        self.favorites_list.setObjectName("favoritesList")
        self.favorites_list.setFixedSize(460, 180)
        self.favorites_list.setMaximumWidth(460)
        self.favorites_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.favorites_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        root.addWidget(self.favorites_list, alignment=Qt.AlignmentFlag.AlignHCenter)

        root.addStretch()

        self.refresh_currency_selector()
        self.update_star_state()
        self.refresh_favorites_label()

    def showEvent(self, event):
        super().showEvent(event)
        self.favorites = set(StorageService.load_favorites())
        self.refresh_currency_selector()
        self.update_star_state()
        self.refresh_favorites_label()

    def refresh_currency_selector(self) -> None:
        current_currency = self.currency_combo.currentData() if self.currency_combo.count() else "RUB"

        self.currency_combo.blockSignals(True)
        self.currency_combo.clear()

        for code in SUPPORTED_CURRENCIES:
            self.currency_combo.addItem(
                self.format_currency_display(code),
                code
            )

        index = self.currency_combo.findData(current_currency)

        if index >= 0:
            self.currency_combo.setCurrentIndex(index)
        else:
            self.currency_combo.setCurrentIndex(0)

        self.currency_combo.blockSignals(False)

    def toggle_favorite(self) -> None:
        currency = self.currency_combo.currentData()

        if not currency:
            return

        if currency in self.favorites:
            self.favorites.remove(currency)
        else:
            self.favorites.add(currency)

        StorageService.save_favorites(sorted(self.favorites))
        self.update_star_state()
        self.refresh_favorites_label()

        window = self.window()
        if hasattr(window, "conversion_page"):
            window.conversion_page.refresh_currency_combos()
            window.conversion_page.update_conversion()

    def update_star_state(self) -> None:
        currency = self.currency_combo.currentData()

        if not currency:
            self.info_label.setText("Выберите валюту")
            self.star_button.setChecked(False)
            return

        is_favorite = currency in self.favorites
        self.star_button.setChecked(is_favorite)

        display_text = self.format_currency_display(currency)

        if is_favorite:
            self.star_button.setStyleSheet(
                """
                QPushButton {
                    border: 2px solid black;
                    background: yellow;
                    color: black;
                    font-size: 28px;
                    font-weight: bold;
                }
                """
            )
            self.info_label.setText(f"{display_text} добавлена в избранное")
        else:
            self.star_button.setStyleSheet(
                """
                QPushButton {
                    border: 2px solid black;
                    background: white;
                    color: black;
                    font-size: 28px;
                    font-weight: bold;
                }
                """
            )
            self.info_label.setText(f"{display_text} не в избранном")

    def refresh_favorites_label(self) -> None:
        self.favorites_list.clear()

        if not self.favorites:
            self.favorites_list.addItem("Избранных валют пока нет")
            return

        for currency in sorted(self.favorites):
            self.favorites_list.addItem(
                self.format_currency_display(currency, with_star=True)
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Конвертер валют")
        self.setFixedSize(760, 580)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.menu_page = MenuPage(
            open_converter=self.open_converter,
            open_help=self.open_help,
            open_favorites=self.open_favorites,
            exit_app=self.close,
        )

        self.conversion_page = ConversionPage(go_back=self.open_menu)
        self.help_page = HelpPage(go_back=self.open_menu)
        self.favorites_page = FavoritesPage(go_back=self.open_menu)

        self.stack.addWidget(self.menu_page)
        self.stack.addWidget(self.conversion_page)
        self.stack.addWidget(self.favorites_page)
        self.stack.addWidget(self.help_page)

        self.open_menu()
        self.apply_styles()

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f2f2f2;
                font-size: 18px;
                color: black;
            }
            QPushButton, QComboBox, QLineEdit {
                border: 2px solid black;
                padding: 8px;
                background: white;
                color: black;
            }
            QLabel#pageTitle {
                border: none;
                font-size: 22px;
                font-weight: 600;
                background: white;
                color: black;
            }
            QLabel#boxedLabel {
                background: white;
                color: black;
                border: none;
                padding: 8px;
            }
            QLabel#smallBadge {
                border: none;
                font-size: 16px;
                font-weight: 600;
                background: transparent;
                color: black;
            }
            QLabel {
                background: transparent;
                color: black;
            }
            QFrame {
                background: transparent;
                color: black;
            }
            QListWidget#favoritesList {
                background: white;
                color: black;
                border: 2px solid black;
                padding: 8px;
            }
            QListWidget#favoritesList::item {
                padding: 4px;
            }
            QMenuBar {
                background: #f2f2f2;
                color: black;
            }
            QMenuBar::item {
                background: #f2f2f2;
                color: black;
            }
            QMenuBar::item:selected {
                background: #dcdcdc;
                color: black;
            }
            QMenu {
                background: white;
                color: black;
                border: 1px solid black;
            }
            QMenu::item:selected {
                background: #dcdcdc;
                color: black;
            }
            """
        )

    def open_menu(self) -> None:
        self.stack.setCurrentWidget(self.menu_page)

    def open_converter(self) -> None:
        self.conversion_page.refresh_currency_combos()
        self.stack.setCurrentWidget(self.conversion_page)

    def open_help(self) -> None:
        self.stack.setCurrentWidget(self.help_page)

    def open_favorites(self) -> None:
        self.favorites_page.refresh_currency_selector()
        self.favorites_page.refresh_favorites_label()
        self.favorites_page.update_star_state()
        self.stack.setCurrentWidget(self.favorites_page)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
