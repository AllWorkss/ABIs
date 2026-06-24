# ============================================================
#  auth_ui.py — Gradio Auth UI Components
#  Login/Signup/Profile screens that wrap auth.py
# ============================================================

import gradio as gr
from auth import (
    signup_user, login_user, verify_jwt_token,
    get_google_oauth_url, revoke_token,
    save_user_data, load_user_data, list_user_data,
    get_user_profile, init_database,
)

AUTH_CSS = """
.auth-wrap{max-width:420px;margin:60px auto;padding:0 16px;}
.auth-card{background:var(--color-background-primary);border:0.5px solid var(--color-border-tertiary);
           border-radius:var(--border-radius-lg);padding:32px;}
.auth-logo{text-align:center;margin-bottom:24px;}
.auth-logo-t{font-size:22px;font-weight:600;color:#1D9E75;}
.auth-logo-s{font-size:12px;color:var(--color-text-secondary);margin-top:4px;}
.auth-divider{display:flex;align-items:center;gap:12px;margin:16px 0;
              font-size:12px;color:var(--color-text-secondary);}
.auth-divider::before,.auth-divider::after{content:"";flex:1;
    height:0.5px;background:var(--color-border-tertiary);}
.google-btn{width:100%;padding:10px;border:0.5px solid var(--color-border-secondary);
            border-radius:var(--border-radius-md);background:var(--color-background-primary);
            display:flex;align-items:center;justify-content:center;gap:10px;
            cursor:pointer;font-size:13px;color:var(--color-text-primary);
            transition:background 0.15s;}
.google-btn:hover{background:var(--color-background-secondary);}
.plan-badge{display:inline-block;background:#E1F5EE;color:#0F6E56;
            font-size:10px;font-weight:600;padding:2px 8px;
            border-radius:20px;border:1px solid #9FE1CB;}
"""

def build_auth_ui():
    """
    Returns a Gradio Blocks component with full auth UI.
    Returns: (auth_block, token_state, user_state)
    """
    with gr.Blocks(css=AUTH_CSS) as auth_block:

        token_state = gr.State("")   # JWT token
        user_state  = gr.State({})   # user dict

        # ── Auth screen (shown when logged out) ──
        with gr.Column(visible=True) as auth_screen:
            gr.HTML("""
<div class="auth-wrap">
  <div class="auth-logo">
    <div class="auth-logo-t">Allworkss BI Suite</div>
    <div class="auth-logo-s">360° AI for Indian SMEs</div>
  </div>
</div>""")

            with gr.Tabs() as auth_tabs:

                # ── Login Tab ──
                with gr.Tab("Sign In"):
                    gr.HTML('<div style="margin-bottom:16px;">')

                    # Google OAuth button
                    google_url = get_google_oauth_url()
                    if google_url:
                        gr.HTML(f"""
<a href="{google_url}" style="text-decoration:none;">
  <div class="google-btn">
    <svg width="18" height="18" viewBox="0 0 18 18">
      <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"/>
      <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"/>
      <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z"/>
      <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z"/>
    </svg>
    Continue with Google
  </div>
</a>
<div class="auth-divider">or sign in with email</div>""")

                    li_email = gr.Textbox(label="Email", placeholder="you@company.com", type="email")
                    li_pass  = gr.Textbox(label="Password", placeholder="Your password", type="password")
                    li_btn   = gr.Button("Sign In", variant="primary", elem_classes=["fw"])
                    li_msg   = gr.Markdown(visible=False)

                # ── Signup Tab ──
                with gr.Tab("Create Account"):
                    su_name  = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Kumar")
                    su_email = gr.Textbox(label="Email", placeholder="you@company.com", type="email")
                    su_pass  = gr.Textbox(label="Password", placeholder="Min 8 chars, upper, lower, number, symbol",
                                          type="password")
                    su_pass2 = gr.Textbox(label="Confirm Password", type="password")
                    gr.Markdown("*By creating an account you agree to our Terms of Service.*")
                    su_btn   = gr.Button("Create Account", variant="primary", elem_classes=["fw"])
                    su_msg   = gr.Markdown(visible=False)

        # ── App screen (shown when logged in) ──
        with gr.Column(visible=False) as app_screen:
            user_header = gr.HTML("")
            # (The main app content goes here — passed in from app.py)
            yield_placeholder = gr.HTML(
                "<div id='app-content-placeholder'></div>",
                label="app"
            )

        # ── Auth Handlers ──────────────────────────────

        def do_login(email, password):
            result = login_user(email, password)
            if result["success"]:
                user  = result["user"]
                token = result["token"]
                header_html = _build_user_header(user)
                return (
                    gr.update(visible=False),    # hide auth screen
                    gr.update(visible=True),     # show app screen
                    token,                       # store token
                    user,                        # store user
                    gr.update(value=header_html),# update header
                    gr.update(visible=False),    # hide error
                )
            else:
                return (
                    gr.update(visible=True),
                    gr.update(visible=False),
                    "",
                    {},
                    gr.update(value=""),
                    gr.update(value=f"❌ {result['error']}", visible=True),
                )

        def do_signup(name, email, password, password2):
            if password != password2:
                return (
                    gr.update(visible=True), gr.update(visible=False),
                    "", {}, gr.update(value=""),
                    gr.update(value="❌ Passwords do not match", visible=True),
                )
            result = signup_user(email, password, name)
            if result["success"]:
                user  = result["user"]
                token = result["token"]
                header_html = _build_user_header(user)
                return (
                    gr.update(visible=False),
                    gr.update(visible=True),
                    token, user,
                    gr.update(value=header_html),
                    gr.update(visible=False),
                )
            else:
                return (
                    gr.update(visible=True), gr.update(visible=False),
                    "", {}, gr.update(value=""),
                    gr.update(value=f"❌ {result['error']}", visible=True),
                )

        shared_outputs = [auth_screen, app_screen, token_state, user_state,
                          user_header, li_msg]

        li_btn.click(fn=do_login,   inputs=[li_email, li_pass],            outputs=shared_outputs)
        su_btn.click(fn=do_signup,  inputs=[su_name, su_email, su_pass, su_pass2],
                     outputs=[auth_screen, app_screen, token_state, user_state, user_header, su_msg])

    return auth_block, token_state, user_state


def _build_user_header(user: dict) -> str:
    """Builds the top-right user info bar shown after login."""
    initials = "".join(w[0].upper() for w in user.get("full_name","?").split()[:2]) or "?"
    plan     = user.get("plan", "free")
    return f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            padding:10px 20px;background:var(--color-background-secondary);
            border-bottom:0.5px solid var(--color-border-tertiary);
            font-family:system-ui,sans-serif;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:32px;height:32px;border-radius:50%;background:#1D9E75;
                display:flex;align-items:center;justify-content:center;
                font-size:13px;font-weight:600;color:#fff;">{initials}</div>
    <div>
      <div style="font-size:13px;font-weight:500;color:var(--color-text-primary);">{user.get('full_name','User')}</div>
      <div style="font-size:11px;color:var(--color-text-secondary);">{user.get('email','')}</div>
    </div>
    <span style="background:#E1F5EE;color:#0F6E56;font-size:10px;font-weight:600;
                 padding:2px 8px;border-radius:20px;border:1px solid #9FE1CB;">
      {plan.upper()}
    </span>
  </div>
  <div style="font-size:12px;color:var(--color-text-secondary);">
    ✅ Logged in · Your data is private and isolated
  </div>
</div>"""


# ════════════════════════════════════════════════════════════
# CONVENIENCE WRAPPERS — use in app.py handlers
# ════════════════════════════════════════════════════════════

def require_auth(token: str):
    """
    Call at the start of any handler that needs authentication.
    Returns (user_id, error_message).
    If error_message is not None, show it to the user and return early.
    """
    if not token:
        return None, "⚠️ Please log in to use this feature."
    result = verify_jwt_token(token)
    if not result["valid"]:
        return None, f"⚠️ {result['error']}"
    return result["user_id"], None


def save_analysis(token: str, module: str, key: str, data: dict) -> str:
    """Saves analysis result for the logged-in user. Returns status message."""
    user_id, err = require_auth(token)
    if err:
        return err
    success = save_user_data(user_id, module, key, data)
    return "✅ Saved to your account." if success else "❌ Failed to save."


def load_analysis(token: str, module: str, key: str) -> tuple:
    """Loads saved analysis for the logged-in user. Returns (data, status)."""
    user_id, err = require_auth(token)
    if err:
        return {}, err
    result = load_user_data(user_id, module, key)
    if result:
        return result["data"], f"✅ Loaded (saved {result['updated_at'][:10]})"
    return {}, "No saved data found for this key."
