# Kynara Staging Environment Setup

This guide sets up a full staging environment so every change is tested before it reaches **kynaraai.com**.

---

## Branch Strategy

| Branch    | Environment | URL                                    |
|-----------|-------------|----------------------------------------|
| `develop` | Staging     | `https://kynara-staging.up.railway.app` |
| `main`    | Production  | `https://kynaraai.com`                 |

**Rule:** all work goes to `develop` first. When staging looks good, open a PR from `develop` → `main`.

---

## How It Works

1. You push a commit to `develop`
2. GitHub Actions runs the full CI suite (tests, lint, type-check, build)
3. If CI passes, the `deploy.yml` workflow auto-deploys to Railway **staging** environment
4. You verify on the staging URL
5. You merge `develop` → `main` via PR
6. `main` auto-deploys to Railway **production** environment

---

## One-Time Railway Setup

### 1. Create the staging environment in Railway

1. Open your [Railway project](https://railway.app)
2. Click **Environments** → **New Environment**
3. Name it `staging`
4. Railway will clone your production environment config — you'll then override variables (see below)

### 2. Set environment variables for staging

In Railway → staging environment, set these for the **backend** service:

```
DATABASE_URL          = <your staging postgres URL — Railway auto-creates if you add a Postgres service>
REDIS_URL             = <your staging redis URL>
SECRET_KEY            = <a different secret from production>
RESEND_API_KEY        = <same key is fine, or use a test key>
FRONTEND_URL          = https://kynara-staging.up.railway.app
ALLOWED_ORIGINS       = https://kynara-staging.up.railway.app
STRIPE_SECRET_KEY     = <use Stripe TEST mode key for staging>
STRIPE_WEBHOOK_SECRET = <staging webhook secret from Stripe dashboard>
ENVIRONMENT           = staging
```

For the **frontend** service in the staging environment, set:

```
VITE_API_BASE = https://kynara-staging.up.railway.app
```

Or configure Railway to run `npm run build:staging` as the build command — this picks up `frontend/.env.staging` automatically.

### 3. Get your Railway tokens

Railway → Account Settings → **Tokens** → create two tokens:

| Token name               | Scope  | Used for          |
|--------------------------|--------|-------------------|
| `github-actions-staging` | Project | Staging deploys  |
| `github-actions-prod`    | Project | Production deploys |

### 4. Add GitHub secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → add:

| Secret name                | Value                         |
|----------------------------|-------------------------------|
| `RAILWAY_TOKEN_STAGING`    | staging token from step above |
| `RAILWAY_TOKEN_PRODUCTION` | production token              |

### 5. Create GitHub Environments (for deploy approvals)

Go to GitHub → **Settings** → **Environments**:

- Create environment `staging` — no approval required, allowed on `develop` branch
- Create environment `production` — **require a reviewer** (yourself), allowed only on `main` branch

This means every production deploy needs a manual approval click in GitHub Actions.

### 6. Create the `develop` branch

```bash
git checkout -b develop
git push -u origin develop
```

### 7. Protect branches in GitHub

Go to **Settings** → **Branches** → add rules:

**`main`:**
- Require pull request before merging
- Require status checks: `backend`, `frontend`, `sdk-python`, `sdk-typescript`, `sidecar`
- Require branches to be up to date before merging
- Do not allow bypassing the above settings

**`develop`:**
- Require status checks: `backend`, `frontend`
- Allow direct pushes (so you can push work-in-progress freely)

---

## Daily Workflow

```bash
# Start new work
git checkout develop
git pull

# Make changes, commit
git add -A
git commit -m "feat: my new feature"
git push

# CI runs automatically, then deploys to staging
# Verify on https://kynara-staging.up.railway.app

# When ready for production
gh pr create --base main --head develop --title "Release: my new feature"
# Get CI green, approve in GitHub Actions, merge
```

---

## Frontend Build Modes

The frontend now has three build scripts:

| Command                   | Env file              | `VITE_API_BASE`                        |
|---------------------------|-----------------------|----------------------------------------|
| `npm run build`           | `.env.production`     | `https://api.kynaraai.com`             |
| `npm run build:staging`   | `.env.staging`        | `https://kynara-staging.up.railway.app`|
| `npm run build:production`| `.env.production`     | `https://api.kynaraai.com`             |

Railway uses your service's **Build Command** setting. Set it to:
- Staging frontend service: `npm run build:staging`
- Production frontend service: `npm run build:production`

---

## Docker Image Tags

CI now pushes:
- `develop` push → tags images `:staging` + `:<sha>`
- `main` push → tags images `:latest` + `:<sha>`

So Railway can pin the staging environment to the `:staging` tag and production to `:latest`.

---

## Verify the Setup

After completing the steps above:

1. Push any small change to `develop`
2. Watch GitHub Actions — CI job should run
3. After CI passes, the `Deploy → Staging` job should run in `deploy.yml`
4. Open `https://kynara-staging.up.railway.app` and confirm the change is live
5. Merge to `main`, approve the production deploy gate in GitHub Actions
6. Confirm `https://kynaraai.com` reflects the change

---

## Files Added/Changed

| File                                    | What changed                                    |
|-----------------------------------------|-------------------------------------------------|
| `.github/workflows/ci.yml`              | Now triggers on `develop` branch too            |
| `.github/workflows/deploy.yml`          | New: auto-deploys staging on `develop`, prod on `main` |
| `frontend/.env.staging`                 | New: `VITE_API_BASE` for staging                |
| `frontend/.env.production`              | New: `VITE_API_BASE` for production             |
| `frontend/package.json`                 | Added `build:staging` and `build:production` scripts |
