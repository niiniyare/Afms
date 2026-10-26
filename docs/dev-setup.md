# Development Setup

Bench root: `/home/niini/afms/`  
App repo: `/home/niini/afms/apps/forecourt/`

## Component versions

| Component | Version |
|---|---|
| Frappe Framework | v16.52.0 (commit `4515014`) |
| ERPNext | v16.51.1 (commit `5af6561`) |
| forecourt | 0.0.1 |
| Python | 3.14.4 |
| Node.js | 24.19.0 |
| MariaDB | 11.8.6 |
| Redis | 8.0.5 |
| bench CLI | 5.31.0 |
| OS | Ubuntu (WSL2, Linux 6.18 microsoft-standard) |

## Sites

| Site | Purpose | Notes |
|---|---|---|
| `fms.localhost` | Development | `developer_mode = 1` |
| `test_fms` | Tests | `allow_tests = true` |

## MariaDB

Unix socket only — TCP on 127.0.0.1 is blocked in this environment.

```json
// sites/common_site_config.json
{ "db_socket": "/var/run/mysqld/mysqld.sock" }
```

## First-time setup

```bash
# 1. Start MariaDB (WSL — must be running before bench start)
sudo service mariadb start

# 2. Start bench (starts web, workers, Redis, watch)
cd /home/niini/afms
bench start

# 3. Open dev site
# http://fms.localhost:8000  (admin / <password set during new-site>)
```

## Common commands

```bash
make migrate          # bench migrate + clear-cache on fms.localhost
make test             # run-tests --app forecourt on test_fms
make lint             # pre-commit run --all-files
make export-fixtures  # export-fixtures on fms.localhost
make console          # frappe console on fms.localhost
make db               # mariadb shell on fms.localhost
```

(See `Makefile` at bench root for full target list.)

## Upgrading

```bash
bench update --pull --patch --build --reset
```
