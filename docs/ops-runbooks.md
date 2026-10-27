# FMS Operations Runbooks

Runbooks for staging, production, backup, monitoring, performance, and deployment.

---

## Staging server setup (FMS-M02)

### Prerequisites

- Server: 2 vCPU, 4 GB RAM minimum; Ubuntu 22.04 LTS
- Domain: `staging.fms.example.com` (replace with actual domain)
- DNS A record pointing to server IP
- App tag: `v0.1.0` (or the latest release tag)

### 1. Install bench and dependencies

```bash
# As root
apt update && apt install -y python3.14 python3.14-dev python3.14-venv \
  git redis-server mariadb-server nginx supervisor \
  nodejs npm wkhtmltopdf libssl-dev libffi-dev build-essential
npm install -g yarn

# Create frappe user
adduser --gecos "" frappe
usermod -aG sudo frappe
su - frappe
```

### 2. Create bench

```bash
pip install frappe-bench
bench init --frappe-branch version-16 frappe-bench
cd frappe-bench
```

### 3. Install apps from tags

```bash
bench get-app --branch version-16 payments
bench get-app --branch version-16 erpnext
bench get-app --branch v0.1.0 https://github.com/niiniyare/Afms.git
```

### 4. Create staging site

```bash
bench new-site staging.fms.example.com \
  --db-name fms_staging \
  --admin-password <strong-password>
bench --site staging.fms.example.com install-app payments
bench --site staging.fms.example.com install-app erpnext
bench --site staging.fms.example.com install-app forecourt
bench --site staging.fms.example.com set-config developer_mode 0
bench build --app forecourt
```

### 5. Configure production mode

```bash
sudo bench setup production frappe
sudo bench setup nginx
sudo supervisorctl reload
sudo systemctl enable nginx && sudo systemctl start nginx
```

### 6. SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d staging.fms.example.com
```

### Verify

Open `https://staging.fms.example.com` — should load the ERPNext login page.
Go to **Help → About** and verify the forecourt app version shows `0.1.0`.

---

## Production server setup (FMS-M03)

Follow the staging instructions above with these differences:

- Domain: `fms.example.com`
- DB name: `fms_production`
- Use a strong separate DB root password stored in a password manager
- `developer_mode` must be **0** (do not set it to 1)

### Security hardening

```bash
# Firewall — allow only SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Disable root SSH login
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### Verify production health

```bash
bench doctor
# Should show: workers running, scheduler enabled, no critical errors

bench --site fms.example.com migrate  # Should complete with no errors
```

---

## Backup and restore (FMS-M04)

### Daily automated backup

```bash
# Add to frappe user's crontab (crontab -e)
0 2 * * * cd /home/frappe/frappe-bench && bench --site fms.example.com backup --with-files --compress 2>&1 >> /home/frappe/backup.log
```

Backups are stored in `/home/frappe/frappe-bench/sites/fms.example.com/private/backups/`.

### Off-site copy (example: rclone to S3)

```bash
# Install rclone and configure an S3 remote named 'fms-backup'
# Then add to crontab after the backup line:
30 2 * * * rclone copy /home/frappe/frappe-bench/sites/fms.example.com/private/backups/ fms-backup:fms-backups/$(hostname)/ --max-age 24h 2>&1 >> /home/frappe/backup-offsite.log
```

### Restore drill

```bash
# Download a backup to a scratch machine, then:
bench new-site restore-test.localhost \
  --db-name fms_restore_test \
  --admin-password admin

bench --site restore-test.localhost restore \
  /path/to/fms_production-2026-10-27-database.sql.gz \
  --with-public-files /path/to/fms_production-2026-10-27-files.tar.gz \
  --with-private-files /path/to/fms_production-2026-10-27-private-files.tar.gz

bench --site restore-test.localhost migrate
bench --site restore-test.localhost list-apps
```

Verify shift counts and last known GL balance match the production snapshot.

---

## Monitoring and alerts (FMS-M05)

### Uptime monitoring

Use an external uptime service (UptimeRobot, Better Uptime, or similar) to ping `https://fms.example.com/api/method/ping` every 5 minutes. Alert on first failure.

### Disk and DB size alert (cron)

```bash
# /home/frappe/check_disk.sh
#!/bin/bash
THRESHOLD=85
USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$USAGE" -gt "$THRESHOLD" ]; then
  echo "Disk usage at ${USAGE}% on $(hostname)" | mail -s "FMS disk alert" admin@example.com
fi
```

Add to crontab: `0 * * * * /home/frappe/check_disk.sh`

### Error Log digest

In ERPNext: set up a **Notification** on doctype *Error Log* with event *New*. Send to admin email when `doc.method` contains "forecourt".

### FMS Health email

Schedule the FMS Health Check report (see **FMS Health** script report) as a daily scheduled report. ERPNext can email a report automatically: go to the report, click *Add to Desktop*, then configure the **Auto Email Report** DocType.

### Background job failure alert

Frappe logs failed jobs in *RQ Failed Jobs*. Create a **Notification** on *Integration Inbox* where `status = "Failed"` to alert the admin by email.

---

## Performance settings (FMS-M06)

### Gunicorn workers

```bash
# In common_site_config.json or via bench command
bench set-config -g gunicorn_workers 4   # Start with 2 × CPU cores
```

### Background workers

For production with many concurrent shifts, run a worker dedicated to the `long` queue:

```bash
# supervisord config (bench generates this at /etc/supervisor/conf.d/frappe.conf)
# Ensure at least one worker for 'long' queue:
bench setup supervisor
```

### MariaDB tuning

Add to `/etc/mysql/mariadb.conf.d/99-fms.cnf`:

```ini
[mysqld]
innodb_buffer_pool_size = 1G      # Set to 60-70% of available RAM
innodb_log_file_size = 256M
query_cache_type = 0              # Disable query cache (deprecated)
max_connections = 200
```

Restart MariaDB after changes: `sudo systemctl restart mariadb`

### Verify

Run a background close on a large shift (250+ rows) and confirm it completes in under 60 seconds. Monitor with: `bench --site fms.example.com execute frappe.utils.doctor`

---

## Deployment pipeline (FMS-M07)

### Deploy a new release tag

```bash
#!/bin/bash
# deploy.sh <tag>
# Example: ./deploy.sh v0.1.1

set -e
TAG=$1
SITE="fms.example.com"
BENCH_DIR="/home/frappe/frappe-bench"

cd "$BENCH_DIR"

echo "=== Backing up $SITE ==="
bench --site "$SITE" backup --with-files --compress

echo "=== Fetching tag $TAG ==="
cd apps/forecourt
git fetch origin
git checkout "$TAG"
cd "$BENCH_DIR"

echo "=== Migrating ==="
bench --site "$SITE" migrate

echo "=== Building assets ==="
bench build --app forecourt

echo "=== Restarting ==="
sudo supervisorctl reload

echo "=== Deploy $TAG complete ==="
bench --site "$SITE" execute forecourt.__version__
```

### Rollback

If the new release fails:

```bash
cd /home/frappe/frappe-bench/apps/forecourt
git checkout <previous-tag>
cd /home/frappe/frappe-bench
bench --site fms.example.com migrate  # migrations are forward-only; rollback only safe without DB changes
bench build --app forecourt
sudo supervisorctl reload
```

For DB changes: restore from the backup taken before the deploy.

---

## Upgrade policy (FMS-M08)

### Monthly minor upgrades

1. First Monday of the month: apply on staging.
2. Run `bench --site staging.fms.example.com execute forecourt.tests.golden.run` — must print "all checks passed".
3. If green: apply same upgrade to production the following Monday.
4. Document each upgrade in `CHANGELOG.md`.

### Upgrade commands

```bash
cd /home/frappe/frappe-bench
bench update --reset --branch version-16  # frappe, erpnext, hrms
bench migrate
bench build
sudo supervisorctl reload
```

### Before every upgrade

```bash
bench --site fms.example.com backup --with-files --compress
```
