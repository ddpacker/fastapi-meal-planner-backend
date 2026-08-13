---
name: auth-plan
overview: >
  Implement authentication for the meal planner backend. Email/password auth with JWT is
  already live. The remaining work is Google OIDC for social login, token invalidation on
  logout, and dedicated auth endpoint tests.
todos:
  - id: setup-jwt
    content: >
      Set up JWT token issuance and validation middleware.
      Implemented in app/core/security.py (create_access_token, decode_token using python-jose/HS256)
      and app/core/deps.py (get_current_user FastAPI dependency). Email/password register + login
      live at POST /auth/register and POST /auth/login in app/routers/auth.py.
    status: done

  - id: user-schema
    content: >
      Create Pydantic schemas for user accounts.
      Implemented in app/schemas/auth.py: UserBase, UserCreate (email + 8-128 char password),
      UserRead, Token, and TokenPayload.
    status: done
    dependencies:
      - setup-jwt

  - id: user-persistence
    content: >
      Create a user record on first auth and perform a lookup on subsequent logins.
      User SQLAlchemy model in app/models/user.py (id, email, password_hash, timestamps,
      relationships to meal_plan_weeks/chat_sessions/recipes). Register endpoint creates the
      row; login endpoint does the lookup.
    status: done
    dependencies:
      - user-schema

  - id: google-oidc
    content: >
      Set up Google OAuth 2.0 / OIDC callback flow for social login.
      Implemented with httpx + manual OIDC in app/services/google_oidc.py; settings
      GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI in app/config.py; endpoints
      GET /auth/google and GET /auth/google/callback in app/routers/auth.py; User.google_sub
       email match links existing accounts (409 if email is tied to another google_sub).
    status: done
    dependencies:
      - user-persistence

  - id: logout
    content: >
      Invalidate the token and clear session on logout.
      Implement POST /auth/logout. Because JWTs are stateless, invalidation requires a server-side
      denylist: store revoked JTI (JWT ID) values in Redis (or a DB table) with TTL equal to the
      token's remaining lifetime. Add jti claim to create_access_token. Check denylist in
      get_current_user before accepting a token.
    status: done
    dependencies:
      - user-persistence

  - id: auth-tests
    content: >
      Add dedicated pytest tests for the auth router and security utilities.
      Create tests/routers/test_auth.py covering: successful register, duplicate email 409,
      login returns valid JWT, login with bad password 401, protected endpoint rejects missing
      token 401. Create tests/core/test_security.py covering: create_access_token round-trips,
      decode_token rejects expired/tampered tokens. Use the existing conftest.py fixtures.
      Tests for other routers already assert 401 on missing auth headers.
    status: done
    dependencies:
      - setup-jwt
    
  - id: cors-middleware
    content: >
      Add CORSMiddleware to main.py with allowed origins driven by a
      CORS_ALLOWED_ORIGINS setting (list[str]) in app/config.py. Defaults to []
      in production. Local dev overrides to [http://localhost:5173] via .env.
      Add CORS_ALLOWED_ORIGINS to .env.example.
    status: done
    dependencies:
      - setup-jwt
---

## Conventions

Cross-cutting rules live in [_conventions.md](_conventions.md). Auth is the mechanism behind
[CONV-AUTH-OWNERSHIP](_conventions.md#conv-auth-ownership) — `get_current_user` resolves the
`current_user` that every other plan filters by.

Task status is tracked in the `todos:` frontmatter above; per-task key files are named in each
todo's `content`.

---

## Implementation notes

### What exists today

**`app/core/security.py`**

- `verify_password(plain, hashed)` — bcrypt via passlib
- `get_password_hash(password)` — bcrypt hash
- `create_access_token(data, expires_delta)` — HS256 JWT via python-jose
- `decode_token(token)` — validates and decodes JWT; raises 401 on failure

**`app/core/deps.py`**

- `oauth2_scheme` — `OAuth2PasswordBearer(tokenUrl="/auth/login")`
- `get_current_user(token, db)` — extracts `sub` from JWT, returns `User` or raises 401

**`app/routers/auth.py`**

- `POST /auth/register` — validates email uniqueness, hashes password, creates User
- `POST /auth/login` — accepts `OAuth2PasswordRequestForm`, returns `Token`

**`app/schemas/auth.py`**

- `UserBase`, `UserCreate` (email + password 8–128 chars), `UserRead`, `Token`, `TokenPayload`

**`app/models/user.py`**

- `User` — `id`, `email` (unique, indexed), `password_hash`, `created_at`, `updated_at`
- Relationships: `meal_plan_weeks`, `chat_sessions`, `recipes`

**`app/config.py`** — `secret_key`, `algorithm = "HS256"`, `access_token_expire_minutes = 1440`

### Google OIDC additions required

```python
# app/config.py additions
google_client_id: str
google_client_secret: str
google_redirect_uri: str  # e.g. http://localhost:8000/auth/google/callback

# app/models/user.py addition
google_sub: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
```

### Logout denylist approach

Add `jti` (UUID) to every issued token. On logout, store the `jti` in a `revoked_tokens` table
(or Redis key) with TTL = token expiry. `get_current_user` checks the denylist before accepting.
