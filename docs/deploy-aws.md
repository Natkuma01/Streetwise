# Deploying Streetwise on AWS (the cheap way)

This guide puts the whole site on **one small AWS Lightsail server**. React, Django, PostgreSQL and nginx all run on that one box. Nobody will use the site much at first, so one box is enough, and it keeps the bill flat.

## What it costs, and what to avoid

- One Lightsail Linux server with 1 GB of memory and a public IPv4 address: about **$7 a month** at the time of writing. AWS lists the plans at https://aws.amazon.com/lightsail/pricing/ . Check that page before you buy, because prices change. AWS has also given new accounts some free months on small plans, so look for that.
- The plan already includes the disk, the traffic allowance and a static IP address.
- The 0.5 GB plan is too small to run PostgreSQL and Django together. Do not pick it.
- The IPv6-only plans are cheaper, but people on IPv4-only networks cannot reach them. Pick the IPv4 plan.

Things that quietly cost a lot. **Do not create any of these:**

- A Lightsail load balancer.
- A managed database (Lightsail database or RDS). PostgreSQL runs on the same server instead.
- A NAT gateway. This is an EC2 and VPC feature, and it is expensive. Lightsail does not need one.
- Extra static IPs that are not attached to a server.

After you finish, set up a **billing alarm** (step 14). It is five minutes and it protects you from surprises.

## How it fits together

```
Browser ──https──> nginx ──/api/ and /admin/──> gunicorn (Django) ──> PostgreSQL
                     │
                     ├──/static/──> Django admin styles
                     └──everything else──> the React build (index.html)
```

The React site and the API share one address. Because the browser sees a single origin, there are no CORS problems in production.

## What you need before you start

1. An AWS account.
2. **A domain name.** This is not optional. The Django admin only works over HTTPS when `DJANGO_DEBUG=False`, because its login cookies are marked secure. HTTPS needs a domain name. Two ways to get one:
   - Buy one (about $10 to $15 a year).
   - Use a free name from DuckDNS (`something.duckdns.org`). Fine for a class project.
3. The Gmail app password for `streetwisefall2026cohort@gmail.com`. Ask Nat. Without it the site works but sends no email.
4. Node.js on your own laptop, to build the React site.

Below, `YOUR_DOMAIN` means your real name, like `streetwise.example.com`, and `SERVER_IP` is the static IP you create in step 1.

## 1. Create the server

In the Lightsail console:

1. **Create instance.** Pick a region near your users. Choose **Linux/Unix**, then **OS Only**, then **Ubuntu 24.04 LTS**.
2. Pick the **1 GB, public IPv4** plan. Name it `streetwise`.
3. After it starts, open **Networking**. Click **Create static IP** and attach it to the server. This keeps the address the same after a restart.
4. Still in **Networking**, open the **IPv4 Firewall**. It already allows SSH (22) and HTTP (80). **Add HTTPS (443).** Do the same on the IPv6 firewall if it shows one.
5. Optional but wise: change the SSH rule to allow only your own IP address.

## 2. Point the domain at the server

At your domain provider (or DuckDNS), create an **A record** for `YOUR_DOMAIN` that points to `SERVER_IP`. It can take a few minutes. Check it with:

```bash
ping YOUR_DOMAIN
```

## 3. Install the software

Connect with the **Connect using SSH** button in the Lightsail console. You are the `ubuntu` user. Then:

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install python3-venv python3-dev nginx postgresql git certbot python3-certbot-nginx
```

Add a 1 GB swap file. It is a safety net, so a busy moment does not kill the database on a small server:

```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 4. Create the database

Make a long random password and keep it for step 6:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Then create the database user and database (paste your password in place of `PASTE_PASSWORD`):

```bash
sudo -u postgres psql -c "CREATE USER streetwise WITH PASSWORD 'PASTE_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE streetwise OWNER streetwise;"
```

PostgreSQL only listens on the server itself by default, and the Lightsail firewall does not open port 5432. So the database is not reachable from the internet. Leave it that way.

## 5. Get the code

Create a service user that runs the app, and the folders it needs:

```bash
sudo adduser --system --group --home /opt/streetwise streetwise
sudo chmod 755 /opt/streetwise
sudo -u streetwise mkdir -p /opt/streetwise/logs
```

Clone the code. The release branch is what you deploy, so **merge the finished feature branch into `release/v1.0` on GitHub first**. Until then that branch only has the empty starter project.

```bash
sudo -u streetwise git clone -b release/v1.0 https://github.com/Natkuma01/Streetwise.git /opt/streetwise/app
```

If the repository is private, this asks for a login. The simple fix is a read-only **deploy key**: run `sudo -u streetwise mkdir -m 700 /opt/streetwise/.ssh` and then `sudo -u streetwise ssh-keygen -t ed25519 -f /opt/streetwise/.ssh/id_ed25519 -N ""`, add the `.pub` file under the repo's **Settings, Deploy keys** on GitHub, and clone with the `git@github.com:Natkuma01/Streetwise.git` address.

Install the Python packages:

```bash
sudo -u streetwise python3 -m venv /opt/streetwise/venv
sudo -u streetwise /opt/streetwise/venv/bin/pip install -r /opt/streetwise/app/requirements.txt
```

## 6. Write the settings file

```bash
sudo -u streetwise cp /opt/streetwise/app/deploy/env.production.example /opt/streetwise/app/.env
sudo -u streetwise nano /opt/streetwise/app/.env
```

Fill in every blank and replace every `YOUR_DOMAIN`:

- `DJANGO_SECRET_KEY`: make one with `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`.
- `POSTGRES_PASSWORD`: the password from step 4.
- `EMAIL_HOST_PASSWORD`: the Gmail app password.
- Check that `NUM_PROXIES=1` is there. This one matters. nginx sits in front of Django. Without it, every visitor looks like the same person, so the spam limit would block everyone after 10 submits. With a wrong setting, a visitor could also fake their address and dodge the limit.

Lock the file down:

```bash
sudo chmod 600 /opt/streetwise/app/.env
```

## 7. Set up the database tables and admin login

```bash
sudo -u streetwise /opt/streetwise/venv/bin/python /opt/streetwise/app/manage.py migrate
sudo -u streetwise /opt/streetwise/venv/bin/python /opt/streetwise/app/manage.py collectstatic --noinput
sudo -u streetwise /opt/streetwise/venv/bin/python /opt/streetwise/app/manage.py createsuperuser
```

`migrate` also adds the eight starting categories.

## 8. Start the app

```bash
sudo cp /opt/streetwise/app/deploy/streetwise.service /etc/systemd/system/streetwise.service
sudo systemctl daemon-reload
sudo systemctl enable --now streetwise
sudo systemctl status streetwise
```

You want to see `active (running)`. If not, read the log with `sudo journalctl -u streetwise -n 50`.

## 9. Set up nginx

```bash
sudo cp /opt/streetwise/app/deploy/streetwise-proxy.conf /etc/nginx/streetwise-proxy.conf
sudo cp /opt/streetwise/app/deploy/nginx-streetwise.conf /etc/nginx/sites-available/streetwise
sudo sed -i 's/YOUR_DOMAIN/your.real.domain/' /etc/nginx/sites-available/streetwise
sudo ln -s /etc/nginx/sites-available/streetwise /etc/nginx/sites-enabled/streetwise
sudo rm /etc/nginx/sites-enabled/default
sudo mkdir -p /var/www/streetwise && sudo chown ubuntu:ubuntu /var/www/streetwise
sudo nginx -t && sudo systemctl reload nginx
```

Put your real domain where it says `your.real.domain`.

## 10. Upload the React site

Do this on **your own laptop**, in the project folder. The server is too small to build React comfortably.

```bash
cd frontend
npm ci
npm run build
rsync -av --delete -e "ssh -i /path/to/your-lightsail-key.pem" dist/ ubuntu@SERVER_IP:/var/www/streetwise/
```

The SSH key is the default key you can download from your Lightsail **Account, SSH keys** page.

## 11. Turn on HTTPS

The domain must already point at the server (step 2). Then, on the server:

```bash
sudo certbot --nginx -d YOUR_DOMAIN
```

Give an email address, accept the terms, and choose to **redirect HTTP to HTTPS** when it asks. Certbot renews the certificate by itself. Check that renewal works:

```bash
sudo certbot renew --dry-run
```

## 12. Turn on the reminder and the backup

```bash
sudo cp /opt/streetwise/app/deploy/streetwise.cron /etc/cron.d/streetwise
sudo chmod 644 /etc/cron.d/streetwise
sudo chmod +x /opt/streetwise/app/deploy/backup-db.sh
```

- Every hour, cron runs `send_pending_reminders`. It emails the project inbox once about any event that has waited more than 24 hours.
- Every night at 03:15 (server time, which is UTC) it saves a compressed copy of the database to `/var/backups/streetwise` and deletes copies older than 14 days.

A backup on the same server does not help if the server itself is lost. For real safety, turn on **automatic snapshots** for the instance in the Lightsail console (they cost a little extra, see the pricing page), or copy the backup folder somewhere else now and then.

## 13. Check that it all works

Go through this list in a browser and write down anything that fails:

1. `https://YOUR_DOMAIN/api/health/` shows `{"status": "ok"}`.
2. `https://YOUR_DOMAIN/` shows the React site.
3. `https://YOUR_DOMAIN/admin/` shows a styled login page, and your superuser can log in.
4. Submit a test event from the site. It shows up in the calendar (faded, as Pending).
5. Two emails arrive: the receipt for the submitter, and the heads-up at the project inbox. The receipt link looks like `https://YOUR_DOMAIN/events/manage#...`.
6. In the admin, approve the event. The submitter gets the approval email.
7. Refresh a page like `https://YOUR_DOMAIN/events/manage`. It still loads the React site (it does not show a 404).
8. Run the reminder by hand: `sudo -u streetwise /opt/streetwise/venv/bin/python /opt/streetwise/app/manage.py send_pending_reminders --dry-run`.
9. Run the backup by hand: `sudo /opt/streetwise/app/deploy/backup-db.sh`, then `ls /var/backups/streetwise`.

If email does not arrive, look at `sudo journalctl -u streetwise -n 100`. A failed email never stops an event from saving. It is only written to the log.

## 14. Add a billing alarm

In the AWS console, open **Billing and Cost Management, Budgets**. Create a **monthly cost budget** of about $15 and send an alert to your email at 80 percent. If something unexpected gets created, you hear about it in days, not at the end of the month.

## Updating the site later

Backend (on the server):

```bash
bash /opt/streetwise/app/deploy/update.sh              # deploys release/v1.0
```

The script pulls the branch, installs packages, runs `migrate` and `collectstatic`, and restarts the app.

Frontend (on your laptop): repeat step 10.

## Restoring a backup

```bash
sudo systemctl stop streetwise
sudo -u postgres psql -c "DROP DATABASE streetwise;"
sudo -u postgres psql -c "CREATE DATABASE streetwise OWNER streetwise;"
gunzip -c /var/backups/streetwise/streetwise-YYYY-MM-DD.sql.gz | sudo -u postgres psql streetwise
sudo systemctl start streetwise
```

## Troubleshooting

| Problem | Likely cause |
| --- | --- |
| nginx shows `502 Bad Gateway` | The app is not running. Run `sudo systemctl status streetwise` and `sudo journalctl -u streetwise -n 50`. |
| Admin login loops or says the CSRF check failed | You are on plain `http://`. Use `https://`. Also check `CSRF_TRUSTED_ORIGINS` in `.env`. |
| `400 Bad Request` on every page | `DJANGO_ALLOWED_HOSTS` in `.env` does not include the domain. |
| Everyone gets `429` after a few submits | `NUM_PROXIES=1` is missing from `.env`, so all visitors share one limit. Add it and run `sudo systemctl restart streetwise`. |
| The admin has no styling | `collectstatic` was not run, or `/opt/streetwise` is not readable by nginx. Run `sudo chmod 755 /opt/streetwise`. |
| No emails | Gmail app password missing or wrong. Read the app log. |
| Page not found on refresh at `/events/manage` | The nginx site file is not the one from `deploy/`, or `/var/www/streetwise/index.html` is missing. |

After any change to `.env`, restart with `sudo systemctl restart streetwise`.

## What has been tested, and what has not

This guide was written in a sandbox with no AWS access, so be clear about what is proven.

**Tested here:**

- The nginx config, on real nginx 1.24 in front of gunicorn running Django with `DEBUG` off. It passed `nginx -t`. `/api/` and `/admin/` reach Django, `/static/` serves the admin styles, `/events/manage` falls back to `index.html`, and API 404s stay as API 404s.
- Rate limiting through nginx with `NUM_PROXIES=1`. Sending fake `X-Forwarded-For` headers did not get around the limit.
- The private link header works through nginx.
- `collectstatic` and `check --deploy` run in production mode. The remaining warnings are about HSTS preload and the temporary test settings used here, not about the project.
- The shell scripts pass `bash -n` (syntax check only).
- The full Django test suite passes on PostgreSQL.

**Not tested, so check these on the real server:**

- Every AWS console step (creating the server, static IP, firewall, domain, billing alarm).
- The `adduser`, permission and `systemctl` commands. The service file passed `systemd-analyze` except for the one complaint that gunicorn was not installed in this sandbox.
- `certbot` and HTTPS.
- The cron file, the backup script and the restore steps against a real PostgreSQL server install.
- Sending real email through Gmail.
- Whether 2 gunicorn workers feel fast enough on the 1 GB plan. Raise `--workers` only if the server has spare memory.
