SITE    = fms.localhost
TEST    = test_fms
APP     = forecourt

.PHONY: start migrate clear build test test-module lint console db export-fixtures

start:
	bench start

migrate:
	bench --site $(SITE) migrate
	bench --site $(SITE) clear-cache

clear:
	bench --site $(SITE) clear-cache

build:
	bench build --app $(APP)

test:
	bench --site $(TEST) run-tests --app $(APP)

test-module:
	bench --site $(TEST) run-tests --app $(APP) --module $(MODULE)

test-doctype:
	bench --site $(TEST) run-tests --app $(APP) --doctype "$(DOCTYPE)"

lint:
	pre-commit run --all-files

console:
	bench --site $(SITE) console

db:
	bench --site $(SITE) mariadb

export-fixtures:
	bench --site $(SITE) export-fixtures --app $(APP)

install-app:
	bench --site $(SITE) install-app $(APP)
