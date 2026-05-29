# Architecture Audit

## Current Pain Points Found

- Source code was split across root-level `gui/`, `tui/`, `settings/`, `script/`
  and standalone modules, so imports encoded UI history instead of architecture.
- Domain tools, UI dialogs, plugin runtime and settings all depended on relative
  working-directory paths.
- Runtime data lived beside source code: `bd/`, `translations/`,
  `lua_plugin_settings.json`, agreement markers and screenshots.
- `gui/tool_registry.py` was a shared application registry but lived inside the
  GUI layer.
- Shared graph models lived in the GUI package while TUI and Lua plugins also
  used them.
- `__pycache__`, `.pytest_cache`, `.ruff_cache` and generated artifacts were
  present in the working tree.

## Duplicate Or Blurred Responsibilities

- Localization exists both in JSON files and in the legacy `TRANSLATIONS` map.
  This is preserved for compatibility; new translation keys should be added to
  `resources/translations`.
- GUI graph rendering and graph models were mixed. Models now live in
  `shared/graph`; GUI rendering remains in `interfaces/gui`.
- The Lua plugin runtime exposes application services and is kept in `app/`
  because it composes core, shared graph objects and selected feature APIs.

## Large File Baseline

These files are over 300 lines and should be split in follow-up focused changes.
They are allow-listed in `scripts/check-structure.py` to avoid turning the first
architecture migration into a risky behavior rewrite.

```text
src/laitoxx/interfaces/gui/graph_editor.py
src/laitoxx/interfaces/gui/image_search_window.py
src/laitoxx/interfaces/gui/username_osint_window.py
src/laitoxx/interfaces/gui/plugin_builder.py
src/laitoxx/interfaces/tui/app.py
src/laitoxx/interfaces/gui/theme_editor.py
src/laitoxx/interfaces/gui/main_window.py
src/laitoxx/features/photo_geolocation/photo2geo.py
src/laitoxx/interfaces/gui/dialogs.py
src/laitoxx/app/plugins/engine.py
src/laitoxx/features/osint/google_osint.py
src/laitoxx/interfaces/tui/tool_forms.py
src/laitoxx/core/localization/i18n.py
src/laitoxx/features/osint/username_osint/nickname_generator.py
src/laitoxx/features/osint/username_osint/_patterns.py
src/laitoxx/shared/graph/mermaid.py
src/laitoxx/features/network/ip_info.py
src/laitoxx/features/osint/data_search.py
src/laitoxx/features/osint/username_osint/checker.py
src/laitoxx/interfaces/gui/worker.py
src/laitoxx/interfaces/gui/_image_workers.py
src/laitoxx/interfaces/tui/input_collectors.py
src/laitoxx/interfaces/tui/screens.py
src/laitoxx/features/photo_geolocation/photo2geo_backend.py
src/laitoxx/features/photo_geolocation/photo2geo_indexer.py
src/laitoxx/features/utilities/text_transformer.py
src/laitoxx/features/web_audit/web_security_tools.py
src/laitoxx/core/settings/network_manager.py
src/laitoxx/core/settings/settings_window.py
tests/test_photo2geo.py
```

## Dead Files And Runtime Artifacts

Moved:

- `bd/` -> `resources/data/`
- `translations/` -> `resources/translations/`
- `User Agreement.txt` -> `docs/legal/user-agreement.txt`
- screenshots and example graph files -> `public/`
- runtime settings -> `config/`

Removed during cleanup where the filesystem allowed it:

- Python bytecode caches;
- empty legacy source folders after migration.

Note: `.pytest_cache` is still present on this machine because Windows denied
deletion even with elevated command approval. It is ignored by `.gitignore` and
excluded from `project_structure.txt`.

## Git Note

The workspace did not contain a `.git` directory, so the guide step
`git checkout -b refactor/architecture` could not be executed here.
