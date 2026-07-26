# Repository Guidelines

## Project Structure & Module Organization

Production code lives in `butterbot/`. `core/` contains framework contracts,
events, data models, and lifecycle primitives; `app/` provides `BotApp`,
configuration, and source management; `sources/bilibili/` and
`sources/napcat/` contain integrations; `utils/` contains logging and WebSocket
support. Tests mirror this layout under `tests/`. User-facing examples and the
configuration template are in `examples/`, while architecture and API guides
are in `docs/`.

Keep dependencies flowing toward `core`: integrations may depend on core
contracts, but core must not import application or source implementations.

## Build, Test, and Development Commands

- `uv sync --locked --dev` installs the locked runtime and development
  environment.
- `uv run pytest` runs the complete test suite.
- `uv run pytest --cov=butterbot --cov-report=term-missing --cov-fail-under=70`
  enforces the CI coverage floor.
- `uv run ruff check .` checks imports and lint rules.
- `uv run ruff format --check .` verifies formatting; omit `--check` to format.
- `uv run pyright` runs static type checking.
- `uv build` creates the wheel and source distribution.
- `uv run pre-commit run --all-files` reproduces repository hooks.

Copy `examples/config.example.yaml` to `config.yaml` before running examples.
Never commit the resulting file or real credentials.

## Coding Style & Naming Conventions

Use Python 3.12+ syntax, four-space indentation, double quotes, and an 88-column
target. Ruff owns formatting and import ordering. Use `snake_case` for
functions/modules, `PascalCase` for classes, and descriptive type parameters.
Public APIs require useful type annotations. Preserve lifecycle ownership:
sources close their tasks, the event bus owns callback tasks, and APIs release
connections through `aclose()`.

Code comments should be written in Chinese when comments are needed. Prefer
comments that explain intent, constraints, or non-obvious behavior rather than
restating the code.

Function names, class names, and variable names should follow normal Python
naming conventions:

- `snake_case` for functions, methods, modules, and variables
- `PascalCase` for classes
- `UPPER_CASE` for constants when appropriate

## Testing Guidelines

Pytest and `pytest-asyncio` are used. Name files `test_*.py`, classes `Test*`,
and functions `test_*`. Add a regression test before fixing confirmed defects.
Tests must avoid external networks, ordering dependencies, unnecessary sleeps,
global-state leakage, and unfinished asyncio tasks. Cover cancellation,
timeouts, exception propagation, and idempotent shutdown when changing async
code.

## Commit & Pull Request Guidelines

Follow Conventional Commits for commit messages: keep the type and optional
scope in English, and write the subject in concise Chinese. Examples:
`feat: 新增配置加载` or `fix(core): 修复重复初始化`.

Keep each commit focused and include its tests.

Pull requests should explain the problem, behavioral and API impact,
verification commands, and related issue. Include logs for lifecycle or CLI
changes; screenshots are only needed for visual changes.
