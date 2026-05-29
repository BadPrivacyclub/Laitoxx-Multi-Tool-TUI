from __future__ import annotations

import json
import os

from laitoxx.core.localization.i18n import TRANSLATIONS as LEGACY_TRANSLATIONS
from laitoxx.core.settings.paths import TRANSLATIONS_DIR


def _repair_mojibake(value):
    """Repair strings that were saved as UTF-8 bytes decoded through cp1252."""
    if isinstance(value, str):
        if any(marker in value for marker in ("Ð", "Ñ", "â", "ï¿½", "\x9d")):
            for encoding in ("cp1252", "latin1"):
                try:
                    repaired = value.encode(encoding).decode("utf-8")
                except UnicodeError:
                    continue
                return repaired or value
        return value
    if isinstance(value, dict):
        return {key: _repair_mojibake(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_repair_mojibake(item) for item in value]
    return value


def _load_json_translations() -> dict:
    out: dict[str, dict] = {}
    for lang in ("en", "ru"):
        path = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                out[lang] = _repair_mojibake(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return out


class Translator:
    def __init__(self):
        self.lang = "en"
        merged = {}
        json_translations = _load_json_translations()
        for lang in set(LEGACY_TRANSLATIONS.keys()) | set(json_translations.keys()):
            merged[lang] = dict(json_translations.get(lang, {}))
            merged[lang].update(_repair_mojibake(LEGACY_TRANSLATIONS.get(lang, {})))
        self.translations = merged

    def set_language(self, lang):
        if lang in self.translations:
            self.lang = lang

    def get(self, key, **kwargs):
        translation = self.translations.get(self.lang, {}).get(key, key)
        if isinstance(translation, str):
            return translation.format(**kwargs)
        return translation


translator = Translator()
