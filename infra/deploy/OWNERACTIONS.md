# Owner actions: put DAHA online (about 30 minutes)

You'll end up with a link like **`https://daha.yourdomain.com`** (a subdomain of a domain you own) or **`https://daha-stanford.duckdns.org`** (free) that works on any phone or laptop. Extra cost: **$0** beyond the Azure VM. The HTTPS certificate is free, and AI usage stays capped by the budgets in your `backend/.env`.

What you need: the VM (step 1), this repo on your laptop, and your `backend/.env` with the keys in it (it already has them). How it all works: `infra/deploy/PLAN.md`.

## 1. Create the VM (about 8 minutes, Azure portal)
Portal → **Create a resource** → **Virtual machine**:

| Field | Choose |
|---|---|
| Image | **Ubuntu Server 24.04 LTS** (x64 or Arm64; both work) |
| Size | your free size. 2 GB of memory or more is smoother; on a smaller VM the script adds swap, and the first build is just slower |
| Authentication | **SSH public key**, username **`azureuser`**. Either "Generate new key pair" (download the `.pem` file) or "Use existing public key" (paste the contents of `~/.ssh/id_ed25519.pub`) |
| Public inbound ports | **Allow selected ports: SSH (22), HTTP (80), HTTPS (443)** |
| Disks | the default is fine (30 GB or more) |
| Networking → Public IP | keep the new one it creates (the Standard kind keeps the same address) |

Click **Create** and wait about 2 minutes. On the VM's **Overview** page, copy the **Public IP address**.
- Already made the VM without HTTP/HTTPS? VM → **Networking** → **Add inbound port rule**: port **80**, TCP, Allow. Then the same again for **443**.
- Downloaded a `.pem` key? Run once: `chmod 600 ~/Downloads/<name>.pem`
- Safer, optional: in the SSH (22) rule, change **Source** from "Any" to **My IP address**.

## 2. Pick the web address (about 3 minutes): A or B
**A. A subdomain of your own domain** (e.g. `daha.yourdomain.com`). At the company that runs your domain's DNS, add **one** record:

| Type | Name / Host | Value / Points to | TTL |
|---|---|---|---|
| `A` | `daha` | the VM's public IP | default / auto |

- This only adds a new name. Your existing website, email and other records stay exactly as they are.
- DNS on **Cloudflare**? Set the record to **DNS only** (grey cloud), so Caddy can get its certificate directly.
- Rare: if your domain has **CAA** records, one of them must allow `letsencrypt.org`.

**B. No domain: a free DuckDNS name.**
1. Go to https://www.duckdns.org and sign in (GitHub, Google, …).
2. Type a name, e.g. `daha-stanford`, and click **add domain**.
3. Copy the **token** shown at the top of the page. Don't type the IP: the script sets it for you.

## 3. Fill in the deploy settings (about 2 minutes, on your laptop)
```bash
cd ~/Desktop/dummy2/Daha
git checkout main && git pull          # before this PR is merged: git checkout infra/azure-deploy
cp infra/deploy/.env.example infra/deploy/.env
```
Open `infra/deploy/.env` and fill in:
- `VM=azureuser@<the public IP>`
- `SSH_KEY=~/Downloads/<name>.pem` (only if you downloaded a key in step 1)
- **A:** `DOMAIN=daha.yourdomain.com`, or **B:** `DUCKDNS_SUBDOMAIN=daha-stanford` (just the name) and `DUCKDNS_TOKEN=<the token>`
- `DEMO_MODE=true` for judges and trying it out (one-tap demo accounts), or `false` for real students only

That file is gitignored, so nothing in it gets committed. Check that `backend/.env` still has `HARNESSROUTER_API_KEY`, `HARNESSROUTER_VISION_HARNESS_ID` and `EXA_API_KEY` filled in.

Say hello to the VM once, so SSH remembers it: `ssh -i ~/Downloads/<name>.pem azureuser@<IP>` (leave out `-i …` if you used your own key), type `yes`, then `exit`.

## 4. Deploy (about 15 minutes, mostly waiting)
```bash
./infra/deploy/deploy.sh        # or: make deploy
```
It connects, adds swap if the VM is small, installs Docker, points the DuckDNS name at the VM (option B), sends the code and your keys, builds and starts everything (database, API, website, HTTPS), turns on nightly backups, and finishes with:
```
✅ DAHA is live: https://daha.yourdomain.com
```

## 5. Check it and share it (about 2 minutes)
- Open the link on your phone. Log in with a demo account (if `DEMO_MODE=true`) or sign up with an `@stanford.edu` email. Try **Add → Snap your stuff** and **Explore → "kayak"**.
- Share the link. People can put it on their home screen like an app: iPhone **Share → Add to Home Screen**, Android **⋮ → Install app**.
- Hackathon: register both harness IDs (from `HARNESSROUTER_VISION_HARNESS_ID` in `backend/.env`) so the usage counts.

## Your questions, answered
- **Do I have to create a `.env` on the VM?** No. The script copies your laptop's `backend/.env` (keys included) to the VM, and adds the server's address, your demo choice, and a login secret that stays on the VM. To change a key later, edit your laptop's `backend/.env` and run the deploy again.
- **Do we need a database?** It's included. Postgres runs on the VM in Docker and stores accounts (email, scrambled password hash, dorm), listings, requests and chats; photos live in a Docker volume. Both are backed up every night at 03:30 to `~/daha/backups` on the VM, kept 7 days.
- **How do people get in?** Your link, in any browser, with HTTPS. Phones can share their location over HTTPS, which the location plan (`plans/LOCATION.md`) needs.
- **Is there email verification?** Not yet. Sign-ups are limited to `@stanford.edu` addresses, but nobody confirms they own the address. See `PLAN.md` → "Later".
- **What does it cost?** $0 beyond the VM. AI calls are capped by `AI_BUDGET_USD` and `COMMERCIAL_BUDGET_USD`.

## Day to day
| To… | Run on your laptop |
|---|---|
| update to the latest code | `git pull`, then `./infra/deploy/deploy.sh` |
| see if it's up | `./infra/deploy/deploy.sh status` |
| watch the logs | `./infra/deploy/deploy.sh logs` (Ctrl+C to stop) |
| back up right now | `./infra/deploy/deploy.sh backup` |

Data survives every redeploy. Restoring, rolling back, and turning demo mode off are in `PLAN.md`.

## If something goes wrong
| You see | Fix |
|---|---|
| `Can't SSH into …` | Check `VM` and `SSH_KEY` in `infra/deploy/.env`, that the VM is running, and that port 22 is allowed |
| `DuckDNS didn't accept the update` | `DUCKDNS_SUBDOMAIN` must be just the name (no `.duckdns.org`); recopy `DUCKDNS_TOKEN` |
| `⚠️ daha.yourdomain.com points to …, not to the VM` | The A record from step 2A is missing or has a typo. Check with `dig +short daha.yourdomain.com`; new records can take a few minutes to show up |
| `https://… isn't answering yet` | Open ports **80 and 443** (step 1), wait a minute, run `./infra/deploy/deploy.sh status` |
| The build stops with `killed` or `exit code 137` | The VM ran out of memory. Run the deploy again (swap is in place now), or pick a bigger size |
| `Something didn't start` + logs | Usually a typo in `backend/.env`. Fix it on your laptop and deploy again; the logs name the problem |
| The app says AI or store search "isn't set up" | A key is empty in your laptop's `backend/.env`. Fill it in and deploy again |
