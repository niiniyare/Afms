# Forecourt Management System (FMS)

Forecourt (fuel station) management app built on **Frappe Framework v16 + ERPNext v16**.

Serves multiple stations owned by different companies, dealers and investors. Station managers post each shift after it ends; the system reconciles fuel and cash, then posts native ERPNext accounting and stock entries.

| Document | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Rules for developers and agents |
| [docs/fms.md](docs/fms.md) | Design guide: behaviour, rules, formulas, error codes |
| [docs/catalogue.md](docs/catalogue.md) | DocType catalogue: names, fields, permissions, workspaces |
| [TASKS.md](TASKS.md) | Task list and progress |

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/niiniyare/Afms.git --branch main
bench --site your-site install-app forecourt
bench --site your-site migrate
```

## Development

```bash
# Install pre-commit hooks
cd apps/forecourt
pre-commit install

# Run tests
bench --site test_fms run-tests --app forecourt

# Build assets
bench build --app forecourt
```

Code style is enforced by pre-commit (ruff, eslint, prettier).

## License

MIT
