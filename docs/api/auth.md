# Authentication

Bremen uses short-lived JWT Bearer tokens for API authentication.

## POST /demo/api/auth/token

Issue an access token and a refresh token.

### Request

- **Content-Type:** `application/json`
- **Auth:** None

**Body:**

```json
{
  "username": "<USERNAME>",
  "password": "<PASSWORD>"
}
```

### Response — 200 OK

```json
{
  "access_token": "<ACCESS_TOKEN>",
  "refresh_token": "<REFRESH_TOKEN>",
  "token_type": "Bearer",
  "expires_in": 900,
  "technical_demo_only": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | Short-lived JWT (default 900 s / 15 min) |
| `refresh_token` | string | Longer-lived JWT for silent refresh |
| `token_type` | string | Always `"Bearer"` |
| `expires_in` | int | Access token lifetime in seconds |

### Example

```bash
export BASE="https://bremen.matur.co.uk:443"

curl -sS -L \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/auth/token" \
  -d '{"username":"<USERNAME>","password":"<PASSWORD>"}' \
  | tee /tmp/bremen-token.json | jq .

export ACCESS="$(jq -r '.access_token // empty' /tmp/bremen-token.json)"
echo "ACCESS_LEN=${#ACCESS}"
```

### Errors

| Status | Meaning |
|--------|---------|
| 401 | `{"error":"Authentication failed"}` — wrong credentials or malformed body |
| 503 | Auth is not configured in this deployment |

## POST /demo/api/auth/refresh

Refresh an expired access token using a valid refresh token.

### Request

- **Content-Type:** `application/json`
- **Auth:** None

**Body:**

```json
{
  "refresh_token": "<REFRESH_TOKEN>"
}
```

### Response — 200 OK

Same shape as `/demo/api/auth/token` above.

### Example

```bash
curl -sS -L \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/auth/refresh" \
  -d "$(jq -n --arg rt "$(jq -r '.refresh_token' /tmp/bremen-token.json)" \
        '{refresh_token: $rt}')" \
  | jq .
```

## Using the Access Token

Include the token in the `Authorization` header for every protected request:

```bash
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/demo/api/h5/containers"
```

## Security Notes

- Passwords are stored as argon2id hashes server-side; **never** transmit or log plaintext passwords.
- The JWT signing secret (`BREMEN_AUTH_JWT_SECRET`) must be at least 32 characters.
- Access tokens are short-lived (default 900 s). Use the refresh endpoint to obtain new tokens before expiry.
- Refresh tokens are longer-lived (default 604 800 s / 7 days).

## Runtime Configuration

Auth is configured via environment variables on the server:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BREMEN_AUTH_ENABLED` | Yes | `false` | Set to `"true"` to enable auth |
| `BREMEN_AUTH_USERNAME` | When enabled | — | Login username |
| `BREMEN_AUTH_PASSWORD_HASH` | When enabled | — | Argon2id or bcrypt hash of the password |
| `BREMEN_AUTH_JWT_SECRET` | When enabled | — | JWT signing secret (≥ 32 chars) |
| `BREMEN_AUTH_ACCESS_TTL_SECONDS` | No | 900 | Access token TTL (60–86 400) |
| `BREMEN_AUTH_REFRESH_TTL_SECONDS` | No | 604 800 | Refresh token TTL (3 600–2 592 000) |
| `BREMEN_AUTH_JWT_ISSUER` | No | `bremen-demo` | JWT issuer claim |
| `BREMEN_AUTH_JWT_AUDIENCE` | No | `bremen-api` | JWT audience claim |

> The password hash is stored in the environment, not the plaintext password.
> Generate a hash with:
> ```bash
> python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('your-password'))"
> ```
