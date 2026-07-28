"""Bremen API Documentation Page.

Planned safe API and authentication documentation for Bremen demo UI.
This is documentation only — no auth enforcement is implemented here.
"""


_CSS = r"""
:root{
  --bg-page:#0e1117;--bg-surface:#161b22;--bg-card:#1c2129;
  --text-primary:#e6edf3;--text-secondary:#8b949e;--text-muted:#6e7681;
  --accent:#58a6ff;--accent-hover:#79c0ff;
  --border:#30363d;--border-muted:#21262d;
  --status-available:#3fb950;--status-pending:#d29922;--status-error:#f85149;
  --fs-11:11px;--fs-13:13px;--fs-14:14px;--fs-16:16px;--fs-20:20px;--fs-24:24px;
  --sp-4:4px;--sp-8:8px;--sp-12:12px;--sp-16:16px;--sp-20:20px;--sp-24:24px;
  --radius-card:8px;--shadow-card:0 1px 3px rgba(0,0,0,0.3);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  background:var(--bg-page);color:var(--text-primary);line-height:1.5;
  font-size:var(--fs-14);-webkit-font-smoothing:antialiased}
.docs-page{max-width:920px;margin:0 auto;padding:var(--sp-24) var(--sp-24) var(--sp-24)}
.docs-header{display:flex;align-items:flex-start;justify-content:space-between;
  margin-bottom:var(--sp-24);padding-bottom:var(--sp-16);border-bottom:1px solid var(--border)}
.docs-brand{font-size:var(--fs-24);font-weight:700;color:var(--text-primary)}
.docs-subtitle{font-size:var(--fs-14);color:var(--text-secondary);margin-top:var(--sp-4)}
.docs-nav{display:flex;gap:var(--sp-12);align-items:center;flex-wrap:wrap}
.docs-nav a{font-size:var(--fs-13);color:var(--accent);text-decoration:none}
.docs-nav a:hover{text-decoration:underline}
.docs-section{margin-bottom:var(--sp-24)}
.docs-section-title{font-size:var(--fs-20);font-weight:600;color:var(--text-primary);
  margin-bottom:var(--sp-12);padding-bottom:var(--sp-8);border-bottom:1px solid var(--border)}
.docs-subsection-title{font-size:var(--fs-16);font-weight:600;color:var(--text-primary);
  margin-bottom:var(--sp-8);margin-top:var(--sp-16)}
.docs-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-card);
  box-shadow:var(--shadow-card);padding:var(--sp-16) var(--sp-20);margin-bottom:var(--sp-16)}
.docs-text{color:var(--text-secondary);font-size:var(--fs-14);line-height:1.6;margin-bottom:var(--sp-8)}
.docs-text:last-child{margin-bottom:0}
.docs-list{color:var(--text-secondary);font-size:var(--fs-14);line-height:1.8;
  padding-left:var(--sp-20);margin-bottom:var(--sp-8)}
.docs-list li{margin-bottom:var(--sp-4)}
.docs-code{background:var(--bg-surface);border:1px solid var(--border-muted);
  border-radius:4px;padding:var(--sp-12) var(--sp-16);font-family:monospace;
  font-size:var(--fs-13);color:var(--text-primary);overflow-x:auto;
  margin-bottom:var(--sp-12);white-space:pre;line-height:1.6}
.docs-code-label{font-size:var(--fs-11);color:var(--text-muted);
  text-transform:uppercase;letter-spacing:0.5px;margin-bottom:var(--sp-4);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.docs-badge{display:inline-block;font-size:var(--fs-11);font-weight:600;
  padding:2px var(--sp-8);border-radius:12px;margin-left:var(--sp-8)}
.docs-badge.planned{background:var(--status-pending);color:#0d1117}
.docs-badge.active{background:var(--status-available);color:#0d1117}
.docs-note{background:var(--bg-surface);border-left:3px solid var(--accent);
  padding:var(--sp-12) var(--sp-16);margin:var(--sp-16) 0;border-radius:0 var(--radius-card) var(--radius-card) 0}
.docs-note-text{color:var(--text-secondary);font-size:var(--fs-13)}
.docs-table{width:100%;border-collapse:collapse;margin-bottom:var(--sp-12)}
.docs-table th,.docs-table td{text-align:left;padding:var(--sp-8) var(--sp-12);
  border-bottom:1px solid var(--border);font-size:var(--fs-13)}
.docs-table th{color:var(--text-primary);font-weight:600;background:var(--bg-surface)}
.docs-table td{color:var(--text-secondary)}
.docs-env-var{font-family:monospace;font-size:var(--fs-13);color:var(--accent)}
.docs-disclaimer{background:var(--bg-surface);border:1px solid var(--status-pending);
  border-radius:var(--radius-card);padding:var(--sp-16) var(--sp-20);margin-bottom:var(--sp-24)}
.docs-disclaimer-text{color:var(--status-pending);font-size:var(--fs-13);font-weight:600}
.docs-footer{text-align:center;padding:var(--sp-16) 0;font-size:var(--fs-11);
  color:var(--text-secondary);border-top:1px solid var(--border);margin-top:var(--sp-24)}
.docs-footer a{color:var(--accent);text-decoration:none}
"""


def build_api_docs_page(
    base_url: str = "http://localhost:8000",
    request_id: str = "",
) -> str:
    """Build the Bremen API documentation HTML page.

    Parameters
    ----------
    base_url : Base URL of the service.
    request_id : Request ID for correlation.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen API Documentation — Planned Authentication and Endpoint Reference</title>
<style>{_CSS}</style>
</head>
<body>
<div class="docs-page">

  <div class="docs-header">
    <div>
      <div class="docs-brand">Bremen API Documentation</div>
      <div class="docs-subtitle">Planned authentication model and safe endpoint reference</div>
    </div>
    <div class="docs-nav">
      <a href="/demo">Start</a>
      <a href="/demo/control-room">Control Room</a>
      <a href="/demo/workspace">Workspace</a>
    </div>
  </div>

  <div class="docs-disclaimer">
    <div class="docs-disclaimer-text">
      Technical demo only. Not clinically validated. Not a diagnosis.
      Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.
      Authentication documentation is planning guidance. Enforcement will be implemented in a follow-up PR.
    </div>
  </div>

  <!-- Section 1: API Status -->
  <div class="docs-section">
    <div class="docs-section-title">1. API Status</div>
    <div class="docs-card">
      <div class="docs-text">
        Bremen currently exposes a local demo API for Control Room and Workspace functionality.
        The existing endpoints operate without authentication in the current demo deployment.
      </div>
      <div class="docs-text">
        This document describes the planned authentication model and safe public API surface
        for a future protected deployment. No authentication enforcement is implemented in this release.
      </div>
    </div>
  </div>

  <!-- Section 2: Authentication Model -->
  <div class="docs-section">
    <div class="docs-section-title">2. Authentication Model<span class="docs-badge planned">Planned</span></div>
    <div class="docs-card">
      <div class="docs-subsection-title">Bearer Token Authentication</div>
      <div class="docs-text">
        The planned authentication model uses short-lived JWT access tokens delivered via
        Bearer authentication. Clients obtain tokens by presenting credentials to a token endpoint,
        then include the token in subsequent API requests.
      </div>
      <div class="docs-code-label">Authorization Header</div>
      <div class="docs-code">Authorization: Bearer &lt;access_token&gt;</div>
    </div>
  </div>

  <!-- Section 3: Token Lifecycle -->
  <div class="docs-section">
    <div class="docs-section-title">3. Token Lifecycle<span class="docs-badge planned">Planned</span></div>

    <div class="docs-card">
      <div class="docs-subsection-title">Token Endpoint</div>
      <div class="docs-text">Planned endpoint for obtaining access and refresh tokens:</div>
      <div class="docs-code-label">Request</div>
      <div class="docs-code">POST /api/auth/token
Content-Type: application/json

{{
  "username": "&lt;username&gt;",
  "password": "&lt;password&gt;"
}}</div>
      <div class="docs-code-label">Response</div>
      <div class="docs-code">{{
  "access_token": "&lt;jwt&gt;",
  "refresh_token": "&lt;refresh-token&gt;",
  "token_type": "Bearer",
  "expires_in": 900
}}</div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Refresh Endpoint</div>
      <div class="docs-text">Planned endpoint for obtaining a new access token using a refresh token:</div>
      <div class="docs-code-label">Request</div>
      <div class="docs-code">POST /api/auth/refresh
Content-Type: application/json

{{
  "refresh_token": "&lt;refresh-token&gt;"
}}</div>
      <div class="docs-code-label">Response</div>
      <div class="docs-code">{{
  "access_token": "&lt;jwt&gt;",
  "refresh_token": "&lt;rotated-or-refreshed-token&gt;",
  "token_type": "Bearer",
  "expires_in": 900
}}</div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Token TTLs</div>
      <table class="docs-table">
        <thead>
          <tr><th>Token</th><th>Default TTL</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr><td>Access token</td><td>15 minutes</td><td>Short-lived JWT; included in Authorization header</td></tr>
          <tr><td>Refresh token</td><td>7 days</td><td>Used to obtain new access tokens without re-authentication</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Section 4: Environment Configuration -->
  <div class="docs-section">
    <div class="docs-section-title">4. Environment Configuration<span class="docs-badge planned">Planned</span></div>
    <div class="docs-card">
      <div class="docs-text">
        When authentication is enabled, the following environment variables configure
        the credential and JWT behavior. All are required when
        <span class="docs-env-var">BREMEN_AUTH_ENABLED=true</span>.
      </div>
      <table class="docs-table">
        <thead>
          <tr><th>Variable</th><th>Purpose</th></tr>
        </thead>
        <tbody>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_ENABLED</span></td><td>Set to <code>true</code> to enable authentication enforcement</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_USERNAME</span></td><td>Allowed username for demo/local deployment</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_PASSWORD_HASH</span></td><td>Bcrypt or argon2 password hash (not plaintext)</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_JWT_SECRET</span></td><td>Signing secret for JWT access tokens. Must be independently generated and distinct from the password hash.</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_JWT_ISSUER</span></td><td>JWT issuer claim value</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_JWT_AUDIENCE</span></td><td>JWT audience claim value</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_ACCESS_TTL_SECONDS</span></td><td>Access token TTL in seconds (default: 900)</td></tr>
          <tr><td><span class="docs-env-var">BREMEN_AUTH_REFRESH_TTL_SECONDS</span></td><td>Refresh token TTL in seconds (default: 604800)</td></tr>
        </tbody>
      </table>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Password Handling</div>
      <ul class="docs-list">
        <li>Store password hash, not plaintext password.</li>
        <li>No default credentials in repository.</li>
        <li>No credentials in frontend JavaScript.</li>
        <li>No credentials in logs.</li>
        <li>Auth fails closed if enabled and required env vars are missing.</li>
      </ul>
    </div>
  </div>

  <!-- Section 5: Endpoint Groups -->
  <div class="docs-section">
    <div class="docs-section-title">5. Safe API Endpoint Groups<span class="docs-badge planned">Planned</span></div>
    <div class="docs-card">
      <div class="docs-text">
        The following table documents the intended safe public API surface.
        This is the planned external endpoint shape, not necessarily the current internal demo route shape.
      </div>

      <div class="docs-subsection-title">A. Authentication</div>
      <table class="docs-table">
        <thead><tr><th>Method</th><th>Endpoint</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td>POST</td><td><code>/api/auth/token</code></td><td>Obtain access and refresh tokens</td></tr>
          <tr><td>POST</td><td><code>/api/auth/refresh</code></td><td>Refresh an expiring access token</td></tr>
          <tr><td>POST</td><td><code>/api/auth/logout</code></td><td>Revoke refresh token (planned later)</td></tr>
        </tbody>
      </table>

      <div class="docs-subsection-title">B. Models</div>
      <table class="docs-table">
        <thead><tr><th>Method</th><th>Endpoint</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td>GET</td><td><code>/api/models</code></td><td>List available models</td></tr>
          <tr><td>GET</td><td><code>/api/models/{{model_id}}</code></td><td>Get model details</td></tr>
        </tbody>
      </table>

      <div class="docs-subsection-title">C. Patients / Sources</div>
      <table class="docs-table">
        <thead><tr><th>Method</th><th>Endpoint</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td>GET</td><td><code>/api/patients</code></td><td>List available patient sources</td></tr>
          <tr><td>GET</td><td><code>/api/patients/{{source_id}}</code></td><td>Get patient source details</td></tr>
        </tbody>
      </table>

      <div class="docs-subsection-title">D. Jobs</div>
      <table class="docs-table">
        <thead><tr><th>Method</th><th>Endpoint</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td>POST</td><td><code>/api/jobs</code></td><td>Create analysis job</td></tr>
          <tr><td>GET</td><td><code>/api/jobs</code></td><td>List analysis jobs</td></tr>
          <tr><td>GET</td><td><code>/api/jobs/{{job_id}}</code></td><td>Get job details</td></tr>
          <tr><td>GET</td><td><code>/api/jobs/{{job_id}}/events</code></td><td>Get job events</td></tr>
        </tbody>
      </table>

      <div class="docs-subsection-title">E. Reports</div>
      <table class="docs-table">
        <thead><tr><th>Method</th><th>Endpoint</th><th>Purpose</th></tr></thead>
        <tbody>
          <tr><td>GET</td><td><code>/api/reports/{{job_id}}</code></td><td>Get analysis report</td></tr>
          <tr><td>POST</td><td><code>/api/reports/{{job_id}}/delete</code></td><td>Soft-delete a report</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Section 6: Safe Payload Boundary -->
  <div class="docs-section">
    <div class="docs-section-title">6. Safe Payload Boundary</div>

    <div class="docs-card">
      <div class="docs-subsection-title">Must Not Expose</div>
      <div class="docs-text">The API must never expose the following in any response:</div>
      <ul class="docs-list">
        <li>Raw S3 bucket names</li>
        <li>Raw S3 object keys</li>
        <li>Filesystem paths</li>
        <li>Raw H5 internals</li>
        <li>PHI (protected health information)</li>
        <li>Patient identifiers beyond display-safe demo labels</li>
        <li>Raw exception traces</li>
        <li>Model coefficients</li>
        <li>Feature values</li>
        <li>Full checksums</li>
        <li>Model package internals</li>
        <li>Credentials</li>
        <li>JWT secrets</li>
        <li>Environment variable values</li>
      </ul>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">May Expose</div>
      <div class="docs-text">The API may safely expose:</div>
      <ul class="docs-list">
        <li>Opaque source IDs</li>
        <li>Safe patient display names</li>
        <li>Safe filenames only when already permitted in the demo</li>
        <li><code>stable_source_key</code> as an opaque deterministic identifier</li>
        <li><code>model_id</code></li>
        <li>Model display name</li>
        <li><code>workflow_id</code></li>
        <li><code>job_id</code></li>
        <li>Status</li>
        <li>Safe decision code</li>
        <li>Score and threshold only if already accepted for public demo output</li>
        <li>Report availability status</li>
        <li>Event status labels</li>
      </ul>
    </div>
  </div>

  <!-- Section 7: Example Requests -->
  <div class="docs-section">
    <div class="docs-section-title">7. Example Requests<span class="docs-badge planned">Planned</span></div>
    <div class="docs-card">
      <div class="docs-subsection-title">Obtain a Token</div>
      <div class="docs-code">curl -X POST {base_url}/api/auth/token \\
  -H "Content-Type: application/json" \\
  -d '{{"username": "&lt;username&gt;", "password": "&lt;password&gt;"}}'</div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Use a Protected Endpoint</div>
      <div class="docs-code">curl -X GET {base_url}/api/models \\
  -H "Authorization: Bearer &lt;access_token&gt;"</div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Refresh a Token</div>
      <div class="docs-code">curl -X POST {base_url}/api/auth/refresh \\
  -H "Content-Type: application/json" \\
  -d '{{"refresh_token": "&lt;refresh_token&gt;"}}'</div>
    </div>
  </div>

  <!-- Section 8: Future Production Hardening -->
  <div class="docs-section">
    <div class="docs-section-title">8. Future Production Hardening<span class="docs-badge planned">Planned</span></div>
    <div class="docs-card">
      <div class="docs-text">
        The following items are planned for future production hardening and are not yet implemented:
      </div>
      <ul class="docs-list">
        <li>Database-backed user management</li>
        <li>Per-user roles and scopes</li>
        <li>Token revocation and blacklisting</li>
        <li>Audit event logging for auth actions</li>
        <li>Secret manager integration for JWT signing keys</li>
        <li>Rotation of JWT signing secret</li>
        <li>Rate limiting on token endpoint</li>
        <li>HTTPS enforcement in production</li>
        <li>CORS policy for public API</li>
      </ul>
    </div>
  </div>

  <!-- Section 9: Authentication Architecture Decisions -->
  <div class="docs-section">
    <div class="docs-section-title">9. Authentication Architecture Decisions<span class="docs-badge planned">Planned</span></div>

    <div class="docs-card">
      <div class="docs-subsection-title">Confirmed Current State</div>
      <ul class="docs-list">
        <li>Current <code>/demo/*</code> routes are unauthenticated.</li>
        <li>No JWT or password hashing dependency is currently present.</li>
        <li>Adding auth dependencies (e.g. PyJWT, argon2-cffi, bcrypt) is a future implementation decision.</li>
        <li>Current safety boundary assumes no authenticated fuller-view surface.</li>
      </ul>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Open Decision 1: Auth Scope</div>
      <div class="docs-text">
        <strong>Decision:</strong> Does authentication gate actions only, or unlock a fuller view?
      </div>
      <div class="docs-text">
        <strong>Recommended demo-stage default:</strong> Auth gates actions only.
        Authenticated users still receive the same safe payloads.
        No raw features, full checksums, H5 internals, model internals, S3 references, PHI,
        or raw exceptions are unlocked by login.
      </div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Open Decision 2: Credential Source</div>
      <div class="docs-text">
        <strong>Decision:</strong> Single demo username/password from environment variables.
        Password must be stored as a hash, not plaintext.
      </div>
      <div class="docs-text"><strong>Planned environment variables:</strong></div>
      <ul class="docs-list">
        <li><span class="docs-env-var">BREMEN_AUTH_ENABLED</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_USERNAME</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_PASSWORD_HASH</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_JWT_SECRET</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_JWT_ISSUER</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_JWT_AUDIENCE</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_ACCESS_TTL_SECONDS</span></li>
        <li><span class="docs-env-var">BREMEN_AUTH_REFRESH_TTL_SECONDS</span></li>
      </ul>
      <div class="docs-note">
        <div class="docs-note-text">
          <span class="docs-env-var">BREMEN_AUTH_JWT_SECRET</span> must be independently generated and
          distinct from the password hash.
        </div>
      </div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Open Decision 3: Refresh-Token Storage</div>
      <div class="docs-text"><strong>Options:</strong></div>
      <ul class="docs-list">
        <li><strong>3a.</strong> In-memory store</li>
        <li><strong>3b.</strong> Stateless refresh JWT</li>
        <li><strong>3c.</strong> Persistent store (database)</li>
      </ul>
      <div class="docs-text">
        <strong>Recommended demo-stage default:</strong> Stateless refresh JWT,
        with the explicit trade-off that server-side revocation is not available.
      </div>
      <div class="docs-text">
        Real logout and revocation require server-side token state, which is a later implementation decision.
      </div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">JWT Mechanics</div>
      <table class="docs-table">
        <thead><tr><th>Property</th><th>Planned Value</th></tr></thead>
        <tbody>
          <tr><td>Library</td><td>PyJWT</td></tr>
          <tr><td>Algorithm</td><td>HS256</td></tr>
          <tr><td>Claims</td><td><code>sub</code>, <code>iat</code>, <code>exp</code>, <code>iss</code>, <code>aud</code>, <code>token_type</code></td></tr>
          <tr><td>Optional claim</td><td><code>jti</code></td></tr>
          <tr><td>Access token TTL</td><td>15 minutes (default)</td></tr>
          <tr><td>Refresh token TTL</td><td>7 days (default)</td></tr>
        </tbody>
      </table>
      <div class="docs-note">
        <div class="docs-note-text">
          Decode must explicitly specify allowed algorithms. Implementation must not trust token header algorithm selection.
        </div>
      </div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Safety Invariant</div>
      <div class="docs-text">
        Authentication does not by itself expand data visibility.
        Any future fuller authenticated view requires its own separate PR and safety review.
      </div>
    </div>

    <div class="docs-card">
      <div class="docs-subsection-title">Planning Status</div>
      <div class="docs-text">
        Every auth endpoint and auth enforcement behavior is planned for a follow-up PR.
        Auth is not active in PR0100.
      </div>
    </div>
  </div>

  <div class="docs-note">
    <div class="docs-note-text">
      Authentication documentation is planning guidance. Enforcement will be implemented in a follow-up PR.
    </div>
  </div>

  <div class="docs-footer">
    Bremen &mdash; MRI triage decision support. Technical demo only. Not clinically validated.
    <br>Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.
    <br><a href="/demo/control-room">Control Room</a> &middot; <a href="/demo/workspace">Workspace</a>
  </div>

</div>
</body>
</html>"""
