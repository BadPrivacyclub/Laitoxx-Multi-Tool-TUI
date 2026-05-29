# Contributing

## Where Code Goes

- Feature-specific tool code: `src/laitoxx/features/<feature>/`
- Reusable code used by multiple features: `src/laitoxx/shared/`
- App-wide configuration and settings: `src/laitoxx/core/`
- CLI/TUI/GUI rendering and input collection: `src/laitoxx/interfaces/`
- Composition and registries: `src/laitoxx/app/`

## Rules

- Do not import from old root packages: `gui`, `tui`, `settings`, `script`.
- Do not add cross-feature imports. Use `app/` composition or `shared/`.
- Do not resolve project files from the current working directory. Use
  `laitoxx.core.settings.paths`.
- Keep new files below 300 lines unless the architecture audit is updated with a
  clear reason.
- Keep folder depth at five levels or less where practical.

## Checks

```bash
python scripts/check-structure.py
python -m compileall -q src tests laitoxx cli.py gui.py install.py
python -m pytest
```
