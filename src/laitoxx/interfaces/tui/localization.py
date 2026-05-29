"""Small localization layer for the Textual interface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SUPPORTED_LANGUAGES = ("en", "ru")

_EN: dict[str, Any] = {
    "brand": "LAITOXX\nOSINT CONSOLE",
    "filter_placeholder": "Filter tools...",
    "tools_root": "Tools",
    "details_empty": "Select a tool to see details.",
    "ready": "Ready",
    "output_title": " Output ",
    "no_matching_tools": "No matching tools.",
    "category": "Category",
    "type": "Type",
    "no_description": "No description.",
    "welcome_phone": (
        "Phone mode: f filter | Esc menu | o output | Enter run | comma settings | q quit."
    ),
    "welcome_desktop": "Use / to filter, arrows to move, Enter or r to run, s to save a report.",
    "plugins_reloaded": "Plugins reloaded",
    "settings_saved": "Settings saved",
    "tool_already_running": "A tool is already running",
    "no_tool_selected": "No tool selected",
    "cancelled": "Cancelled",
    "run_worker": "Run {name}",
    "running_tool": "Running {name}...",
    "tool_completed": "{name} completed",
    "tool_failed": "{name} failed",
    "done": "Done.",
    "no_result_to_save": "No result to save",
    "report": "Report",
    "report_saved": "Report saved: {path}",
    "open_report": "Open report",
    "leak_report_title": "LeakOSINT HTML report",
    "leak_report_saved": "LeakOSINT report saved: {path}",
    "lua_plugins": "Lua Plugins",
    "community_indexes": "Community indexes",
    "download_all": "Download all",
    "download": "Download",
    "unknown": "Unknown",
    "cancel": "Cancel",
    "close": "Close",
    "save": "Save",
    "run": "Run",
    "browse": "Browse",
    "use_folder": "Use folder",
    "select_file": "Select file",
    "select_folder": "Select folder",
    "settings": "Settings",
    "tui_theme": "TUI theme",
    "theme": "Theme",
    "language": "Language",
    "language_en": "English",
    "language_ru": "Russian",
    "proxy": "Proxy",
    "enable_proxy": "Enable proxy",
    "proxy_type": "Proxy type",
    "proxy_host": "Proxy host",
    "proxy_port": "Proxy port",
    "proxy_username": "Proxy username",
    "proxy_password": "Proxy password",
    "optional": "optional",
    "preparing_download": "Preparing download",
    "preparing_download_count": "Preparing download: {count} index(es)",
    "waiting_for_data": "Waiting for data...",
    "downloading_index": "Downloading community index...",
    "download_failed": "Download failed",
    "download_cancelled": "Download cancelled",
    "download_completed": "Download completed",
    "download_cancel_status": "Cancelling community index download...",
    "download_cancel_title": "Cancelling download...",
    "download_title": "Downloading {position}/{count}: {repo_id}",
    "unpacking_title": "Unpacking {position}/{count}: {repo_id}",
    "installing_downloaded_index": "Installing downloaded index",
    "extracting_index": "Extracting downloaded index",
    "installing_index": "Installing",
    "cancellation_unavailable": "cancellation is unavailable",
    "downloading_unknown_size": "Downloading files; size is unavailable",
    "remaining": "remaining",
    "photo_title_netryx": "Preparing Netryx Photo geolocation",
    "photo_title_geoclip": "Preparing PlaNet-like global model",
    "photo_title_hub_search": "Searching community indexes",
    "photo_title_index_io": "Preparing index operation",
    "worker_running": "Worker process is running...",
    "completed": "Completed.",
    "stopped_error": "Stopped with an error.",
    "photo_completed": "Photo geolocation completed",
    "photo_failed": "Photo geolocation failed",
    "photo_download_failed": "Photo geolocation download failed",
    "local_index_area": ("Area: {lat}, {lon} | radius {radius} km | grid {grid}"),
    "preparing_local_index": "Preparing local visual index",
    "street_view_scan_start": "Starting Street View coverage scan...",
    "local_index_cancel_status": "Cancelling local index creation...",
    "local_index_cancel_title": "Cancelling index creation...",
    "local_index_cancelled": "Local index creation cancelled",
    "index_creation_cancelled": "Index creation cancelled",
    "local_index_ready": "Local index ready",
    "index_creation_failed": "Index creation failed",
    "scan_coverage": "Scanning Street View coverage",
    "download_extract_descriptors": "Downloading views and extracting descriptors",
    "building_index": "Building compact visual index",
    "fitting_index": "Fitting PCA and saving index",
    "index_created": "Index created",
    "preparing_index_creation": "Preparing index creation",
    "categories": {
        "information_gathering": "Info",
        "web_security": "Web",
        "utils": "Utils",
    },
}

_RU: dict[str, Any] = {
    "brand": "LAITOXX\nOSINT КОНСОЛЬ",
    "filter_placeholder": "Фильтр инструментов...",
    "tools_root": "Инструменты",
    "details_empty": "Выберите инструмент, чтобы увидеть описание.",
    "ready": "Готово",
    "output_title": " Вывод ",
    "no_matching_tools": "Подходящих инструментов нет.",
    "category": "Категория",
    "type": "Тип",
    "no_description": "Описание отсутствует.",
    "welcome_phone": (
        "Режим телефона: f фильтр | Esc меню | o вывод | Enter запуск | , настройки | q выход."
    ),
    "welcome_desktop": "Используйте / для фильтра, стрелки для выбора, Enter или r для запуска, s для отчета.",
    "plugins_reloaded": "Плагины перезагружены",
    "settings_saved": "Настройки сохранены",
    "tool_already_running": "Инструмент уже выполняется",
    "no_tool_selected": "Инструмент не выбран",
    "cancelled": "Отменено",
    "run_worker": "Запуск {name}",
    "running_tool": "Выполняется {name}...",
    "tool_completed": "{name} завершен",
    "tool_failed": "{name} завершился ошибкой",
    "done": "Готово.",
    "no_result_to_save": "Нет результата для сохранения",
    "report": "Отчет",
    "report_saved": "Отчет сохранен: {path}",
    "open_report": "Открыть отчет",
    "leak_report_title": "HTML-отчет LeakOSINT",
    "leak_report_saved": "Отчет LeakOSINT сохранен: {path}",
    "lua_plugins": "Lua-плагины",
    "community_indexes": "Индексы сообщества",
    "download_all": "Скачать все",
    "download": "Скачать",
    "unknown": "Неизвестно",
    "cancel": "Отмена",
    "close": "Закрыть",
    "save": "Сохранить",
    "run": "Запустить",
    "browse": "Обзор",
    "use_folder": "Выбрать папку",
    "select_file": "Выберите файл",
    "select_folder": "Выберите папку",
    "settings": "Настройки",
    "tui_theme": "Тема TUI",
    "theme": "Тема",
    "language": "Язык",
    "language_en": "Английский",
    "language_ru": "Русский",
    "proxy": "Прокси",
    "enable_proxy": "Включить прокси",
    "proxy_type": "Тип прокси",
    "proxy_host": "Хост прокси",
    "proxy_port": "Порт прокси",
    "proxy_username": "Логин прокси",
    "proxy_password": "Пароль прокси",
    "optional": "необязательно",
    "preparing_download": "Подготовка скачивания",
    "preparing_download_count": "Подготовка скачивания: {count} индекс(ов)",
    "waiting_for_data": "Ожидание данных...",
    "downloading_index": "Скачивание индекса сообщества...",
    "download_failed": "Скачивание не удалось",
    "download_cancelled": "Скачивание отменено",
    "download_completed": "Скачивание завершено",
    "download_cancel_status": "Отмена скачивания индекса сообщества...",
    "download_cancel_title": "Отмена скачивания...",
    "download_title": "Скачивание {position}/{count}: {repo_id}",
    "unpacking_title": "Распаковка {position}/{count}: {repo_id}",
    "installing_downloaded_index": "Установка скачанного индекса",
    "extracting_index": "Распаковка скачанного индекса",
    "installing_index": "Установка",
    "cancellation_unavailable": "отмена недоступна",
    "downloading_unknown_size": "Скачивание файлов; размер неизвестен",
    "remaining": "осталось",
    "photo_title_netryx": "Подготовка Netryx Photo geolocation",
    "photo_title_geoclip": "Подготовка глобальной модели PlaNet-like",
    "photo_title_hub_search": "Поиск индексов сообщества",
    "photo_title_index_io": "Подготовка операции с индексом",
    "worker_running": "Рабочий процесс выполняется...",
    "completed": "Завершено.",
    "stopped_error": "Остановлено с ошибкой.",
    "photo_completed": "Геолокация фото завершена",
    "photo_failed": "Геолокация фото завершилась ошибкой",
    "photo_download_failed": "Скачивание для геолокации фото не удалось",
    "local_index_area": ("Область: {lat}, {lon} | радиус {radius} км | сетка {grid}"),
    "preparing_local_index": "Подготовка локального визуального индекса",
    "street_view_scan_start": "Запуск сканирования покрытия Street View...",
    "local_index_cancel_status": "Отмена создания локального индекса...",
    "local_index_cancel_title": "Отмена создания индекса...",
    "local_index_cancelled": "Создание локального индекса отменено",
    "index_creation_cancelled": "Создание индекса отменено",
    "local_index_ready": "Локальный индекс готов",
    "index_creation_failed": "Создание индекса не удалось",
    "scan_coverage": "Сканирование покрытия Street View",
    "download_extract_descriptors": "Скачивание видов и извлечение дескрипторов",
    "building_index": "Сборка компактного визуального индекса",
    "fitting_index": "Расчет PCA и сохранение индекса",
    "index_created": "Индекс создан",
    "preparing_index_creation": "Подготовка создания индекса",
    "categories": {
        "information_gathering": "Информация",
        "web_security": "Веб",
        "utils": "Утилиты",
    },
    "tools": {
        "Check Phone Number": "Проверка телефона",
        "Check IP": "Проверка IP",
        "Validate Email": "Проверка Email",
        "Data Search": "Поиск данных",
        "Info Website": "Информация о сайте",
        "Gmail Osint": "Gmail OSINT",
        "Database search": "Поиск по базам",
        "Check MAC-address": "Проверка MAC-адреса",
        "Subdomain finder": "Поиск субдоменов",
        "Google Osint": "Google OSINT",
        "Telegram (paketlib)": "Telegram (paketlib)",
        "Search Nick": "OSINT по никнейму",
        "Web-crawler": "Веб-краулер",
        "Port Scanner": "Сканер портов",
        "HTTP Inspector": "HTTP-инспектор",
        "Tech Detector": "Детектор технологий",
        "CMS Audit": "Аудит CMS",
        "JWT Analyzer": "Анализ JWT",
        "CIDR Calculator": "CIDR-калькулятор",
        "Text Hasher": "Хеширование текста",
        "Hash Identifier": "Определение хеша",
        "Rainbow Table Generator": "Генератор rainbow-таблиц",
        "Password Generator": "Генератор паролей",
        "Text Transformer": "Преобразование текста",
        "Regex Tester": "Тест regex",
        "Image Search": "Поиск изображений",
        "Photo geolocation": "Геолокация фото",
    },
}


def normalize_language(language: str | None) -> str:
    """Return a supported language code."""
    return language if language in SUPPORTED_LANGUAGES else "en"


class TuiTranslator:
    """Translate stable TUI keys without changing internal tool identifiers."""

    def __init__(self, language: str | None = "en") -> None:
        self.language = normalize_language(language)

    def set_language(self, language: str | None) -> None:
        self.language = normalize_language(language)

    def t(self, key: str, **kwargs: Any) -> str:
        value = self._lookup(key)
        if not isinstance(value, str):
            return key
        return value.format(**kwargs)

    def category(self, key: str) -> str:
        categories = self._lookup("categories")
        if isinstance(categories, Mapping):
            value = categories.get(key)
            if isinstance(value, str):
                return value
        return key

    def tool_name(self, name: str) -> str:
        tools = self._lookup("tools")
        if isinstance(tools, Mapping):
            value = tools.get(name)
            if isinstance(value, str):
                return value
        return name

    def _lookup(self, key: str) -> Any:
        current = _RU if self.language == "ru" else _EN
        fallback = _EN
        return current.get(key, fallback.get(key, key))
