"""Bremen Login Page — PR0102.

Minimal login page for Bearer/JWT authentication.
"""


def build_login_page(
    base_url: str = "http://localhost:8000",
    auth_enabled: bool = True,
) -> str:
    """Build the login page HTML.

    Parameters
    ----------
    base_url : Base URL of the service.
    auth_enabled : Whether auth is actually enabled on the server.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Sign In</title>
<style>
:root{{
  --bg-page:#0e1117;--bg-surface:#161b22;--bg-card:#1c2129;
  --text-primary:#e6edf3;--text-secondary:#8b949e;
  --accent:#58a6ff;--accent-hover:#79c0ff;
  --border:#30363d;--status-error:#f85149;
  --fs-13:13px;--fs-14:14px;--fs-16:16px;--fs-24:24px;
  --sp-4:4px;--sp-8:8px;--sp-12:12px;--sp-16:16px;--sp-24:24px;
  --sp-32:32px;--radius-card:8px;--shadow-card:0 1px 3px rgba(0,0,0,0.3);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  background:var(--bg-page);color:var(--text-primary);line-height:1.5;
  display:flex;align-items:center;justify-content:center;min-height:100vh}}
.login-card{{background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius-card);box-shadow:var(--shadow-card);
  padding:var(--sp-32);width:100%;max-width:380px;margin:var(--sp-24)}}
.login-brand{{font-size:var(--fs-24);font-weight:700;margin-bottom:var(--sp-4)}}
.login-subtitle{{font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-24)}}
.login-label{{display:block;font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-4)}}
.login-input{{width:100%;padding:var(--sp-8) var(--sp-12);background:var(--bg-surface);
  color:var(--text-primary);border:1px solid var(--border);border-radius:4px;
  font-size:var(--fs-14);margin-bottom:var(--sp-16)}}
.login-input:focus{{outline:none;border-color:var(--accent)}}
.login-btn{{width:100%;padding:var(--sp-8) var(--sp-16);background:var(--accent);
  color:#0d1117;border:none;border-radius:4px;font-size:var(--fs-14);
  font-weight:600;cursor:pointer;margin-bottom:var(--sp-16)}}
.login-btn:hover{{background:var(--accent-hover)}}
.login-btn:disabled{{opacity:0.5;cursor:not-allowed}}
.login-error{{color:var(--status-error);font-size:var(--fs-13);
  margin-bottom:var(--sp-16);min-height:20px}}
.login-footer{{font-size:var(--fs-13);color:var(--text-secondary);text-align:center}}
.login-footer a{{color:var(--accent);text-decoration:none}}
</style>
</head>
<body>
<div class="login-card">
  <div class="login-brand">Bremen</div>
  <div class="login-subtitle">Sign in to perform actions</div>

  <div id="error" class="login-error"></div>

  <form id="loginForm" onsubmit="handleLogin(event)">
    <label class="login-label" for="username">Username</label>
    <input class="login-input" type="text" id="username" name="username"
      autocomplete="username" required autofocus>

    <label class="login-label" for="password">Password</label>
    <input class="login-input" type="password" id="password" name="password"
      autocomplete="current-password" required>

    <button class="login-btn" type="submit" id="submitBtn">Sign in</button>
  </form>

  <div class="login-footer">
    <a href="/demo">Back to Start</a>
    <br><br>
    Technical demo only. Not clinically validated.
    <br>Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.
  </div>
</div>
<script>
(function() {{
  var authEnabled = {'true' if auth_enabled else 'false'};

  if (!authEnabled) {{
    document.getElementById('error').textContent = 'Authentication is not configured on this server.';
    document.getElementById('submitBtn').disabled = true;
    return;
  }}

  // If already logged in, redirect to control room
  var existing = sessionStorage.getItem('bremen_access_token');
  if (existing) {{
    window.location.href = '/demo/control-room';
    return;
  }}
}})();

function handleLogin(e) {{
  e.preventDefault();
  var errorEl = document.getElementById('error');
  var btn = document.getElementById('submitBtn');
  var username = document.getElementById('username').value;
  var password = document.getElementById('password').value;

  errorEl.textContent = '';
  btn.disabled = true;
  btn.textContent = 'Signing in...';

  fetch('{base_url}/demo/api/auth/token', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{username: username, password: password}})
  }})
  .then(function(r) {{ return r.json().then(function(data) {{ return {{status: r.status, data: data}}; }}); }})
  .then(function(result) {{
    if (result.status === 200 && result.data.access_token) {{
      sessionStorage.setItem('bremen_access_token', result.data.access_token);
      sessionStorage.setItem('bremen_refresh_token', result.data.refresh_token);
      sessionStorage.setItem('bremen_token_expires', String(Date.now() + result.data.expires_in * 1000));
      window.location.href = '/demo/control-room';
    }} else {{
      errorEl.textContent = 'Authentication failed';
      btn.disabled = false;
      btn.textContent = 'Sign in';
      document.getElementById('password').value = '';
    }}
  }})
  .catch(function() {{
    errorEl.textContent = 'Authentication failed';
    btn.disabled = false;
    btn.textContent = 'Sign in';
  }});
}}
</script>
</body>
</html>"""
