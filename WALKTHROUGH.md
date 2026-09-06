# Coffee Connoisseur Platform — API Walkthrough

Step-by-step manual exploration of every service. Follow in order — each phase
builds on the previous one. All commands work fully offline except where noted.

---

## Setup

### Start the stack
```bash
docker compose up -d
```

### Verify all services are healthy
```bash
curl -s http://localhost:8001/health  # auth-service
curl -s http://localhost:8002/health  # coffee-service
curl -s http://localhost:8003/health  # security-service
```

All three should return `{"status":"healthy","service":"..."}`.

### Check Celery worker is running
```bash
docker compose logs celery-worker --tail=5
# Should show: "celery@<id> ready."
```

---

## Phase 2 — Auth Service

### 1. Register a consumer user
```bash
curl -s -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "james@coffee.dev",
    "password": "Consumer1!secure",
    "full_name": "James"
  }' | python3 -m json.tool
```

Expected: `201` with `id`, `email`, `role: "CONSUMER"`.

Try a weak password to see validation kick in:
```bash
curl -s -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test2@coffee.dev", "password": "weak"}' \
  | python3 -m json.tool
```

Expected: `422` with a clear validation error — Pydantic rejects it before
the request ever touches the database.

---

### 2. Register an admin user and promote them
```bash
curl -s -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@coffee.dev",
    "password": "Admin1!secure",
    "full_name": "Admin User"
  }' | python3 -m json.tool
```

Promote to ADMIN directly in the database:
```bash
docker compose exec postgres psql -U postgres -d coffee \
  -c "UPDATE users SET role = 'ADMIN' WHERE email = 'admin@coffee.dev';"
```

Register a roaster user (for coffee catalog demos later):
```bash
curl -s -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "roaster@coffee.dev",
    "password": "Roaster1!secure",
    "full_name": "Roaster User"
  }' | python3 -m json.tool
```

Promote to ROASTER:
```bash
docker compose exec postgres psql -U postgres -d coffee \
  -c "UPDATE users SET role = 'ROASTER' WHERE email = 'roaster@coffee.dev';"
```

---

### 3. Login and capture tokens
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "james@coffee.dev", "password": "Consumer1!secure"}' \
  | python3 -m json.tool
```

Expected: `access_token` (15-min JWT) and `refresh_token` (7-day, stored in DB).

Set them as variables:
```bash
CONSUMER_TOKEN="<paste access_token>"
CONSUMER_REFRESH="<paste refresh_token>"
```

Login as admin and roaster too:
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@coffee.dev", "password": "Admin1!secure"}' \
  | python3 -m json.tool

ADMIN_TOKEN="<paste access_token>"

curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "roaster@coffee.dev", "password": "Roaster1!secure"}' \
  | python3 -m json.tool

ROASTER_TOKEN="<paste access_token>"
ROASTER_REFRESH="<paste refresh_token>"
```

---

### 4. Inspect the JWT
Paste your access token at jwt.io (needs internet) or decode it locally:
```bash
echo $CONSUMER_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```

You'll see: `sub` (user ID), `role: "CONSUMER"`, `type: "access"`, `jti`
(unique token ID), `exp` (Unix timestamp 15 minutes from now).

**Talking point:** Role is embedded in the token — no DB lookup on every request.
`type` prevents MFA tokens from being used as access tokens.

---

### 5. Hit a protected endpoint
```bash
# Works — CONSUMER can reach /users/me
curl -s http://localhost:8001/users/me \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  | python3 -m json.tool

# Fails 401 — no token
curl -s http://localhost:8001/users/me | python3 -m json.tool

# Fails 403 — CONSUMER can't reach admin-only endpoint
curl -s http://localhost:8001/users/admin-only \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  | python3 -m json.tool

# Works — ADMIN can reach it
curl -s http://localhost:8001/users/admin-only \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool
```

---

### 6. Refresh token rotation
```bash
curl -s -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$ROASTER_REFRESH\"}" \
  | python3 -m json.tool
```

Expected: a brand-new `access_token` AND `refresh_token`. The old refresh token
is now consumed. Try replaying the old token:

```bash
# Use the ORIGINAL refresh token again — should fail
curl -s -X POST http://localhost:8001/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$ROASTER_REFRESH\"}" \
  | python3 -m json.tool
```

Expected: `401 Invalid or expired refresh token`.

**Talking point:** This is replay attack prevention. If an attacker intercepts
a refresh token and uses it, the legitimate user's next refresh also fails —
both parties get locked out, which is detectable.

---

### 7. Tamper with a JWT
Take your consumer token and change one character in the signature (last segment):
```bash
BAD_TOKEN="${CONSUMER_TOKEN}x"
curl -s http://localhost:8001/users/me \
  -H "Authorization: Bearer $BAD_TOKEN" \
  | python3 -m json.tool
```

Expected: `401 Could not validate credentials`.

---

### 8. SQL injection attempt
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "'"'"' OR '"'"'1'"'"'='"'"'1", "password": "anything"}' \
  | python3 -m json.tool
```

Expected: `401` — treated as a literal wrong email, not interpreted as SQL.
SQLAlchemy parameterizes all queries by default.

---

### 9. MFA enrollment
```bash
# Enroll MFA on the consumer account
curl -s -X POST http://localhost:8001/auth/mfa/enroll \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  | python3 -m json.tool
```

Expected: `secret` (base32 TOTP secret) and `uri` (otpauth:// URL for
authenticator apps). Copy the `secret`.

Confirm enrollment with a live TOTP code:
```bash
# Generate a code from the secret (requires pyotp installed locally,
# or use an authenticator app)
python3 -c "import pyotp; print(pyotp.TOTP('<your_secret>').now())"

curl -s -X POST http://localhost:8001/auth/mfa/confirm \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"code": "<6-digit-code>"}' \
  | python3 -m json.tool
```

---

### 10. Full MFA login flow
```bash
# Step 1 — login returns mfa_token instead of access_token
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "james@coffee.dev", "password": "Consumer1!secure"}' \
  | python3 -m json.tool
```

Expected: `mfa_token` (not an access token). Try using it as an access token:
```bash
MFA_TOKEN="<paste mfa_token>"
curl -s http://localhost:8001/users/me \
  -H "Authorization: Bearer $MFA_TOKEN" \
  | python3 -m json.tool
```

Expected: `401` — `type: "mfa"` tokens are rejected by the auth middleware.

Complete the MFA flow:
```bash
python3 -c "import pyotp; print(pyotp.TOTP('<your_secret>').now())"

curl -s -X POST http://localhost:8001/auth/mfa/verify \
  -H "Content-Type: application/json" \
  -d "{\"mfa_token\": \"$MFA_TOKEN\", \"code\": \"<6-digit-code>\"}" \
  | python3 -m json.tool
```

Expected: full `access_token` + `refresh_token` pair.

---

### 11. Logout
```bash
curl -s -X POST http://localhost:8001/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$CONSUMER_REFRESH\"}" \
  -w "\nHTTP %{http_code}\n"
```

Expected: `204 No Content`. The refresh token is revoked in the DB.

---

## Phase 3 — Coffee Service

### 12. Seed the coffee catalog
```bash
docker compose exec coffee-service python seeds/seed.py
```

Expected: 8 realistic coffees inserted (Ethiopia Yirgacheffe, Colombia Huila, etc.).
Running it twice is safe — idempotent.

---

### 13. Browse the public catalog (no auth required)
```bash
curl -s http://localhost:8002/coffees | python3 -m json.tool
```

```bash
# Paginate
curl -s "http://localhost:8002/coffees?skip=0&limit=3" | python3 -m json.tool

# Filter by roast level
curl -s "http://localhost:8002/coffees?roast_level=light" | python3 -m json.tool
```

Expected: list of coffees with name, origin, roast level, price, tasting notes.
No token needed — the catalog is public.

---

### 14. Get a single coffee
```bash
# Grab an ID from the list above
COFFEE_ID="<paste a coffee id>"
curl -s "http://localhost:8002/coffees/$COFFEE_ID" | python3 -m json.tool
```

---

### 15. RBAC on coffee creation
```bash
# Fails 403 — CONSUMER can't create coffees
curl -s -X POST http://localhost:8002/coffees \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Coffee",
    "origin": "Brazil",
    "roast_level": "medium",
    "price_usd": 18.00,
    "description": "A test coffee"
  }' | python3 -m json.tool

# Works — ROASTER can create coffees
curl -s -X POST http://localhost:8002/coffees \
  -H "Authorization: Bearer $ROASTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Single Origin",
    "origin": "Kenya",
    "roast_level": "light",
    "price_usd": 22.50,
    "description": "Bright and fruity with blackcurrant notes"
  }' | python3 -m json.tool
```

Expected: `201` with the new coffee. Save the ID:
```bash
MY_COFFEE_ID="<paste new coffee id>"
```

---

### 16. Ownership checks on update/delete
```bash
# Fails 403 — CONSUMER doesn't own this coffee
curl -s -X PATCH "http://localhost:8002/coffees/$MY_COFFEE_ID" \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price_usd": 25.00}' | python3 -m json.tool

# Works — ROASTER owns it
curl -s -X PATCH "http://localhost:8002/coffees/$MY_COFFEE_ID" \
  -H "Authorization: Bearer $ROASTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price_usd": 25.00}' | python3 -m json.tool

# Works — ADMIN can edit anything regardless of ownership
curl -s -X PATCH "http://localhost:8002/coffees/$MY_COFFEE_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price_usd": 27.00}' | python3 -m json.tool
```

---

### 17. Collections
```bash
# Create a collection (any authenticated user)
curl -s -X POST http://localhost:8002/collections \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Favourites",
    "description": "Coffees I keep coming back to"
  }' | python3 -m json.tool

COLLECTION_ID="<paste collection id>"

# Add a coffee to the collection
curl -s -X POST "http://localhost:8002/collections/$COLLECTION_ID/coffees/$COFFEE_ID" \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  | python3 -m json.tool

# List your collections
curl -s http://localhost:8002/collections \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  | python3 -m json.tool

# Collections are user-scoped — another user can't see yours
curl -s http://localhost:8002/collections \
  -H "Authorization: Bearer $ROASTER_TOKEN" \
  | python3 -m json.tool
```

---

### 18. Tasting notes
```bash
# Add a tasting note (auth required)
curl -s -X POST http://localhost:8002/tasting-notes \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"coffee_id\": \"$COFFEE_ID\",
    \"rating\": 5,
    \"notes\": \"Incredible blueberry and jasmine on the nose. Clean finish.\",
    \"brew_method\": \"V60\",
    \"is_public\": true
  }" | python3 -m json.tool

NOTE_ID="<paste note id>"

# Public notes for a coffee — no auth required
curl -s "http://localhost:8002/tasting-notes/coffee/$COFFEE_ID" \
  | python3 -m json.tool
```

---

### 19. AI Recommendations (requires internet + OPENAI_API_KEY)
```bash
# Set your key in .env: OPENAI_API_KEY=sk-...
# Then restart: docker compose up -d coffee-service

curl -s -X POST http://localhost:8002/recommendations \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "preferred_roast": "light",
    "flavor_notes": ["fruity", "floral", "bright"],
    "max_price_usd": 30.00
  }' | python3 -m json.tool
```

Expected: structured JSON recommendations from the catalog with reasoning.

**Talking point:** User preferences are sent as structured JSON in the user
message — never interpolated into the system prompt. This prevents prompt
injection attacks.

---

## Phase 4 — Security Service

### 20. Trigger the rate limiter (5 bad logins → 429)
```bash
for i in 1 2 3 4 5; do
  echo -n "Attempt $i: "
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8001/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "attacker@evil.com", "password": "wrong"}'
  echo
done
```

Expected output: `401 401 401 401 401`

Now attempt a 6th login — this should be blocked:
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "attacker@evil.com", "password": "wrong"}' \
  | python3 -m json.tool
```

Expected: `429` with:
```json
{
  "detail": "Too many failed login attempts. Try again in 900 seconds."
}
```

Also check the response headers for `Retry-After`:
```bash
curl -s -I -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "attacker@evil.com", "password": "wrong"}' \
  | grep -i retry
```

Expected: `retry-after: 900`

**Talking point:** The 429 returns before the request touches the database
or bcrypt. One Redis TTL check vs. 100ms of bcrypt — this is how you prevent
load amplification from a brute-force attack.

---

### 21. List blocked IPs (admin view in security-service)
```bash
curl -s http://localhost:8003/blocked-ips \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool
```

Expected: array with your IP, TTL in seconds.

Try without auth:
```bash
curl -s http://localhost:8003/blocked-ips | python3 -m json.tool
# 401

curl -s http://localhost:8003/blocked-ips \
  -H "Authorization: Bearer $CONSUMER_TOKEN" \
  | python3 -m json.tool
# 403
```

**Talking point:** auth-service wrote these Redis keys; security-service reads
them. No inter-service HTTP call — Redis is the shared state store.

---

### 22. Unblock the IP
```bash
# Use the IP from step 21
BLOCKED_IP="<paste ip from blocked-ips response>"

curl -s -X DELETE "http://localhost:8003/blocked-ips/$BLOCKED_IP" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool
```

Expected: `{"unblocked": true}`.

Verify the IP can log in again:
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "attacker@evil.com", "password": "wrong"}' \
  -w "\nHTTP %{http_code}\n"
```

Expected: back to `401` (not `429`).

---

### 23. Trigger a dependency scan (requires internet for pip-audit)
```bash
curl -s -X POST http://localhost:8003/security/scan-history/trigger \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool
```

Expected: `202 Accepted` with a Celery task ID. The scan runs asynchronously
in the celery-worker container.

Watch the worker pick it up:
```bash
docker compose logs celery-worker --tail=20 -f
```

Wait ~15 seconds for pip-audit to finish, then ctrl-C.

---

### 24. View scan history
```bash
curl -s http://localhost:8003/security/scan-history \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool
```

The most recent scan (97 packages) will show real CVEs found in the pinned
dependencies. Key findings to point out:

- **`python-jose 3.3.0`** — CVE-2024-33663 (algorithm confusion, token forgery)
  and CVE-2024-33664 (JWT bomb / resource exhaustion). Fix: upgrade to 3.4.0.
- **`starlette 0.37.2`** — CVE-2024-47874 (multipart form DoS). Fix: >= 0.40.0.
- **`ecdsa 0.19.1`** — CVE-2024-23342 (Minerva timing attack). No fix available.
- **`pip 25.0.1`** — tar extraction path traversal (build environment only).

**Talking point:** The scanner found a real CVE in the JWT library we're
actually using for authentication. In a real team, this goes straight into the
security backlog as a patch PR.

---

### 25. Get a single scan and resolve it
```bash
# Grab the ID of the most recent scan
SCAN_ID="<paste scan id>"

curl -s "http://localhost:8003/security/scan-history/$SCAN_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool

# Mark it resolved (after hypothetically patching the dependencies)
curl -s -X POST "http://localhost:8003/security/scan-history/$SCAN_ID/resolve" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -m json.tool
```

Expected: `{"resolved": true}`. The scan record now shows `"resolved": true`
in the history.

---

### 26. Run the full test suites
```bash
# auth-service: 40 tests
docker compose exec auth-service python -m pytest tests/ -v

# coffee-service: 45 tests
docker compose exec coffee-service python -m pytest tests/ -v

# security-service: 24 tests (fully offline — uses fakeredis)
docker compose exec security-service python -m pytest tests/ -v
```

Total: 109 tests, all passing.

---

## Quick Reference

| Service          | Port  | Docs                              |
|------------------|-------|-----------------------------------|
| auth-service     | 8001  | http://localhost:8001/docs        |
| coffee-service   | 8002  | http://localhost:8002/docs        |
| security-service | 8003  | http://localhost:8003/docs        |

The `/docs` endpoint (FastAPI's auto-generated Swagger UI) is a good thing to
open in an interview — it shows all endpoints, schemas, and lets you make
live requests. It's generated directly from the code, so it's always in sync.

### Token variables cheatsheet
```bash
CONSUMER_TOKEN=""    # james@coffee.dev
ROASTER_TOKEN=""     # roaster@coffee.dev
ADMIN_TOKEN=""       # admin@coffee.dev
COFFEE_ID=""         # any coffee from GET /coffees
COLLECTION_ID=""     # from POST /collections
NOTE_ID=""           # from POST /tasting-notes
SCAN_ID=""           # from GET /security/scan-history
BLOCKED_IP=""        # from GET /blocked-ips
```

### Re-login if tokens expire (15 min)
```bash
CONSUMER_TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"james@coffee.dev","password":"Consumer1!secure"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

ADMIN_TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@coffee.dev","password":"Admin1!secure"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

ROASTER_TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"roaster@coffee.dev","password":"Roaster1!secure"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```
