"""Form definitions and input adapters for TUI tools."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterable
from typing import Any

from .localization import normalize_language
from .models import Field, ToolItem

MAX_RAINBOW_CHAIN_LENGTH = 2_000
MAX_RAINBOW_CHAINS = 5_000
MAX_RAINBOW_OPERATIONS = 2_000_000
MAX_RAINBOW_PASSWORD_LENGTH = 12
MAX_RAINBOW_SALT_LENGTH = 64
MAX_RAINBOW_CHARSET_LENGTH = 128


class ToolFormFactory:
    """Build Textual form fields and convert submitted values for tools."""

    def __init__(self, language: str | None = "en") -> None:
        self.language = normalize_language(language)

    def set_language(self, language: str | None) -> None:
        self.language = normalize_language(language)

    def _tr(self, text: str) -> str:
        if self.language != "ru":
            return text
        return _RU_FIELD_LABELS.get(text, text)

    def _field(self, name: str, label: str, *args: Any, **kwargs: Any) -> Field:
        return Field(name, self._tr(label), *args, **kwargs)

    def _options(self, items: Iterable[tuple[str, Any]]) -> tuple[tuple[str, Any], ...]:
        return tuple((self._tr(label), value) for label, value in items)

    def fields_for_item(self, item: ToolItem, data: dict[str, Any] | None = None) -> list[Field]:
        if item.plugin is not None:
            label = self._tr("Data" if item.plugin.plugin_type == "processor" else "Query")
            return [Field("query", label, "textarea")]

        spec = item.spec
        if spec is None or spec.input_type is None:
            return []

        name = item.name
        input_type = spec.input_type
        if input_type == "text":
            return self._text_fields(name, spec.prompt)
        if input_type == "telegram":
            return self._telegram_fields()
        if input_type == "google_osint":
            return self._google_osint_fields()
        if input_type == "username_osint_dialog":
            return [self._field("username", "Username or nickname")]
        if input_type == "hash":
            return self._hash_fields(name)
        if input_type == "jwt":
            return self._jwt_fields()
        if input_type == "nmap":
            return self._nmap_fields()
        if input_type == "web_security":
            return self._web_security_fields()
        if input_type == "text_transformer":
            return self._text_transformer_fields()
        if input_type == "password_gen":
            return self._password_fields()
        if input_type == "regex":
            return self._regex_fields()
        if input_type == "cidr":
            return self._cidr_fields()
        if input_type == "image_search":
            return self._image_search_fields()
        if input_type == "photo2geo":
            return self._photo2geo_fields(
                str((data or {}).get("task") or "check_setup"),
                str((data or {}).get("engine") or "netryx"),
            )
        return [self._field("value", spec.prompt or "Input")]

    def build_input(self, item: ToolItem, data: dict[str, Any]) -> Any:
        if item.plugin is not None:
            return data.get("query", "")

        spec = item.spec
        if spec is None or spec.input_type is None:
            return None

        input_type = spec.input_type
        if input_type == "text":
            return self._build_text_input(item.name, data)
        if input_type == "hash":
            return self._build_hash_input(item.name, data)
        if input_type == "telegram":
            return {"method": data.get("method"), "query": data.get("query", "")}
        if input_type == "google_osint":
            return {"query": data.get("query", ""), "engines": data.get("engines") or ["google"]}
        if input_type == "username_osint_dialog":
            return {"username": data.get("username", "")}
        if input_type == "jwt":
            return {
                "mode": data.get("mode", "analyze"),
                "token": data.get("token", ""),
                "wordlist": data.get("wordlist", ""),
            }
        if input_type == "nmap":
            return {
                "target": data.get("target", ""),
                "ports": data.get("ports", "1-1024"),
                "profile": data.get("profile", "quick"),
            }
        if input_type == "web_security":
            return {"check": data.get("check", "all"), "url": data.get("url", "")}
        if input_type == "text_transformer":
            return {
                "mode": data.get("mode", ""),
                "action": data.get("action", "encode"),
                "shift": self._to_int(data.get("shift"), 3),
                "text": data.get("text", ""),
            }
        if input_type == "password_gen":
            return self._build_password_input(data)
        if input_type == "regex":
            return {
                "pattern": data.get("pattern", ""),
                "text": data.get("text", ""),
                "flags": data.get("flags", []),
            }
        if input_type == "cidr":
            return {
                "cidr": data.get("cidr", ""),
                "check_ip": data.get("check_ip", ""),
                "subnet_count": self._to_int(data.get("subnet_count"), 0),
            }
        if input_type == "image_search":
            return {
                "file_path": data.get("file_path", ""),
                "search_engines": data.get("search_engines", []),
            }
        if input_type == "photo2geo":
            return self._build_photo2geo_input(data)
        return data.get("value", "")

    def _text_fields(self, name: str, prompt: str | None) -> list[Field]:
        if name == "Subdomain finder":
            return [
                self._field("value", prompt or "Domain"),
                self._field("save", "Save to file", "bool", False),
            ]
        if name == "Web-crawler":
            return [
                self._field("value", prompt or "Start URL"),
                self._field("max_pages", "Max pages", "text", "20"),
                self._field("save", "Save crawled pages", "bool", False),
            ]
        return [self._field("value", prompt or "Value")]

    def _telegram_fields(self) -> list[Field]:
        return [
            Field(
                "method",
                self._tr("Search type"),
                "select",
                "TelegramUsername",
                self._options(
                    [
                        ("Username", "TelegramUsername"),
                        ("Channel", "TelegramChannel"),
                        ("Chat", "TelegramChat"),
                        ("Parse channel", "TelegramCParser"),
                        ("Telegram ID", "TelegramID"),
                    ]
                ),
            ),
            self._field("query", "Query / @username"),
        ]

    def _google_osint_fields(self) -> list[Field]:
        return [
            self._field("query", "Dork query", "textarea"),
            Field(
                "engines",
                self._tr("Search engines"),
                "multi",
                options=self._options(
                    [
                        ("Google", "google"),
                        ("Bing", "bing"),
                        ("DuckDuckGo", "duckduckgo"),
                        ("Yandex", "yandex"),
                    ]
                ),
                enabled=("google",),
            ),
        ]

    def _hash_fields(self, name: str) -> list[Field]:
        if name == "Text Hasher":
            return [self._field("text", "Text to hash"), self._algorithm_field("sha256")]
        if name == "Hash Identifier":
            return [self._field("hash", "Hash string")]
        return [
            self._field("charset", "Charset", default="abcdefghijklmnopqrstuvwxyz0123456789"),
            self._algorithm_field("md5"),
            self._field("chain_length", "Chain length", default="500"),
            self._field("num_chains", "Number of chains", default="1000"),
            self._field("password_len", "Password length", default="6"),
            self._field("output_file", "Output CSV file", default="rainbow_table.csv"),
            self._field("use_salt", "Use salt", "bool", False),
            self._field("salt_length", "Salt length", default="8"),
        ]

    def _jwt_fields(self) -> list[Field]:
        return [
            Field(
                "mode",
                self._tr("Mode"),
                "select",
                "analyze",
                self._options([("Analyze", "analyze"), ("Crack", "crack")]),
            ),
            self._field("token", "JWT token", "textarea"),
            self._field("wordlist", "Wordlist path"),
        ]

    def _nmap_fields(self) -> list[Field]:
        return [
            self._field("target", "Target host/IP/network"),
            self._field("ports", "Ports", default="1-1024"),
            Field(
                "profile",
                self._tr("Profile"),
                "select",
                "quick",
                self._options(
                    [
                        ("Quick service scan", "quick"),
                        ("Top 100 ports", "top100"),
                        ("Service + default scripts", "service"),
                        ("Ping discovery", "ping"),
                    ]
                ),
            ),
        ]

    def _web_security_fields(self) -> list[Field]:
        return [
            Field(
                "check",
                self._tr("Check"),
                "select",
                "all",
                self._options(
                    [
                        ("All checks", "all"),
                        ("SSL/TLS", "ssl"),
                        ("CORS", "cors"),
                        ("Open Redirect", "redirect"),
                        ("Security Headers", "headers"),
                    ]
                ),
            ),
            self._field("url", "Target URL"),
        ]

    def _text_transformer_fields(self) -> list[Field]:
        return [
            Field(
                "mode",
                self._tr("Mode"),
                "select",
                "base64",
                self._options(
                    [
                        ("leet", "leet"),
                        ("morse", "morse"),
                        ("binary", "binary"),
                        ("hex", "hex"),
                        ("rot13", "rot13"),
                        ("caesar", "caesar"),
                        ("base64", "base64"),
                        ("url", "url"),
                        ("reverse", "reverse"),
                        ("upper", "upper"),
                        ("lower", "lower"),
                    ]
                ),
            ),
            Field(
                "action",
                self._tr("Action"),
                "select",
                "encode",
                self._options([("Encode", "encode"), ("Decode", "decode")]),
            ),
            self._field("shift", "Caesar shift", default="3"),
            self._field("text", "Text", "textarea"),
        ]

    def _password_fields(self) -> list[Field]:
        return [
            self._field("length", "Length", default="16"),
            self._field("count", "Count", default="1"),
            self._field("use_upper", "Include uppercase", "bool", True),
            self._field("use_lower", "Include lowercase", "bool", True),
            self._field("use_digits", "Include digits", "bool", True),
            self._field("use_symbols", "Include symbols", "bool", True),
            self._field("custom_chars", "Only these chars"),
            self._field("exclude_chars", "Exclude chars"),
        ]

    def _regex_fields(self) -> list[Field]:
        return [
            self._field("pattern", "Regex pattern"),
            Field(
                "flags",
                self._tr("Flags"),
                "multi",
                options=self._options(
                    [
                        ("IGNORECASE", "IGNORECASE"),
                        ("MULTILINE", "MULTILINE"),
                        ("DOTALL", "DOTALL"),
                        ("VERBOSE", "VERBOSE"),
                        ("ASCII", "ASCII"),
                    ]
                ),
            ),
            self._field("text", "Test text", "textarea"),
        ]

    def _cidr_fields(self) -> list[Field]:
        return [
            self._field("cidr", "CIDR"),
            self._field("check_ip", "Check IP in range"),
            self._field("subnet_count", "Split into N subnets", default="0"),
        ]

    def _image_search_fields(self) -> list[Field]:
        return [
            self._field("file_path", "Image file", "file"),
            Field(
                "search_engines",
                self._tr("Engines"),
                "multi",
                options=self._options(
                    [
                        ("Yandex", "Yandex"),
                        ("Google Lens", "Google Lens"),
                        ("Bing", "Bing"),
                        ("TinEye", "TinEye"),
                        ("SauceNao", "SauceNao"),
                        ("IQDB", "IQDB"),
                        ("Ascii2D", "Ascii2D"),
                        ("TraceMoe", "TraceMoe"),
                        ("Baidu", "Baidu"),
                        ("Sogou", "Sogou"),
                    ]
                ),
            ),
        ]

    def _photo2geo_fields(self, task: str = "check_setup", engine: str = "netryx") -> list[Field]:
        engine = "geoclip" if str(engine).lower() in {"geoclip", "planet"} else "netryx"
        engine_field = Field(
            "engine",
            self._tr("Geolocation mode"),
            "select",
            engine,
            self._options(
                [
                    ("Netryx Astra local index", "netryx"),
                    ("GeoCLIP / PlaNet-like global", "geoclip"),
                ]
            ),
        )
        if engine == "geoclip":
            if task not in {"check_setup", "find_photo"}:
                task = "check_setup"
            task_field = Field(
                "task",
                self._tr("What do you want to do?"),
                "select",
                task,
                self._options(
                    [
                        ("Check setup", "check_setup"),
                        ("Find photo location", "find_photo"),
                    ]
                ),
            )
            task_fields: dict[str, list[Field]] = {
                "check_setup": [],
                "find_photo": [
                    self._field("target", "Photo file", "file"),
                    self._field("top_k", "Predictions count", default="5"),
                    Field(
                        "model_device",
                        self._tr("Device"),
                        "select",
                        "auto",
                        self._options(
                            [
                                ("Auto", "auto"),
                                ("CPU", "cpu"),
                                ("CUDA", "cuda"),
                            ]
                        ),
                    ),
                    Field(
                        "precision",
                        self._tr("Precision"),
                        "select",
                        "auto",
                        self._options(
                            [
                                ("Auto", "auto"),
                                ("Float32", "float32"),
                                ("BFloat16", "bfloat16"),
                                ("Float16", "float16"),
                            ]
                        ),
                    ),
                ],
            }
            return [engine_field, task_field, *task_fields.get(task, [])]

        task_field = Field(
            "task",
            self._tr("What do you want to do?"),
            "select",
            task,
            self._options(
                [
                    ("Check setup", "check_setup"),
                    ("Find photo location", "find_photo"),
                    ("Search community indexes", "hub_search"),
                    ("Create local index", "create_index"),
                    ("Import .netryx index", "import_index"),
                    ("Export current index", "export_index"),
                    ("Build compact index", "build_index"),
                ]
            ),
        )
        source_field = self._field("source_path", "Netryx Astra folder (optional)", "directory")
        task_fields: dict[str, list[Field]] = {
            "check_setup": [],
            "find_photo": [
                self._field("target", "Photo file", "file"),
                self._field("location_hint", "Location hint: lat, lon, radius_km"),
                self._field("top_k", "Results count", default="25"),
            ],
            "hub_search": [self._field("target", "City name (optional)")],
            "create_index": [
                self._field("center_lat", "Center latitude"),
                self._field("center_lon", "Center longitude"),
                self._field("radius_km", "Radius (km)", default="1"),
                self._field("grid_resolution", "Grid resolution", default="300"),
                self._field("crop_fov", "Crop field of view", default="90"),
                self._field("crop_size", "Crop size (pixels)", default="256"),
                self._field("crop_step", "Heading step (degrees)", default="90"),
            ],
            "import_index": [self._field("target", ".netryx index file", "file")],
            "export_index": [
                self._field("target", "Output .netryx file path (optional)"),
                self._field("location_hint", "Index center: lat, lon, radius_km"),
            ],
            "build_index": [],
        }
        return [engine_field, task_field, *task_fields.get(task, []), source_field]

    def _build_photo2geo_input(self, data: dict[str, Any]) -> dict[str, Any]:
        task = str(data.get("task") or "check_setup")
        config = {
            "task": task,
            "source_path": data.get("source_path", ""),
        }
        if "engine" in data:
            config["engine"] = data.get("engine", "netryx")
        engine = str(config.get("engine") or "netryx")
        allowed_fields: dict[str, tuple[str, ...]] = {
            "find_photo": ("target", "location_hint", "top_k"),
            "hub_search": ("target",),
            "create_index": (
                "center_lat",
                "center_lon",
                "radius_km",
                "grid_resolution",
                "crop_fov",
                "crop_size",
                "crop_step",
            ),
            "import_index": ("target",),
            "export_index": ("target", "location_hint"),
        }
        if engine == "geoclip":
            allowed_fields = {
                "find_photo": ("target", "top_k", "model_device", "precision"),
            }
        for name in allowed_fields.get(task, ()):
            config[name] = data.get(name, "")
        return config

    def _build_text_input(self, name: str, data: dict[str, Any]) -> Any:
        value = data.get("value", "")
        if name == "Check IP":
            return {"ip": value}
        if name in {"HTTP Inspector", "Tech Detector", "CMS Audit"}:
            return {"url": value}
        if name == "Subdomain finder":
            return [value, "y" if data.get("save") else "n"]
        if name == "Web-crawler":
            return [value, str(data.get("max_pages") or "20"), "y" if data.get("save") else "n"]
        return value

    def _build_hash_input(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        algorithm = self._selected_algorithm(data)
        if name == "Text Hasher":
            return {"text": data.get("text", ""), "algorithm": algorithm}
        if name == "Hash Identifier":
            return {"hash": data.get("hash", "")}
        chain_length = self._bounded_int(
            data.get("chain_length"), 500, minimum=1, maximum=MAX_RAINBOW_CHAIN_LENGTH
        )
        num_chains = self._bounded_int(
            data.get("num_chains"), 1000, minimum=1, maximum=MAX_RAINBOW_CHAINS
        )
        max_chains_for_work = max(1, MAX_RAINBOW_OPERATIONS // chain_length)
        num_chains = min(num_chains, max_chains_for_work)
        return {
            "charset": str(data.get("charset", ""))[:MAX_RAINBOW_CHARSET_LENGTH],
            "algorithm": algorithm,
            "chain_length": chain_length,
            "num_chains": num_chains,
            "password_len": self._bounded_int(
                data.get("password_len"), 6, minimum=1, maximum=MAX_RAINBOW_PASSWORD_LENGTH
            ),
            "output_file": self._safe_output_filename(data.get("output_file", "")),
            "use_salt": bool(data.get("use_salt")),
            "salt_length": self._bounded_int(
                data.get("salt_length"), 8, minimum=1, maximum=MAX_RAINBOW_SALT_LENGTH
            ),
        }

    def _build_password_input(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "length": self._to_int(data.get("length"), 16),
            "count": self._to_int(data.get("count"), 1),
            "use_upper": bool(data.get("use_upper")),
            "use_lower": bool(data.get("use_lower")),
            "use_digits": bool(data.get("use_digits")),
            "use_symbols": bool(data.get("use_symbols")),
            "custom_chars": data.get("custom_chars", ""),
            "exclude_chars": data.get("exclude_chars", ""),
        }

    def _algorithm_field(self, default: str) -> Field:
        common = [
            "sha256",
            "sha512",
            "sha1",
            "md5",
            "sha224",
            "sha384",
            "blake2b",
            "blake2s",
            "sha3_256",
            "sha3_512",
        ]
        available = sorted(str(name).lower() for name in hashlib.algorithms_available)
        ordered = [name for name in common if name in available]
        ordered.extend(name for name in available if name not in ordered)
        return Field(
            "algorithm",
            self._tr("Algorithm"),
            "select",
            default,
            self._options((name, name) for name in ordered),
        )

    @staticmethod
    def _bounded_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
        parsed = ToolFormFactory._to_int(value, default)
        return max(minimum, min(parsed, maximum))

    @staticmethod
    def _safe_output_filename(value: Any) -> str:
        name = os.path.basename(str(value or "rainbow_table.csv").strip())
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", name) or "rainbow_table.csv"
        if not name.lower().endswith(".csv"):
            name = f"{name}.csv"
        return name

    @staticmethod
    def _selected_algorithm(data: dict[str, Any]) -> str:
        return str(data.get("algorithm") or "sha256").strip().lower()

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


_RU_FIELD_LABELS = {
    "Action": "Действие",
    "Algorithm": "Алгоритм",
    "All checks": "Все проверки",
    "Analyze": "Анализ",
    "Auto": "Авто",
    "BFloat16": "BFloat16",
    "Build compact index": "Собрать компактный индекс",
    "Caesar shift": "Сдвиг Цезаря",
    "Center latitude": "Широта центра",
    "Center longitude": "Долгота центра",
    "Chain length": "Длина цепочки",
    "Channel": "Канал",
    "Chat": "Чат",
    "Check": "Проверка",
    "Check IP in range": "Проверить IP в диапазоне",
    "Check setup": "Проверить настройку",
    "City name (optional)": "Город (необязательно)",
    "Count": "Количество",
    "CPU": "CPU",
    "CUDA": "CUDA",
    "Crack": "Взлом",
    "Create local index": "Создать локальный индекс",
    "Crop field of view": "Угол обзора кадра",
    "Crop size (pixels)": "Размер кадра (пиксели)",
    "Data": "Данные",
    "Decode": "Декодировать",
    "Device": "Устройство",
    "Dork query": "Dork-запрос",
    "Encode": "Кодировать",
    "Engines": "Движки",
    "Export current index": "Экспорт текущего индекса",
    "Find photo location": "Найти место фото",
    "Flags": "Флаги",
    "Float16": "Float16",
    "Float32": "Float32",
    "Geolocation mode": "Режим геолокации",
    "Grid resolution": "Разрешение сетки",
    "Hash string": "Строка хеша",
    "Heading step (degrees)": "Шаг направления (градусы)",
    "Image file": "Файл изображения",
    "Import .netryx index": "Импорт .netryx индекса",
    "Include digits": "Добавить цифры",
    "Include lowercase": "Добавить строчные",
    "Include symbols": "Добавить символы",
    "Include uppercase": "Добавить заглавные",
    "Index center: lat, lon, radius_km": "Центр индекса: широта, долгота, радиус_км",
    "Length": "Длина",
    "Location hint: lat, lon, radius_km": "Подсказка места: широта, долгота, радиус_км",
    "Max pages": "Максимум страниц",
    "Mode": "Режим",
    "Netryx Astra folder (optional)": "Папка Netryx Astra (необязательно)",
    "Number of chains": "Количество цепочек",
    "Only these chars": "Только эти символы",
    "Output .netryx file path (optional)": "Путь выходного .netryx файла (необязательно)",
    "Output CSV file": "Выходной CSV-файл",
    "Parse channel": "Парсинг канала",
    "Password length": "Длина пароля",
    "Photo file": "Файл фото",
    "Ports": "Порты",
    "Precision": "Точность",
    "Predictions count": "Количество предсказаний",
    "Profile": "Профиль",
    "Query": "Запрос",
    "Query / @username": "Запрос / @username",
    "Radius (km)": "Радиус (км)",
    "Regex pattern": "Шаблон regex",
    "Results count": "Количество результатов",
    "Save crawled pages": "Сохранить найденные страницы",
    "Save to file": "Сохранить в файл",
    "Search community indexes": "Поиск индексов сообщества",
    "Search engines": "Поисковые движки",
    "Search type": "Тип поиска",
    "Security Headers": "Security Headers",
    "Split into N subnets": "Разделить на N подсетей",
    "Start URL": "Начальный URL",
    "Target host/IP/network": "Хост/IP/сеть",
    "Target URL": "Целевой URL",
    "Telegram ID": "Telegram ID",
    "Test text": "Тестовый текст",
    "Text": "Текст",
    "Text to hash": "Текст для хеширования",
    "Top 100 ports": "Топ-100 портов",
    "Use salt": "Использовать соль",
    "Username": "Имя пользователя",
    "Username or nickname": "Username или никнейм",
    "Value": "Значение",
    "What do you want to do?": "Что нужно сделать?",
    "Wordlist path": "Путь к словарю",
}
