# Migration Plan

Strategy: big-bang migration with compatibility wrappers.

## Completed

- [x] Create `src/laitoxx` package.
- [x] Move CLI/TUI/GUI code into `interfaces/`.
- [x] Move application composition code into `app/`.
- [x] Move settings, localization and installer orchestration into `core/`.
- [x] Move tools into domain feature groups.
- [x] Move graph models/rendering helpers into `shared/graph`.
- [x] Move runtime config and data out of source folders.
- [x] Keep root `cli.py`, `gui.py`, `install.py` as compatibility wrappers.
- [x] Update imports to `laitoxx.*`.
- [x] Add architecture documentation and structure checker.

## Follow-Up Refactors

- [ ] Split large GUI modules listed in `audit.md`.
- [ ] Move remaining legacy inline translation map fully to JSON files.
- [ ] Add focused unit tests around the application registry.
- [ ] Package the project with console entry points after behavior is stable.
