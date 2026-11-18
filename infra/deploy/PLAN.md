# Plan: DAHA on one Azure VM

The checklist is `OWNERACTIONS.md`. This page is how it works and how to run it day to day.

## 1. The picture
```
 phone / laptop
      │  https://daha.yourdomain.com  (one DNS A record → the VM's public IP)
      │  or https://<name>.duckdns.org (free DuckDNS name → the same IP)
      ▼
 Azure VM (Ubuntu 24.04) · network rules allow only 22 (SSH), 80, 443
 └─ Docker Compose, project "daha"
     ├─ caddy  :80/:443  HTTPS (free Let's Encrypt certificate, renewed by itself)
     │    ▼
     ├─ web    127.0.0.1:3000  Next.js; proxies /api and /uploads to the API
     │    ▼
     ├─ api    127.0.0.1:8000  FastAPI; migrates and seeds on start
     │    ▼                    calls out to HarnessRouter (photo AI) and Exa (store search)
     └─ db     127.0.0.1:5432  Postgres 16 + pgvector
   volumes: daha_pgdata (database) · daha_uploads (photos) · daha_fastembed (search model)
            caddy_data (certificates)
   ~/daha/backups: nightly database + photo backups, kept 7 days
```
Only Caddy listens on the public network. The web app, the API and the database answer on `127.0.0.1` only. It's the same `docker-compose.yml` everyone uses with `make up`, plus `infra/deploy/docker-compose.prod.yml`, which adds Caddy, keeps the other ports local, and gives the API a long first-boot allowance.

**Your own subdomain:** one `A` record (`daha` → the VM's IP) at your DNS provider is all it takes. Nothing else on the domain changes, and Caddy gets a certificate for that one name only. That's also why it's not a Cloudflare Tunnel here: a tunnel needs the whole domain's DNS moved to Cloudflare.

**Why DuckDNS + Caddy without a domain:** it's free, the link is permanent, and people connect straight to the VM. `duckdns.org` is on the Public Suffix List, so our certificate limits aren't shared with other DuckDNS users. Azure's own free names (`*.cloudapp.azure.com`) are not on it, so their free certificates often fail. Other options we looked at: Tailscale Funnel (no open ports, but an unpublished bandwidth limit), Cloudflare quick tunnels (the link changes on every restart), and a named Cloudflare Tunnel or Cloudflare Access email gate (both need a domain you pay for).

## 2. What `deploy.sh` does
On your laptop:
1. Reads `infra/deploy/.env` (VM, SSH key, your subdomain or DuckDNS, demo choice), checks that `backend/.env` has the keys, and, for your own subdomain, warns if its DNS doesn't point at the VM yet.
2. Sends the committed code (`git archive HEAD`, so uncommitted edits never ship) to `~/daha/src.new` on the VM.
3. Sends your `backend/.env`, minus `JWT_SECRET`, `DEMO_MODE`, `PUBLIC_BASE_URL` and `CORS_ORIGINS`, plus the server's values for the last three. Files are written with owner-only permissions.
4. Runs `infra/deploy/remote.sh` on the VM, then waits until `https://<name>.duckdns.org/api/health` answers.

On the VM (`remote.sh`; every step checks first, so re-running is safe):
1. Adds a 4 GB swap file if the VM has under ~4 GB of memory and no swap.
2. Installs Docker (official `get.docker.com` script) if it's missing.
3. DuckDNS only: points the name at the VM's IP. (Your own subdomain is already pointed by its A record.)
4. Moves the new code into `~/daha/src`; the previous version stays in `~/daha/src.old` until the next deploy.
5. Writes `~/daha/config/backend.env` (your settings + a `JWT_SECRET` created once on the VM, so redeploys never log anyone out), links it as `src/backend/.env`, and writes `src/.env` with Docker Compose's own settings.
6. `docker compose up -d --build --remove-orphans --wait`: builds, starts, and waits until everything is healthy, or prints the logs.
7. Installs the nightly backup job (cron, 03:30).

## 3. Where things live on the VM
| Path | What |
|---|---|
| `~/daha/src` | the running code (`~/daha/src.old` = the previous deploy) |
| `~/daha/config/backend.env` | the server's settings and keys (owner-only) |
| `~/daha/config/jwt_secret` | the login-token secret, made once on the VM |
| `~/daha/config/deploy.env` | the web address, demo choice, and DuckDNS name and token if used (owner-only) |
| `~/daha/backups` | `db-YYYY-MM-DD.sql.gz`, `uploads-YYYY-MM-DD.tgz`, `backup.log` |

To run Docker commands yourself: `ssh` in, `cd ~/daha/src`, then e.g. `sudo docker compose ps`. The compose `.env` there already picks the right files and profile.

## 4. Running it
- **Update:** `git pull` on your laptop, then `./infra/deploy/deploy.sh`. Images rebuild where needed; data stays. Expect about a minute of downtime while containers restart.
- **Change a key or setting:** edit your laptop's `backend/.env`, then deploy again.
- **Roll back:** `git checkout <older commit>`, deploy, then `git checkout main`. If the newer version changed the database (a new migration in `backend/alembic/versions/`), the older code may not fit it: restore the backup from before the update too (§5).
- **Status and logs:** `./infra/deploy/deploy.sh status` and `./infra/deploy/deploy.sh logs`.

## 5. Data and backups
- Every night at 03:30, `backup.sh` saves `pg_dump` of the database and a tarball of the photos in `~/daha/backups`, keeping 7 days. Run one now with `./infra/deploy/deploy.sh backup`.
- **These backups live on the same VM**, so copy one to your laptop now and then:
  `scp azureuser@<IP>:~/daha/backups/db-<date>.sql.gz .` (add `-i <key>` if needed)
- **Restore the database** (on the VM, in `~/daha/src`; this replaces the current data):
  ```bash
  sudo docker compose stop caddy web api
  sudo docker compose exec -T db psql -U daha -d postgres -c 'DROP DATABASE daha' -c 'CREATE DATABASE daha'
  gunzip -c ~/daha/backups/db-<date>.sql.gz | sudo docker compose exec -T db psql -U daha -d daha
  sudo docker compose up -d --wait
  ```
- **Restore photos:** `sudo docker run --rm -v daha_daha_uploads:/uploads -v ~/daha/backups:/backup alpine tar -xzf /backup/uploads-<date>.tgz -C /uploads`

## 6. Turn demo mode off (for real students)
With `DEMO_MODE=true`, the first boot seeds a demo campus whose accounts (`maya@demo.daha` and the others, password `daha-demo`) are public knowledge. Turning demo off later hides the one-tap logins, but those accounts would still exist. So start from a clean database. **This deletes all data on the server**, so back up first:
```bash
ssh azureuser@<IP>
cd ~/daha/src && sudo docker compose down && sudo docker volume rm daha_daha_pgdata daha_daha_uploads
exit
```
Then set `DEMO_MODE=false` in `infra/deploy/.env` and run `./infra/deploy/deploy.sh`. The first boot then seeds only the campus, dorms and exchange points.

## 7. Security choices
- Keys live only in your laptop's `backend/.env` and the VM's `~/daha/config` (owner-only files), never in git or in Docker images. The scripts never print them.
- Public ports are only 80 and 443 (Caddy); the API, web and database listen on `127.0.0.1`. SSH is key-only; limit it to your IP in the Azure network rules.
- HTTPS everywhere, with HSTS. The API and web containers run as non-root users.
- Ubuntu installs security updates automatically (unattended-upgrades is on by default). Docker images update when you redeploy.

## 8. Later (not in this setup)
- **Email verification** at sign-up: a 6-digit code to the `@stanford.edu` address. It needs an email sender, either a team Gmail account over SMTP for a pilot, or a proper sending domain. That's A's backend work plus a web screen.
- **Backups off the VM:** copy the nightly files to Azure Blob Storage with a SAS token.
- **Uptime alerts:** a free external monitor on `https://<your address>/api/health`.
- **Auto-deploy:** a GitHub Action that runs `deploy.sh` when `main` changes.
- **Your own domain someday:** then a named Cloudflare Tunnel (no open ports) and the Cloudflare Access email gate become options.
- **More users:** a bigger VM first; Azure's managed Postgres later, if needed.
