# Kynara — Operationalization Guide (Free Tier)

**Stack:** AWS EC2 t2.micro · AWS RDS Postgres · DuckDNS · Let's Encrypt · Okta Dev · Stripe Test · Grafana Cloud  
**Estimated time:** 2–3 hours end to end  
**Cost:** $0 (AWS free tier valid for 12 months on new accounts)

---

## Before you start — create these free accounts

Do this first, in parallel, as some confirmations take a few minutes:

| Service | Free tier | Sign-up URL |
|---------|-----------|-------------|
| AWS | 12 months free (EC2 + RDS) | https://aws.amazon.com/free |
| DuckDNS | Free subdomains forever | https://www.duckdns.org |
| Okta Developer | Free up to 100 users | https://developer.okta.com/signup |
| Stripe | Test mode is always free | https://dashboard.stripe.com/register |
| Grafana Cloud | Free tier (no credit card) | https://grafana.com/auth/sign-up |

---

## Step 1 — Verify the app runs locally

Before touching any cloud infrastructure, confirm the app works on your machine.

```bash
# In the project root
docker compose up --build -d

# Run migrations and seed demo data
docker compose exec -e PYTHONPATH=/app backend alembic upgrade head
docker compose exec -e PYTHONPATH=/app backend python -m app.scripts.seed

# Open the app
open http://localhost:5173
# Login: admin@acme.com / demo-password-123!
```

If you see the dashboard, you're ready to proceed. Stop the containers:

```bash
docker compose down
```

---

## Step 2 — Get a free domain (DuckDNS)

You need a domain for HTTPS. DuckDNS gives you a free `*.duckdns.org` subdomain.

1. Go to https://www.duckdns.org and sign in with Google or GitHub.
2. Under "Domains", pick a name — e.g. `kynara-yourname` — and click **Add domain**.
3. Copy your **token** from the top of the page. You'll need it in Step 5.
4. Leave the IP blank for now — you'll fill it in once you have your EC2 IP.

Your app will be at: `https://kynara-yourname.duckdns.org`

---

## Step 3 — Launch an EC2 instance (AWS free tier)

1. Open **AWS Console → EC2 → Launch Instance**.
2. Fill in:
   - **Name:** `kynara-server`
   - **AMI:** Ubuntu Server 24.04 LTS (free tier eligible)
   - **Instance type:** `t2.micro` (free tier)
   - **Key pair:** Create new → name it `kynara-key` → download the `.pem` file → keep it safe
3. Under **Network settings → Security group**, add these inbound rules:
   - SSH: port 22, source = My IP
   - HTTP: port 80, source = Anywhere (0.0.0.0/0)
   - HTTPS: port 443, source = Anywhere (0.0.0.0/0)
4. **Storage:** leave at 8 GB (free tier includes 30 GB, you can increase later).
5. Click **Launch instance**.

Once the instance is running, copy its **Public IPv4 address**.

6. Go back to DuckDNS → paste the IP address into your domain → click **Update IP**.

---

## Step 4 — Create the RDS Postgres database (AWS free tier)

1. Open **AWS Console → RDS → Create database**.
2. Settings:
   - **Engine:** PostgreSQL 16
   - **Template:** Free tier
   - **DB instance identifier:** `kynara-db`
   - **Master username:** `kynara`
   - **Master password:** choose a strong password, write it down
   - **Instance class:** `db.t3.micro` (free tier)
   - **Storage:** 20 GB gp2 (free tier includes 20 GB)
3. Under **Connectivity:**
   - **VPC:** same VPC as your EC2 instance (usually `default`)
   - **Public access:** No
   - Under **VPC security group**, create a new one: `kynara-rds-sg`
4. Click **Create database**. It takes 3–5 minutes to provision.

**Allow EC2 to reach RDS:**

1. Once the DB is created, go to its **Security group** (`kynara-rds-sg`).
2. Add an inbound rule:
   - Type: PostgreSQL (port 5432)
   - Source: the security group attached to your EC2 instance

5. Copy the **Endpoint** from the RDS database page — looks like:
   `kynara-db.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com`

---

## Step 5 — SSH into EC2 and install Docker

```bash
# On your local machine — fix key permissions first
chmod 400 ~/Downloads/kynara-key.pem

# SSH in (replace with your EC2 public IP)
ssh -i ~/Downloads/kynara-key.pem ubuntu@YOUR_EC2_IP
```

Once inside the server, run:

```bash
# Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

# Install Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# Install Nginx and Certbot (for free SSL)
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Log out and back in so Docker group takes effect
exit
```

SSH back in:

```bash
ssh -i ~/Downloads/kynara-key.pem ubuntu@YOUR_EC2_IP
docker ps   # should work without sudo now
```

---

## Step 6 — Copy the app to the server

On your **local machine** (not the server):

```bash
# From the project root — copy files to the server
scp -i ~/Downloads/kynara-key.pem -r \
  "." ubuntu@YOUR_EC2_IP:~/kynara
```

Or if you have a Git remote:

```bash
# On the server
git clone https://github.com/YOUR_ORG/kynara.git ~/kynara
```

---

## Step 7 — Create the production environment file

On the server:

```bash
cd ~/kynara
nano .env.production
```

Paste this, filling in your real values:

```env
# Database — use your RDS endpoint
DATABASE_URL=postgresql+asyncpg://kynara:YOUR_DB_PASSWORD@YOUR_RDS_ENDPOINT:5432/kynara

# Redis — runs locally on this server
REDIS_URL=redis://localhost:6379/0

# Security — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=GENERATE_A_LONG_RANDOM_STRING_HERE

# Environment
ENV=production

# Okta SSO — fill in after Step 9
OKTA_ISSUER=
OKTA_CLIENT_ID=
OKTA_CLIENT_SECRET=

# Stripe — fill in after Step 10
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# OpenTelemetry — fill in after Step 11
OTEL_EXPORTER_OTLP_ENDPOINT=
```

Save and close (`Ctrl+X`, then `Y`).

Generate your JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Copy the output and paste it as JWT_SECRET in .env.production
```

---

## Step 8 — Create a production docker-compose

On the server:

```bash
nano ~/kynara/docker-compose.prod.yml
```

Paste:

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    restart: always
    ports:
      - "127.0.0.1:6379:6379"   # only accessible locally
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    restart: always
    env_file: .env.production
    depends_on:
      redis:
        condition: service_healthy
    ports:
      - "127.0.0.1:8000:8000"   # only accessible via Nginx
    command: >
      uvicorn app.main:app
      --host 0.0.0.0
      --port 8000
      --workers 2

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod      # we'll create this below
    restart: always
    ports:
      - "127.0.0.1:3000:80"
```

Now create a production Dockerfile for the frontend that builds static files:

```bash
nano ~/kynara/frontend/Dockerfile.prod
```

Paste:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV VITE_API_BASE=https://YOUR_DUCKDNS_DOMAIN
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Create the Nginx SPA config for the frontend container:

```bash
nano ~/kynara/frontend/nginx-spa.conf
```

Paste:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## Step 9 — Get free HTTPS with Let's Encrypt

**First**, make sure DuckDNS is pointing to your EC2 IP (Step 2).

On the server:

```bash
# Get a free SSL certificate (replace with your domain)
sudo certbot --nginx -d kynara-yourname.duckdns.org \
  --non-interactive --agree-tos -m your@email.com
```

Now configure Nginx to proxy to Docker:

```bash
sudo nano /etc/nginx/sites-available/kynara
```

Paste (replace the domain):

```nginx
server {
    listen 80;
    server_name kynara-yourname.duckdns.org;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name kynara-yourname.duckdns.org;

    ssl_certificate     /etc/letsencrypt/live/kynara-yourname.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/kynara-yourname.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Prometheus metrics (restrict to localhost in prod)
    location /metrics {
        proxy_pass http://127.0.0.1:8000;
        allow 127.0.0.1;
        deny all;
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/kynara /etc/nginx/sites-enabled/
sudo nginx -t          # should say "ok"
sudo systemctl reload nginx
```

---

## Step 10 — Set up Okta SSO (free developer account)

1. Sign in at https://developer.okta.com
2. Go to **Applications → Create App Integration**.
3. Choose **OIDC – Web Application** → Next.
4. Fill in:
   - **App name:** Kynara
   - **Sign-in redirect URI:** `https://YOUR_DOMAIN/api/v1/auth/sso/okta/callback`
   - **Sign-out redirect URI:** `https://YOUR_DOMAIN/login`
5. Click **Save**.
6. On the app's page, copy:
   - **Client ID**
   - **Client Secret**
7. On the Okta dashboard, click your org name (top right) → copy the **Okta domain** (looks like `dev-12345678.okta.com`).

Update `.env.production`:

```bash
nano ~/kynara/.env.production
```

Fill in:

```env
OKTA_ISSUER=https://dev-12345678.okta.com/oauth2/default
OKTA_CLIENT_ID=YOUR_CLIENT_ID
OKTA_CLIENT_SECRET=YOUR_CLIENT_SECRET
```

---

## Step 11 — Set up Stripe (test mode, free)

1. Log in at https://dashboard.stripe.com
2. Make sure the toggle at the top says **Test mode**.
3. Go to **Developers → API keys** → copy the **Secret key** (starts with `sk_test_`).
4. Go to **Developers → Webhooks → Add endpoint**:
   - URL: `https://YOUR_DOMAIN/api/v1/billing/webhook`
   - Events to listen to: `customer.subscription.updated`, `invoice.payment_succeeded`, `invoice.payment_failed`
5. After saving, click the webhook → reveal **Signing secret** (starts with `whsec_`).

Update `.env.production`:

```env
STRIPE_SECRET_KEY=sk_test_YOUR_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET
```

---

## Step 12 — Set up Grafana Cloud monitoring (free tier)

1. Sign up at https://grafana.com/auth/sign-up (no credit card needed).
2. Create a **Free** stack — choose a region close to you.
3. Go to **Connections → Add new connection → OpenTelemetry**.
4. Grafana will show you an OTLP endpoint and an API token. Copy both.

Update `.env.production`:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-0.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic YOUR_BASE64_TOKEN
```

> The Grafana UI will show you the exact header value — copy it exactly.

---

## Step 13 — Build and launch the app

On the server:

```bash
cd ~/kynara

# Build containers
docker compose -f docker-compose.prod.yml build

# Start everything
docker compose -f docker-compose.prod.yml up -d

# Watch logs to confirm startup
docker compose -f docker-compose.prod.yml logs -f backend
```

Wait until you see: `Application startup complete.`

---

## Step 14 — Run migrations and seed

```bash
docker compose -f docker-compose.prod.yml exec -e PYTHONPATH=/app backend \
  alembic upgrade head

docker compose -f docker-compose.prod.yml exec -e PYTHONPATH=/app backend \
  python -m app.scripts.seed
```

---

## Step 15 — Verify everything works

Open `https://YOUR_DOMAIN` in your browser and run through this checklist:

```
[ ] Login page loads with HTTPS padlock
[ ] Sign in with admin@acme.com / demo-password-123!
[ ] Dashboard loads and shows stat cards
[ ] "Continue with Okta" button redirects to Okta login page
[ ] Audit log page shows events
[ ] Billing page loads (even if showing test plan)
[ ] /api/v1/health returns {"status": "ok"}    (open in browser)
[ ] /api/docs loads the OpenAPI docs            (open in browser)
[ ] Grafana Cloud → Explore shows incoming traces
```

---

## Maintenance cheatsheet

```bash
# Restart the app
docker compose -f docker-compose.prod.yml restart

# View live logs
docker compose -f docker-compose.prod.yml logs -f

# Deploy a code update
cd ~/kynara
git pull
docker compose -f docker-compose.prod.yml build backend frontend
docker compose -f docker-compose.prod.yml up -d

# Run a new migration after a code update
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Renew SSL certificate (runs automatically, but can force it)
sudo certbot renew --dry-run
```

---

## Free tier limits to watch

| Resource | Free limit | What happens when exceeded |
|----------|-----------|---------------------------|
| EC2 t2.micro | 750 hrs/month | Billed at ~$0.012/hr |
| RDS t3.micro | 750 hrs/month | Billed at ~$0.017/hr |
| RDS storage | 20 GB | Billed at $0.115/GB/month |
| Data transfer out | 100 GB/month | Billed at $0.09/GB |
| Okta users | 100 MAU | Paid plan required |
| Grafana Cloud | 10k series, 50GB logs | Free tier throttles, not bills |

Set up an **AWS Budget alert** (Billing → Budgets → Create budget → Zero spend budget) to get an email if you accidentally exceed the free tier.

---

*Generated for Kynara · AWS free tier deployment · Okta Dev + Stripe test + Grafana Cloud*

---

---

# Alternative: Railway Deployment (Recommended for Quick Start)

**Stack:** Railway · Supabase Postgres · Okta Dev · Stripe Test · Grafana Cloud  
**Estimated time:** 30–45 minutes end to end  
**Cost:** $0 — Railway gives $5 free credit/month; Supabase free tier is permanent

Railway reads your existing `docker-compose.yml` directly and provisions managed infrastructure alongside it. No server config, no Nginx, no SSL setup — Railway handles all of that automatically.

---

## Before you start — create these free accounts

| Service | Free tier | Sign-up URL |
|---------|-----------|-------------|
| Railway | $5 credit/month (no card needed) | https://railway.app |
| Supabase | 500 MB Postgres, no time limit | https://supabase.com |
| Okta Developer | Free up to 100 users | https://developer.okta.com/signup |
| Stripe | Test mode is always free | https://dashboard.stripe.com/register |
| Grafana Cloud | Free tier (no credit card) | https://grafana.com/auth/sign-up |

---

## Step 1 — Verify the app runs locally first

```bash
docker compose up --build -d
docker compose exec backend sh -c "PYTHONPATH=/app alembic upgrade head"
docker compose exec backend sh -c "PYTHONPATH=/app python -m app.scripts.seed"
```

Open http://localhost:5173 and log in with `admin@acme.com` / `demo-password-123!`

If the dashboard loads, you're ready to deploy.

```bash
docker compose down
```

---

## Step 2 — Create a Supabase project (free Postgres)

1. Go to https://supabase.com and sign in.
2. Click **New project** → give it a name (e.g. `kynara`) → choose a region close to you → set a strong database password → click **Create new project**.
3. Wait ~2 minutes for provisioning.
4. Go to **Project Settings → Database**.
5. Under **Connection string**, select **URI** and choose the **Transaction pooler** mode (port 6543). Copy the full URI — it looks like:
   `postgresql://postgres.xxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres`
6. Replace `postgresql://` with `postgresql+asyncpg://` — this is what the backend expects.

Your `DATABASE_URL` will be:
```
postgresql+asyncpg://postgres.xxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

---

## Step 3 — Push your code to GitHub

Railway deploys from a Git repository.

```bash
# In the project root — initialise git if not already done
git init
git add .
git commit -m "Initial Kynara commit"
```

Create a new repository at https://github.com/new (keep it private), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/kynara.git
git push -u origin main
```

---

## Step 4 — Create a Railway project

1. Go to https://railway.app and sign in with GitHub.
2. Click **New Project → Deploy from GitHub repo** → select your `kynara` repository.
3. Railway will detect the repo. **Do not deploy yet** — click **Add variables** first (Step 5).

---

## Step 5 — Add environment variables in Railway

In your Railway project, click the **backend** service → **Variables** tab → add each variable:

```env
DATABASE_URL=postgresql+asyncpg://postgres.xxxx:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
REDIS_URL=redis://redis.railway.internal:6379/0
JWT_SECRET=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ENV=production

# Fill in after Step 7
OKTA_ISSUER=
OKTA_CLIENT_ID=
OKTA_CLIENT_SECRET=

# Fill in after Step 8
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

> **JWT_SECRET**: generate it locally with `python3 -c "import secrets; print(secrets.token_hex(32))"` and paste the result.

---

## Step 6 — Add a Redis service

Railway has a one-click Redis plugin:

1. In your Railway project dashboard, click **+ New** → **Database** → **Add Redis**.
2. Railway automatically injects `REDIS_URL` into services in the same project. You can delete the manual `REDIS_URL` variable you added if Railway auto-populates it.

---

## Step 7 — Configure the Railway services

Railway will try to deploy both `backend` and `frontend` from your `docker-compose.yml`. You need to point each service at the right Dockerfile and set the start command.

**Backend service:**
- **Root directory:** `backend`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`
- **Port:** `8000`

**Frontend service:**
- **Root directory:** `frontend`
- **Dockerfile:** `Dockerfile.prod` (create this file — see below)
- **Port:** `80`

Create `frontend/Dockerfile.prod` in your repo:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Create `frontend/nginx-spa.conf`:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Add a build variable to the **frontend** service in Railway:
```
VITE_API_BASE=https://<your-backend-railway-url>
```
(You'll get the backend URL after the first deploy — you can update this after.)

Commit and push both files:
```bash
git add frontend/Dockerfile.prod frontend/nginx-spa.conf
git commit -m "Add production frontend Dockerfile and nginx config"
git push
```

---

## Step 8 — Set up Okta SSO

1. Sign in at https://developer.okta.com
2. Go to **Applications → Create App Integration → OIDC – Web Application**.
3. Fill in:
   - **Sign-in redirect URI:** `https://<your-backend-railway-url>/api/v1/auth/sso/okta/callback`
   - **Sign-out redirect URI:** `https://<your-frontend-railway-url>/login`
4. Copy the **Client ID**, **Client Secret**, and your **Okta domain**.
5. Update Railway backend variables:
   ```env
   OKTA_ISSUER=https://dev-12345678.okta.com/oauth2/default
   OKTA_CLIENT_ID=YOUR_CLIENT_ID
   OKTA_CLIENT_SECRET=YOUR_CLIENT_SECRET
   ```

---

## Step 9 — Set up Stripe (test mode)

1. Log in at https://dashboard.stripe.com (ensure **Test mode** is on).
2. Go to **Developers → API keys** → copy the **Secret key** (`sk_test_...`).
3. Go to **Developers → Webhooks → Add endpoint**:
   - URL: `https://<your-backend-railway-url>/api/v1/billing/webhook`
   - Events: `customer.subscription.updated`, `invoice.payment_succeeded`, `invoice.payment_failed`
4. Reveal and copy the **Signing secret** (`whsec_...`).
5. Update Railway backend variables:
   ```env
   STRIPE_SECRET_KEY=sk_test_YOUR_KEY
   STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET
   ```

---

## Step 10 — Deploy and run migrations

Railway auto-deploys on every `git push`. Once the backend service shows **Active**:

1. Open the backend service → **Shell** tab (Railway provides a web shell).
2. Run:
   ```bash
   PYTHONPATH=/app alembic upgrade head
   PYTHONPATH=/app python -m app.scripts.seed
   ```

Or trigger it from your local machine using the Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Run migrations
railway run --service backend sh -c "PYTHONPATH=/app alembic upgrade head"
railway run --service backend sh -c "PYTHONPATH=/app python -m app.scripts.seed"
```

---

## Step 11 — Verify everything works

Open your Railway frontend URL and run through the checklist:

```
[ ] Login page loads with HTTPS padlock (Railway provides SSL automatically)
[ ] Sign in with admin@acme.com / demo-password-123!
[ ] Dashboard loads and shows stat cards
[ ] "Continue with Okta" button redirects to Okta login page
[ ] Audit log page shows events
[ ] Billing page loads
[ ] https://<backend-url>/api/v1/health returns {"status": "ok"}
[ ] https://<backend-url>/api/docs loads the OpenAPI docs
```

---

## Deploying updates

```bash
# Make your changes, then:
git add .
git commit -m "your change"
git push
# Railway auto-deploys — watch the build logs in the dashboard
```

After a code change that includes a new migration:

```bash
railway run --service backend sh -c "PYTHONPATH=/app alembic upgrade head"
```

---

## Railway free tier limits to watch

| Resource | Free limit | What happens when exceeded |
|----------|-----------|---------------------------|
| Railway compute | $5 credit/month | Services pause until next billing cycle |
| Supabase DB | 500 MB storage | Project paused (can unpause) |
| Supabase bandwidth | 5 GB/month | Throttled |
| Okta users | 100 MAU | Paid plan required |
| Stripe | Test mode unlimited | N/A |

Railway's $5/month credit is enough to run a backend + frontend + Redis with very light traffic. Add a credit card to Railway to avoid services pausing mid-month (you won't be charged unless you exceed the credit).

---

*Generated for Kynara · Railway free-tier deployment · Supabase + Okta Dev + Stripe test*
