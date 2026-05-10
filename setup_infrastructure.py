#!/usr/bin/env python3
"""
Kynara Infrastructure Setup Script
====================================
Run this once from your local machine to:
  1. Create a Railway project (Postgres + backend + frontend services)
  2. Generate fresh secrets (JWT, encryption key, etc.)
  3. Configure all Railway environment variables
  4. Verify the Resend sending domain
  5. Print DNS records to add for kynaraai.com

Requirements:
    pip install requests python-dotenv

Usage:
    python setup_infrastructure.py
"""

import os
import json
import secrets
import string
import sys

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

# ── Credentials ───────────────────────────────────────────────────────────────
RAILWAY_TOKEN = "6aaeac5c-c776-41fd-bff2-9316d245b5c6"
RESEND_API_KEY = "re_BMNvU2Jy_6QtK3iJ1kQsuLqtPTjFL4Pqz"

BRAND_NAME   = "Kynara"
BRAND_DOMAIN = "kynaraai.com"
APP_URL      = f"https://{BRAND_DOMAIN}"
API_URL      = f"https://api.{BRAND_DOMAIN}"

RAILWAY_GQL  = "https://backboard.railway.app/graphql/v2"
RESEND_BASE  = "https://api.resend.com"

# ── Helpers ───────────────────────────────────────────────────────────────────

def railway(query, variables=None):
    r = requests.post(
        RAILWAY_GQL,
        headers={"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"Railway API error: {data['errors']}")
    return data["data"]

def resend(method, path, body=None):
    r = requests.request(
        method,
        f"{RESEND_BASE}{path}",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def gen_secret(n=48):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def banner(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

# ── Step 1: Verify Railway token ───────────────────────────────────────────────

banner("Step 1 — Verifying Railway token")
me = railway("{ me { name email } }")["me"]
print(f"  Logged in as: {me['name']} <{me['email']}>")

# ── Step 2: Create Railway project ────────────────────────────────────────────

banner("Step 2 — Creating Railway project: kynara")

# Fetch workspace ID
workspace_q = "{ workspaces { id name } }"
try:
    workspaces = railway(workspace_q).get("workspaces", [])
except Exception:
    workspaces = []

if not workspaces:
    # Try me.workspaces path
    me_q = "{ me { workspaces { id name } } }"
    try:
        workspaces = railway(me_q)["me"]["workspaces"]
    except Exception:
        workspaces = []

if not workspaces:
    raise RuntimeError("Could not fetch Railway workspaceId — please check API token permissions.")

WORKSPACE_ID = workspaces[0]["id"]
print(f"  Workspace: {workspaces[0]['name']} ({WORKSPACE_ID})")

create_project = """
mutation CreateProject($input: ProjectCreateInput!) {
  projectCreate(input: $input) {
    id
    name
  }
}
"""
project = railway(create_project, {
    "input": {
        "name": "kynara",
        "description": "Kynara — AI Agent Permission System",
        "workspaceId": WORKSPACE_ID,
    }
})["projectCreate"]
PROJECT_ID = project["id"]
print(f"  Created project: {project['name']} ({PROJECT_ID})")

# ── Step 3: Add Postgres database ─────────────────────────────────────────────

banner("Step 3 — Adding Postgres database")

# Get the default environment ID
env_q = """
query Envs($projectId: String!) {
  project(id: $projectId) {
    environments { edges { node { id name } } }
  }
}
"""
envs = railway(env_q, {"projectId": PROJECT_ID})["project"]["environments"]["edges"]
ENV_ID = envs[0]["node"]["id"]
ENV_NAME = envs[0]["node"]["name"]
print(f"  Environment: {ENV_NAME} ({ENV_ID})")

# Create Postgres via serviceCreate with the Railway Postgres template
create_db = """
mutation CreatePostgres($projectId: String!, $environmentId: String!) {
  serviceCreate(input: {
    projectId: $projectId
    name: "Postgres"
    source: { image: "ghcr.io/railwayapp-templates/postgres-ssl:edge" }
  }) {
    id
    name
  }
}
"""
try:
    db = railway(create_db, {"projectId": PROJECT_ID, "environmentId": ENV_ID})
    print(f"  Postgres service created: {db['serviceCreate']['id']}")
    print("  NOTE: Go to Railway dashboard → Postgres service → Variables to get DATABASE_URL")
except Exception as e:
    print(f"  Postgres auto-create failed ({e})")
    print("  ACTION: In Railway dashboard → New Service → Database → PostgreSQL")

# ── Step 4: Generate secrets ──────────────────────────────────────────────────

banner("Step 4 — Generating fresh secrets")

JWT_SECRET        = gen_secret(64)
ENCRYPTION_KEY    = gen_secret(32)
SESSION_SECRET    = gen_secret(48)
WEBHOOK_SECRET    = "whsec_" + gen_secret(32)

print("  JWT_SECRET:        generated ✓")
print("  ENCRYPTION_KEY:    generated ✓")
print("  SESSION_SECRET:    generated ✓")
print("  WEBHOOK_SECRET:    generated ✓")

# ── Step 5: Create backend service ────────────────────────────────────────────

banner("Step 5 — Creating backend service")

# NOTE: Railway service creation via API requires a source (GitHub repo or Docker image).
# We'll create a placeholder and print instructions to link your repo.

print("""
  ACTION REQUIRED — link your GitHub repo to Railway:

  1. Push the Kynara codebase to a new GitHub repo:
       cd "C:\\Users\\vitan\\Documents\\AI_Labs\\AgentGov\\Kynara"
       git init
       git add .
       git commit -m "init: Kynara AI Agent Permission System"
       gh repo create kynara-hq/kynara --private --push --source=.

  2. In Railway dashboard (railway.app/project/{PROJECT_ID}):
       → New Service → GitHub Repo → select kynara-hq/kynara
       → Set Root Directory: backend   (for API service)
       → Add another service, Root Directory: frontend   (for web)

  After linking, come back — the env vars below will be ready to paste.
""".format(PROJECT_ID=PROJECT_ID))

# ── Step 6: Set up Resend domain ──────────────────────────────────────────────

banner("Step 6 — Setting up Resend email domain")

try:
    domain_resp = resend("POST", "/domains", {"name": BRAND_DOMAIN, "region": "us-east-1"})
    domain_id = domain_resp["id"]
    dns_records = domain_resp.get("records", [])
    print(f"  Domain '{BRAND_DOMAIN}' added to Resend (id: {domain_id})")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"  Domain already registered in Resend")
        domains = resend("GET", "/domains")
        domain_id = next((d["id"] for d in domains.get("data", []) if d["name"] == BRAND_DOMAIN), None)
        dns_records = []
    else:
        print(f"  WARN: Resend domain setup failed: {e}")
        domain_id = None
        dns_records = []

# ── Step 7: Print everything ──────────────────────────────────────────────────

banner("Step 7 — Environment Variables (add to Railway backend service)")

env_vars = {
    # App
    "APP_URL":           APP_URL,
    "API_URL":           API_URL,
    "ENVIRONMENT":       "production",
    # Auth
    "JWT_SECRET":        JWT_SECRET,
    "ENCRYPTION_KEY":    ENCRYPTION_KEY,
    "SESSION_SECRET":    SESSION_SECRET,
    # Email (Resend)
    "RESEND_API_KEY":    RESEND_API_KEY,
    "SMTP_FROM":         f"noreply@{BRAND_DOMAIN}",
    "EMAIL_FROM_NAME":   BRAND_NAME,
    # Webhooks
    "WEBHOOK_SECRET":    WEBHOOK_SECRET,
    # CORS
    "ALLOWED_ORIGINS":   APP_URL,
}

print("\n  Copy these into Railway → Service → Variables:\n")
for k, v in env_vars.items():
    print(f"  {k}={v}")

print(f"\n  Also add: DATABASE_URL=<from Railway Postgres plugin>")
print(f"  (Railway auto-injects ${{DATABASE_URL}} if you reference it as a variable)")

# ── Step 8: DNS records ───────────────────────────────────────────────────────

banner("Step 8 — DNS Records to add for kynaraai.com")

print("""
  Add these records in your DNS provider (Cloudflare/Namecheap/etc.):

  ┌─────────────────────────────────────────────────────────────────┐
  │ Type   Name              Value                                   │
  ├─────────────────────────────────────────────────────────────────┤
  │ CNAME  www               <railway-frontend-domain>.up.railway.app│
  │ CNAME  api               <railway-backend-domain>.up.railway.app │
  └─────────────────────────────────────────────────────────────────┘

  (Replace the values with the actual Railway service domains from
   Railway dashboard → Service → Settings → Networking → Generate Domain)
""")

if dns_records:
    print("  Resend DKIM / SPF / DMARC records:\n")
    for rec in dns_records:
        print(f"  Type: {rec.get('type','')}")
        print(f"  Name: {rec.get('name','')}")
        print(f"  Value: {rec.get('value','')}")
        print()
else:
    print("  Resend DNS records: log in to resend.com → Domains → kynaraai.com")
    print("  and copy the DKIM, SPF, and DMARC records shown there.\n")

# ── Save env vars to .env.kynara ──────────────────────────────────────────────

env_file = os.path.join(os.path.dirname(__file__), ".env.kynara")
with open(env_file, "w") as f:
    f.write("# Kynara production environment variables\n")
    f.write("# DO NOT COMMIT THIS FILE\n\n")
    for k, v in env_vars.items():
        f.write(f"{k}={v}\n")
    f.write("DATABASE_URL=<from Railway Postgres plugin>\n")

print(f"\n  Saved to: {env_file}")
print("  (Keep this file safe — do not commit it to git)\n")

banner("Setup complete!")
print(f"""
  Summary:
    Railway Project ID : {PROJECT_ID}
    Railway Env ID     : {ENV_ID}
    Resend Domain ID   : {domain_id or 'see resend.com'}

  Remaining manual steps:
    1. Push Kynara code to GitHub (see Step 5 above)
    2. Link GitHub repo to Railway services (backend + frontend)
    3. Add DATABASE_URL to Railway backend service
    4. Add the DNS records above to kynaraai.com
    5. In Railway: add custom domains
         api.kynaraai.com  → backend service
         kynaraai.com      → frontend service
    6. Run database migrations:
         railway run alembic upgrade head
         (from the Kynara/backend directory)
    7. Rotate your Railway token at railway.app/account/tokens
""")
