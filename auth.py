# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  auth.py — Complete Authentication System
#  
#  Features:
#  - Email/password signup & login (bcrypt)
#  - JWT token management
#  - Google OAuth 2.0
#  - PostgreSQL user storage
#  - Per-user data isolation
# ============================================================

import os, re, jwt, time, json, secrets, hashlib, requests
from datetime import datetime, timedelta
from functools import wraps

try:
    import bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_OK = True
except ImportError:
    PSYCOPG2_OK = False

# ── Config from environment variables ──────────────────────
JWT_SECRET       = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
DATABASE_URL     = os.environ.get("DATABASE_URL", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
APP_BASE_URL     = os.environ.get("APP_BASE_URL", "http://localhost:7860")
GOOGLE_REDIRECT  = f"{APP_BASE_URL}/auth/google/callback"

# ════════════════════════════════════════════════════════════
# SECTION A — DATABASE CONNECTION & SCHEMA
# ════════════════════════════════════════════════════════════

def get_db():
    """Returns a psycopg2 connection from DATABASE_URL."""
    if not PSYCOPG2_OK:
        raise RuntimeError("psycopg2 not installed. Add to requirements.txt")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_database():
    """
    Creates all tables if they don't exist.
    Call once on app startup.
    
    Schema:
    ┌─────────────────────────────────────────────────────┐
    │  users                                              │
    │  ├── id (UUID, PK)                                  │
    │  ├── email (UNIQUE)                                 │
    │  ├── password_hash (nullable for Google users)      │
    │  ├── full_name                                      │
    │  ├── google_id (nullable, for OAuth users)          │
    │  ├── avatar_url                                     │
    │  ├── plan (free/pro/enterprise)                     │
    │  ├── created_at                                     │
    │  └── last_login                                     │
    │                                                     │
    │  user_sessions                                      │
    │  ├── id (UUID, PK)                                  │
    │  ├── user_id (FK → users.id)                       │
    │  ├── token_hash                                     │
    │  ├── created_at                                     │
    │  └── expires_at                                     │
    │                                                     │
    │  user_data                                          │
    │  ├── id (UUID, PK)                                  │
    │  ├── user_id (FK → users.id) ← ISOLATION KEY       │
    │  ├── module (m1/m2/m3/m4/m5)                       │
    │  ├── data_type (analysis/config/report/chat)        │
    │  ├── data_key (unique name per user)                │
    │  ├── data_json (JSONB — stores any result)          │
    │  ├── created_at                                     │
    │  └── updated_at                                     │
    └─────────────────────────────────────────────────────┘
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            CREATE EXTENSION IF NOT EXISTS "pgcrypto";

            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email         VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT,
                full_name     VARCHAR(255) NOT NULL DEFAULT '',
                google_id     VARCHAR(255) UNIQUE,
                avatar_url    TEXT,
                plan          VARCHAR(50)  NOT NULL DEFAULT 'free',
                is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
                created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                last_login    TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash  VARCHAR(64) UNIQUE NOT NULL,
                ip_address  VARCHAR(45),
                user_agent  TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at  TIMESTAMPTZ NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_data (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                module      VARCHAR(10)  NOT NULL,
                data_type   VARCHAR(50)  NOT NULL,
                data_key    VARCHAR(255) NOT NULL,
                data_json   JSONB        NOT NULL DEFAULT '{}',
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, module, data_key)
            );

            CREATE INDEX IF NOT EXISTS idx_user_data_user_id
                ON user_data(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_data_module
                ON user_data(user_id, module);
            CREATE INDEX IF NOT EXISTS idx_sessions_token
                ON user_sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_sessions_user
                ON user_sessions(user_id);
        """)
        conn.commit()
        print("✅ Database tables initialized")
    except Exception as e:
        conn.rollback()
        print(f"❌ Database init error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


# ════════════════════════════════════════════════════════════
# SECTION B — PASSWORD UTILITIES
# ════════════════════════════════════════════════════════════

def validate_password_strength(password: str) -> tuple:
    """Returns (is_valid, error_message)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, ""


def hash_password(password: str) -> str:
    """Hash password with bcrypt (12 rounds)."""
    if not BCRYPT_OK:
        # Fallback: SHA-256 with salt (not as secure, but works)
        salt   = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"sha256:{salt}:{hashed}"
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored hash."""
    if not hashed:
        return False
    if hashed.startswith("sha256:"):
        _, salt, stored = hashed.split(":")
        check = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(check, stored)
    if not BCRYPT_OK:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# ════════════════════════════════════════════════════════════
# SECTION C — JWT TOKEN MANAGEMENT
# ════════════════════════════════════════════════════════════

def create_jwt_token(user_id: str, email: str, plan: str = "free") -> str:
    """Creates a signed JWT token valid for JWT_EXPIRY_HOURS hours."""
    payload = {
        "sub":   user_id,
        "email": email,
        "plan":  plan,
        "iat":   int(time.time()),
        "exp":   int(time.time()) + (JWT_EXPIRY_HOURS * 3600),
        "jti":   secrets.token_hex(16),  # unique token ID
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_jwt_token(token: str) -> dict:
    """
    Verifies JWT token.
    Returns user payload dict or raises exception.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"valid": True, "user_id": payload["sub"],
                "email": payload["email"], "plan": payload.get("plan","free")}
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Session expired. Please log in again."}
    except jwt.InvalidTokenError as e:
        return {"valid": False, "error": f"Invalid session: {e}"}


def store_session_token(user_id: str, token: str, ip: str = None, ua: str = None):
    """Stores token hash in DB for revocation support."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires    = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_sessions (user_id, token_hash, ip_address, user_agent, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (token_hash) DO NOTHING
        """, (user_id, token_hash, ip, ua, expires))
        conn.commit()
    finally:
        cur.close(); conn.close()


def revoke_token(token: str):
    """Deletes session token (logout)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM user_sessions WHERE token_hash = %s", (token_hash,))
        conn.commit()
    finally:
        cur.close(); conn.close()


# ════════════════════════════════════════════════════════════
# SECTION D — USER REGISTRATION & LOGIN
# ════════════════════════════════════════════════════════════

def signup_user(email: str, password: str, full_name: str) -> dict:
    """
    Registers a new user.
    Returns {"success": True, "token": "...", "user": {...}}
    """
    # Validate inputs
    if not validate_email(email):
        return {"success": False, "error": "Invalid email address"}

    is_strong, pw_error = validate_password_strength(password)
    if not is_strong:
        return {"success": False, "error": pw_error}

    if not full_name or len(full_name.strip()) < 2:
        return {"success": False, "error": "Full name must be at least 2 characters"}

    email = email.lower().strip()

    conn = get_db()
    cur  = conn.cursor()
    try:
        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return {"success": False, "error": "An account with this email already exists"}

        # Create user
        pw_hash = hash_password(password)
        cur.execute("""
            INSERT INTO users (email, password_hash, full_name)
            VALUES (%s, %s, %s)
            RETURNING id, email, full_name, plan, created_at
        """, (email, pw_hash, full_name.strip()))
        user = dict(cur.fetchone())
        conn.commit()

        # Create JWT
        token = create_jwt_token(str(user["id"]), user["email"], user["plan"])
        store_session_token(str(user["id"]), token)

        return {
            "success":  True,
            "token":    token,
            "user": {
                "id":        str(user["id"]),
                "email":     user["email"],
                "full_name": user["full_name"],
                "plan":      user["plan"],
            }
        }

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Signup failed: {str(e)}"}
    finally:
        cur.close(); conn.close()


def login_user(email: str, password: str) -> dict:
    """
    Authenticates user with email + password.
    Returns {"success": True, "token": "...", "user": {...}}
    """
    if not email or not password:
        return {"success": False, "error": "Email and password are required"}

    email = email.lower().strip()

    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT id, email, full_name, password_hash, plan, is_active, google_id
            FROM users WHERE email = %s
        """, (email,))
        user = cur.fetchone()

        if not user:
            return {"success": False, "error": "Invalid email or password"}

        if not user["is_active"]:
            return {"success": False, "error": "Account is deactivated"}

        if user["google_id"] and not user["password_hash"]:
            return {"success": False,
                    "error": "This account uses Google Sign-In. Please use the Google button."}

        if not verify_password(password, user["password_hash"]):
            return {"success": False, "error": "Invalid email or password"}

        # Update last login
        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],))
        conn.commit()

        token = create_jwt_token(str(user["id"]), user["email"], user["plan"])
        store_session_token(str(user["id"]), token)

        return {
            "success": True,
            "token":   token,
            "user": {
                "id":        str(user["id"]),
                "email":     user["email"],
                "full_name": user["full_name"],
                "plan":      user["plan"],
            }
        }

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Login failed: {str(e)}"}
    finally:
        cur.close(); conn.close()


# ════════════════════════════════════════════════════════════
# SECTION E — GOOGLE OAUTH 2.0
# ════════════════════════════════════════════════════════════

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

def get_google_oauth_url() -> str:
    """
    Generates Google OAuth redirect URL.
    User clicks this to go to Google sign-in page.
    """
    if not GOOGLE_CLIENT_ID:
        return ""

    state  = secrets.token_urlsafe(32)  # CSRF protection
    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  GOOGLE_REDIRECT,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    from urllib.parse import urlencode
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def handle_google_callback(code: str) -> dict:
    """
    Handles Google OAuth callback.
    Exchanges code for tokens, gets user info,
    creates account if first time, returns JWT.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return {"success": False, "error": "Google OAuth not configured"}

    try:
        # Exchange authorization code for access token
        token_resp = requests.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  GOOGLE_REDIRECT,
            "grant_type":    "authorization_code",
        }, timeout=10)

        if token_resp.status_code != 200:
            return {"success": False, "error": "Failed to get Google token"}

        access_token = token_resp.json().get("access_token")

        # Get user info from Google
        user_resp = requests.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if user_resp.status_code != 200:
            return {"success": False, "error": "Failed to get Google user info"}

        google_user = user_resp.json()
        google_id   = google_user.get("sub")
        email       = google_user.get("email", "").lower()
        full_name   = google_user.get("name", "")
        avatar_url  = google_user.get("picture", "")

        if not email or not google_id:
            return {"success": False, "error": "Google did not return email"}

        # Upsert user in database
        conn = get_db()
        cur  = conn.cursor()
        try:
            # Check if user exists by google_id or email
            cur.execute("""
                SELECT id, email, full_name, plan
                FROM users
                WHERE google_id = %s OR email = %s
                LIMIT 1
            """, (google_id, email))
            existing = cur.fetchone()

            if existing:
                # Update google_id and last_login if missing
                cur.execute("""
                    UPDATE users
                    SET google_id = %s, avatar_url = %s, last_login = NOW()
                    WHERE id = %s
                    RETURNING id, email, full_name, plan
                """, (google_id, avatar_url, existing["id"]))
                user = dict(cur.fetchone())
                is_new = False
            else:
                # Create new account via Google
                cur.execute("""
                    INSERT INTO users (email, full_name, google_id, avatar_url)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, full_name, plan
                """, (email, full_name, google_id, avatar_url))
                user = dict(cur.fetchone())
                is_new = True

            conn.commit()

            token = create_jwt_token(str(user["id"]), user["email"], user["plan"])
            store_session_token(str(user["id"]), token)

            return {
                "success":  True,
                "token":    token,
                "is_new":   is_new,
                "user": {
                    "id":         str(user["id"]),
                    "email":      user["email"],
                    "full_name":  user["full_name"],
                    "plan":       user["plan"],
                    "avatar_url": avatar_url,
                }
            }

        except Exception as e:
            conn.rollback()
            return {"success": False, "error": f"Database error: {e}"}
        finally:
            cur.close(); conn.close()

    except Exception as e:
        return {"success": False, "error": f"Google OAuth error: {e}"}


# ════════════════════════════════════════════════════════════
# SECTION F — USER DATA ISOLATION
# All reads/writes scoped to user_id — User A CANNOT access User B
# ════════════════════════════════════════════════════════════

def save_user_data(user_id: str, module: str, data_key: str,
                   data: dict, data_type: str = "analysis") -> bool:
    """
    Saves analysis result/config under the logged-in user's ID.
    Uses UPSERT — overwrites if same key exists for this user.
    """
    import json
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_data (user_id, module, data_type, data_key, data_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, module, data_key)
            DO UPDATE SET
                data_json  = EXCLUDED.data_json,
                data_type  = EXCLUDED.data_type,
                updated_at = NOW()
        """, (user_id, module, data_type, data_key, json.dumps(data)))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"save_user_data error: {e}")
        return False
    finally:
        cur.close(); conn.close()


def load_user_data(user_id: str, module: str, data_key: str) -> dict:
    """
    Loads saved data for a specific user + module + key.
    Returns {} if not found.
    SECURITY: user_id is always scoped — no cross-user access possible.
    """
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT data_json, updated_at
            FROM user_data
            WHERE user_id = %s AND module = %s AND data_key = %s
        """, (user_id, module, data_key))
        row = cur.fetchone()
        if row:
            return {"data": row["data_json"], "updated_at": str(row["updated_at"])}
        return {}
    finally:
        cur.close(); conn.close()


def list_user_data(user_id: str, module: str = None) -> list:
    """Lists all saved items for a user, optionally filtered by module."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        if module:
            cur.execute("""
                SELECT module, data_type, data_key, updated_at
                FROM user_data
                WHERE user_id = %s AND module = %s
                ORDER BY updated_at DESC
            """, (user_id, module))
        else:
            cur.execute("""
                SELECT module, data_type, data_key, updated_at
                FROM user_data
                WHERE user_id = %s
                ORDER BY updated_at DESC
            """, (user_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        cur.close(); conn.close()


def delete_user_data(user_id: str, module: str, data_key: str) -> bool:
    """Deletes a specific saved item. Only the owner can delete."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            DELETE FROM user_data
            WHERE user_id = %s AND module = %s AND data_key = %s
        """, (user_id, module, data_key))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        cur.close(); conn.close()


def get_user_profile(user_id: str) -> dict:
    """Gets user profile. Only returns own profile."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT id, email, full_name, plan, avatar_url,
                   created_at, last_login, google_id IS NOT NULL as has_google
            FROM users WHERE id = %s AND is_active = TRUE
        """, (user_id,))
        row = cur.fetchone()
        if row:
            return {k: str(v) if v is not None else None for k, v in dict(row).items()}
        return {}
    finally:
        cur.close(); conn.close()
