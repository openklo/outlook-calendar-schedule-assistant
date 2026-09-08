#!/usr/bin/env python3
"""
msgraph_auth.py — shared Microsoft Graph DELEGATED auth (authorization code + PKCE).

Replaces the old app-only client-credentials flow. 2-step onboarding, no local server:
    1) login      → generates PKCE + state, stores the one-time nonce in the profile .env ($HERMES_HOME/.env, or the shared ~/.hermes/.env when unset),
                 prints the sign-in URL (open it in ANY browser, ANY device).
    2) consume    → after sign-in the browser hits an unreachability page at
                 http://127.0.0.1:8765/callback?code=...&state=... (EXPECTED).
                 The user copies that FULL URL from the address bar and runs:
                   msgraph_auth.py consume "<PASTED_URL>"
                  (state is verified, code exchanged with the stored code_verifier,
                   access + refresh tokens persisted to the resolved profile .env ($HERMES_HOME/.env or the shared ~/.hermes/.env when unset)).

Consumers only ever call:  msgraph_auth.get_access_token()
    → returns a valid token, auto-refreshes on expiry, or raises
    NotAuthenticatedError carrying the exact 2-step fix.

Authority: MULTI-TENANT. The auth/token endpoints use the `organizations`
authority by default (work/school accounts only, spanning every tenant):
    https://login.microsoftonline.com/organizations/oauth2/v2.0/...

Requires, in the profile .env ($HERMES_HOME/.env, or the shared ~/.hermes/.env when unset):  MSFT_CLIENT_ID
Optional overrides:  MSFT_AUTHORITY (default "organizations"; e.g. "common",
"consumers", or a tenant guid/domain to scope sign-in instead)
MSFT_TENANT_ID is NOT used to build the authority path under a multi-tenant
authority — it is kept only for diagnostics and may be removed from .env.
"""
import argparse, base64, datetime, hashlib, json, os, secrets, subprocess, sys, time, urllib.parse

# Resolve the secrets file profile-safely. A Hermes profile sets $HERMES_HOME to
# its own home (profiles/<name>), which is where .env lives; $HOME may be
# redirected to a per-profile sandbox, so never trust `~` alone. Fall back to the
# shared ~/.hermes/.env only when $HERMES_HOME is unset (central/non-profile runs).
_hermes_home = os.environ.get("HERMES_HOME", "").strip()
ENV_PATH             = os.path.join(_hermes_home, ".env") if _hermes_home else os.path.expanduser("~/.hermes/.env")
REDIRECT_URI         = os.environ.get("MSFT_REDIRECT_URI", "http://127.0.0.1:8765/callback")
SCOPES               = "offline_access User.Read Mail.Read Calendars.Read Mail.ReadWrite"
AUTHORITY            = "https://login.microsoftonline.com"
DEFAULT_TENANT       = "organizations"       # multi-tenant: work/school accounts only
HERE                 = os.path.abspath(__file__)


# ---------- .env helpers (write-through, preserves other keys/comments) ----------
def _load_env():
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH) as fh:
        for line in fh:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            kv = s.split("=", 1)
            if len(kv) == 2:
                key = kv[0].strip()
                val = kv[1].strip().strip('"').strip("'")
                # .env is CANONICAL for keys it holds: a value present in .env must
                # OVERRIDE any stale value already sitting in the shell env. The old
                # setdefault here let a shell-exported MSFT_REFRESH_TOKEN shadow the
                # freshly-onboarded token, causing a cross-account refresh to clobber
                # .env. Warn (never silent) when a token var is being shadowed so the
                # wrong-account mint is visible instead of invisible.
                # Fail-loud (OPT-IN): when MSGRAPH_AUTH_STRICT is set, surface a
                # cross-account token shadow to stderr instead of silently
                # clobbering. OFF by default so the digest's "empty stderr"
                # contract that the regression suites assert on stays intact.
                if (os.environ.get("MSGRAPH_AUTH_STRICT")
                        and key.startswith("MSFT_") and "TOKEN" in key):
                    prior = os.environ.get(key, "")
                    if prior and prior != val:
                        sys.stderr.write(
                            f"[msgraph_auth] WARN env {key} "
                            f"(len={len(prior)}) shadowed by .env (len={len(val)})\n")
                os.environ[key] = val


def _v(*keys):
    for k in keys:
        val = os.environ.get(k, "") or ""
        if val:
            return val.strip().strip('"').strip("'")
    raise RuntimeError(f"Missing env (checked: {list(keys)})")


CLIENT_ID = lambda: _v("MSFT_CLIENT_ID", "CLIENT_ID")

def _tenant_seg():
    """Authority path segment (multi-tenant). MSFT_AUTHORITY overrides the
    default 'organizations'; MSFT_TENANT_ID is no longer consulted."""
    return (os.environ.get("MSFT_AUTHORITY", "").strip()
            or DEFAULT_TENANT)


def set_env(key: str, value: str):
    """Set/replace KEY=VALUE in .env (never touching comments or unknown keys)."""
    try:
        with open(ENV_PATH) as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        lines = []
    new, hit = f"{key}={value}", False
    out = []
    for ln in lines:
        head = ln.split("=", 1)[0].strip()
        if head == key and "=" in ln and not ln.lstrip().startswith("#"):
            out.append(new + "\n"); hit = True; continue
        out.append(ln)
    if not hit:
        out.append(new + "\n")
    with open(ENV_PATH, "w") as fh:
        fh.writelines(out)
    os.chmod(ENV_PATH, 0o600)    # env holds a refresh token + PKCE nonce


# ---------- PKCE (RFC 7636) ----------
def b64url(data: bytes) -> str:
    """URL-safe base64, no padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_code_verifier(num_bytes: int = 48) -> str:
    """Random 32-64 bytes → base64url (43..128 chars)."""
    if not (32 <= num_bytes <= 64):
        raise ValueError("code verifier must be 32-64 random bytes")
    return b64url(secrets.token_bytes(num_bytes))


def make_code_challenge(verifier: str) -> str:
    """S256: base64url(sha256(ascii(verifier))) → 43 chars."""
    return b64url(hashlib.sha256(verifier.encode("ascii")).digest())


# ---------- offline self-test: PKCE ----------
def selftest_pkce():
    # property checks
    v = make_code_verifier()
    assert 43 <= len(v) <= 128, f"verifier length {len(v)}"
    assert len(make_code_challenge(v)) == 43, "challenge must be 43 chars"
    assert "=" not in b64url(b"\xfb\xff\xfe"), "b64url must strip padding"
    # RFC 7636 Appendix B known vector (S256)
    v_fixed = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    c_fixed = make_code_challenge(v_fixed)
    assert c_fixed == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", \
        f"RFC7636 vector mismatch: {c_fixed}"
    print("SELFTEST-OK pkce")
    return 0


# ---------- offline self-test: authorize URL matches the owner's template ----------
def selftest_url():
    # pin env so the test is independent of the real .env
    os.environ["MSFT_CLIENT_ID"] = "cid-123"
    url = authorize_url("cid-123", "CHALL", "STATE9")
    assert url.startswith("https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize?"), url
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["client_id"] == ["cid-123"]
    assert q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["http://127.0.0.1:8765/callback"]
    assert q["response_mode"] == ["query"]
    assert q["scope"] == ["offline_access User.Read Mail.Read Calendars.Read Mail.ReadWrite"]
    assert q["code_challenge"] == ["CHALL"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["state"] == ["STATE9"]
    print("SELFTEST-OK auth-url")
    return 0


# ---------- offline self-test: multi-tenant authority config (MSFT_AUTHORITY) ----------
def selftest_authority_mode():
    saved_auth = os.environ.get("MSFT_AUTHORITY")
    saved_tenant = os.environ.get("MSFT_TENANT_ID")
    os.environ.pop("MSFT_AUTHORITY", None)
    try:
        # 1) default authority is the multi-tenant organizations endpoint
        u = authorize_url("cid-123", "CHALL", "STATE9")
        assert u.startswith("https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize?"), u
        # 2) MSFT_TENANT_ID must NOT steer the authority path (multi-tenant)
        os.environ["MSFT_TENANT_ID"] = "tid-456"
        u2 = authorize_url("cid-123", "CHALL", "STATE9")
        assert u2 == u, "authority must ignore MSFT_TENANT_ID"
        assert "/organizations/" in u2, "TENANT_ID leaked into path"
        # 3) MSFT_AUTHORITY overrides the default (e.g. back to a tenant / common)
        os.environ["MSFT_AUTHORITY"] = "common"
        u3 = authorize_url("cid-123", "CHALL", "STATE9")
        assert u3.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"), u3
        u4 = authorize_url("cid-123", "CHALL", "STATE9")
        assert u3 == u4, "override unstable"
    finally:
        if saved_auth is None:
            os.environ.pop("MSFT_AUTHORITY", None)
        else:
            os.environ["MSFT_AUTHORITY"] = saved_auth
        if saved_tenant is None:
            os.environ.pop("MSFT_TENANT_ID", None)
        else:
            os.environ["MSFT_TENANT_ID"] = saved_tenant
    print("SELFTEST-OK authority-mode")
    return 0


# ---------- token-endpoint plumbing + authorize-URL builder (Task 3) ----------
def _post_token(form: dict) -> dict:
    """POST to the v2.0 token endpoint (curl, x-www-form-urlencoded)."""
    cmd = ["curl", "-sS", "-X", "POST",
           f"{AUTHORITY}/{_tenant_seg()}/oauth2/v2.0/token",
           "-H", "Content-Type: application/x-www-form-urlencoded"]
    for k, v in form.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"[AUTH] token request failed rc={r.returncode}: "
                           f"{(r.stderr or r.stdout)[:256]}")
    body = json.loads(r.stdout)
    if "access_token" not in body:
        raise RuntimeError(f"[AUTH] no access_token — {body.get('error_description', body)}")
    return body


def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def _fmt_iso_z(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def save_tokens(body: dict):
    """Persist access/refresh/expiry from an AAD token response to .env."""
    expires_in = int(body.get("expires_in", 3600))
    set_env("MSFT_ACCESS_TOKEN", body["access_token"])
    set_env("MSFT_REFRESH_TOKEN", body.get("refresh_token", ""))
    set_env("MSFT_TOKEN_EXPIRES_AT",
             _fmt_iso_z(_now_utc() + datetime.timedelta(seconds=max(expires_in - 60, 1))))


def authorize_url(client_id: str, challenge: str, state: str) -> str:
    """Delegated authorize URL (PKCE S256 + state), multi-tenant by default."""
    q = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": SCOPES,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    return f"{AUTHORITY}/{_tenant_seg()}/oauth2/v2.0/authorize?{q}"


def exchange_code(code: str, verifier: str) -> dict:
    """authorization_code grant: one-time code + PKCE verifier → tokens (saved)."""
    body = _post_token({
        "client_id": CLIENT_ID(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
        "scope": SCOPES,
    })
    save_tokens(body)
    return body


def refresh_access_token(refresh_token: str) -> dict:
    """refresh_token grant → new access token (+ rotated refresh token)."""
    body = _post_token({
        "client_id": CLIENT_ID(),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": SCOPES,
    })
    save_tokens(body)
    return body


# ---------- offline self-test: pending store + redirect-URL parser (Task 4) ----------
def selftest_parse():
    os.environ["MSFT_PENDING_VERIFIER"] = "PV"
    os.environ["MSFT_PENDING_STATE"]    = "PS"
    v, s = read_pending()
    assert (v, s) == ("PV", "PS"), (v, s)
    clear_pending()
    for k in ("MSFT_PENDING_VERIFIER", "MSFT_PENDING_STATE", "MSFT_PENDING_TS"):
        assert os.environ.get(k, "") == "", k
    try:
        read_pending()
        raise AssertionError("expected 'no pending' error")
    except RuntimeError as e:
        assert "No pending login" in str(e)

    st = "abcDEF123"
    url1 = ("http://127.0.0.1:8765/callback?code=A9B2C3D&state=" + st +
            "&session_state=x%3AeyJ0IjoxfQ")
    assert parse_authorize_callback(url1) == ("A9B2C3D", st)
    assert parse_authorize_callback(f"code=A9B2C3D&state={st}") == ("A9B2C3D", st), "bare query"
    assert parse_authorize_callback(f'"{url1}"') == ("A9B2C3D", st), "quoted"
    try:
        parse_authorize_callback(
              "http://127.0.0.1:8765/callback?error=access_denied"
              "&error_description=User+closed+the+window")
        raise AssertionError("expected error")
    except RuntimeError as e:
        assert "User closed the window" in str(e)
    try:
        parse_authorize_callback(f"http://127.0.0.1:8765/callback?state={st}")
        raise AssertionError("expected missing-code error")
    except RuntimeError as e:
        assert "code" in str(e)
    print("SELFTEST-OK parse")
    return 0


# ---------- paste-back capture: pending nonce store + redirect-URL parser (Task 4) ----------
def save_pending(verifier: str, state: str):
    """Persist the one-time PKCE material for the upcoming `consume`."""
    set_env("MSFT_PENDING_VERIFIER", verifier)
    set_env("MSFT_PENDING_STATE", state)
    set_env("MSFT_PENDING_TS", str(int(time.time())))
    # mirror into os.environ so read_pending() is coherent in the SAME process
    # that just called login() (symmetric with clear_pending()'s os.environ.pop).
    os.environ["MSFT_PENDING_VERIFIER"] = verifier
    os.environ["MSFT_PENDING_STATE"] = state
    os.environ["MSFT_PENDING_TS"] = str(int(time.time()))


def read_pending():
    v = os.environ.get("MSFT_PENDING_VERIFIER", "").strip()
    s = os.environ.get("MSFT_PENDING_STATE", "").strip()
    if not v or not s:
        raise RuntimeError(
            "No pending login found (MSFT_PENDING_* empty/missing).\n"
            f"    → Run: python3 {HERE} login\n"
            "    open the printed URL in a browser, sign in, then hand us the "
            "FULL redirect URL from the browser address bar.")
    return v, s


def clear_pending():
    for k in ("MSFT_PENDING_VERIFIER", "MSFT_PENDING_STATE", "MSFT_PENDING_TS"):
        set_env(k, "")
        os.environ.pop(k, None)


def parse_authorize_callback(url: str):
    """
    Accept the FULL redirect URL the user copied from the browser address bar:
      http://127.0.0.1:8765/callback?code=...&state=...
    Forgiving: full URL, URL w/o scheme, bare 'code=...&state=...', surrounding quotes.
    Extra AAD params (e.g. session_state) tolerated. Returns (code, state).
    Raises on AAD error payloads or missing code.
    """
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        raise RuntimeError("Empty URL passed to consume.")
    if "://" not in url:
        i = url.find("?")
        url = "http://localhost" + url[i:] if i != -1 else "http://localhost/?" + url
    p = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(p.query)
    if "error" in qs or "error_description" in qs:
        raise RuntimeError(
            "OAuth returned an error: "
            + (qs.get("error_description", [""])[0] or qs.get("error", ["unknown"])[0]))
    code = qs.get("code", [""])[0]
    state = qs.get("state", [""])[0]
    if not code:
        raise RuntimeError(
            "No 'code' in the pasted URL. Copy the FULL URL from the browser's "
            "address bar of the failed redirect page — it should contain "
            "?code=...&state=...")
    return code, state


def consume(callback_url: str) -> dict:
    """Verify pasted redirect URL against pending nonce, exchange code, save, clear."""
    _load_env()
    verifier, expected_state = read_pending()
    code, got_state = parse_authorize_callback(callback_url)
    if got_state != expected_state:
        raise RuntimeError(
            "state mismatch — that URL is not the one we issued for this login "
            "(don't reuse an old paste). Re-run `login` and use the new URL.")
    body = exchange_code(code, verifier)
    clear_pending()
    print(f"✅ Auth complete — access + refresh token saved to {ENV_PATH}")
    return body


# ---------- offline self-test: login() output + pending + get_access_token contract (Task 5) ----------
def selftest_flow():
    global ENV_PATH
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        login()
    out = buf.getvalue()
    assert "authorize_url" not in out and "https://login.microsoftonline.com/" in out, out
    assert "code_challenge_method=S256" in out
    assert "127.0.0.1:8765/callback" in out
    assert "consume" in out and "address bar" in out, "instructions missing"
    # pending was stored with a real verifier challenge relationship
    v = os.environ.get("MSFT_PENDING_VERIFIER", "")
    st = os.environ.get("MSFT_PENDING_STATE", "")
    assert v and st, "pending not stored"
    assert make_code_challenge(v) != "", "challenge computable"
    # get_access_token contract: no valid token + no refresh token + no interactive
    # → raises NotAuthenticatedError mentioning login (no network call attempted)
    # Isolate from the real .env: both pop os.environ and redirect ENV_PATH to
    # a nonexistent file so get_access_token() can't reload any stored tokens.
    saved = {k: os.environ.pop(k, "") for k in
             ("MSFT_ACCESS_TOKEN", "MSFT_REFRESH_TOKEN", "MSFT_TOKEN_EXPIRES_AT")}
    saved_env_path = ENV_PATH
    try:
        os.environ["MSFT_ACCESS_TOKEN"] = ""
        os.environ["MSFT_REFRESH_TOKEN"] = ""
        os.environ["MSFT_TOKEN_EXPIRES_AT"] = ""
        os.environ.pop("MSFT_PENDING_VERIFIER", None)
        os.environ.pop("MSFT_PENDING_STATE", None)
        os.environ.pop("MSFT_PENDING_TS", None)
        ENV_PATH = "/dev/null/__does_not_exist__"
        try:
            get_access_token()
            raise AssertionError("expected NotAuthenticatedError")
        except NotAuthenticatedError as e:
            assert "login" in str(e)
    finally:
        ENV_PATH = saved_env_path
        os.environ.update(saved)
        # Restore the pending values that login() stored in os.environ during
        # its own save_pending() call — clear them so the test doesn't leak.
        os.environ.pop("MSFT_PENDING_VERIFIER", None)
        os.environ.pop("MSFT_PENDING_STATE", None)
        os.environ.pop("MSFT_PENDING_TS", None)
    print("SELFTEST-OK flow")
    return 0


# ---------- login (non-blocking) + get_access_token contract (Task 5) ----------
class NotAuthenticatedError(RuntimeError):
    """No valid token available without the 2-step browser flow."""
    def __init__(self):
        super().__init__(
            "Not authenticated to Microsoft Graph (delegated). To fix:\n"
            f"    1) python3 {HERE} login\n"
            "       → open the printed URL in a browser (ANY device), sign in\n"
            "     2) browser will show the redirect page failed — EXPECTED\n"
            "        → copy the FULL URL from the address bar (contains ?code=...&state=...)\n"
            f'        → run: python3 {HERE} consume "<PASTED_URL>"')


def _access_still_valid() -> str:
    acc = os.environ.get("MSFT_ACCESS_TOKEN", "").strip()
    exp = os.environ.get("MSFT_TOKEN_EXPIRES_AT", "").strip()
    if acc and exp:
        try:
            t = datetime.datetime.strptime(exp, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=datetime.timezone.utc)
            if _now_utc() < t:
                return acc
        except ValueError:
            pass
    return ""


def get_access_token() -> str:
    """
    Return a valid delegated access token:
      1) cached access token still valid → return it
      2) else refresh token present        → refresh (persist), return it
      3) else                              → raise NotAuthenticatedError (2-step fix)
    """
    _load_env()
    tok = _access_still_valid()
    if tok:
        return tok
    rt = os.environ.get("MSFT_REFRESH_TOKEN", "").strip()
    if rt:
        try:
            return refresh_access_token(rt)["access_token"]
        except Exception:
            pass    # stale/rotated refresh token → force fresh login
    raise NotAuthenticatedError()


def login() -> None:
    """
    Step 1 of 2. NON-BLOCKING. Generates PKCE + state, stores the nonce in .env,
    prints the sign-in URL and the paste-back instructions. Nothing listens.
    Multi-tenant by default (organizations): any work/school account signs in.
    """
    _load_env()
    verifier = make_code_verifier()
    state     = secrets.token_urlsafe(16)
    save_pending(verifier, state)
    url = authorize_url(CLIENT_ID(), make_code_challenge(verifier), state)
    print("\n===== Microsoft sign-in (delegated, multi-tenant) — step 1 of 2 =====")
    print("Scopes:", SCOPES)
    print("\nOpen this URL in a browser (ANY device) and sign in:\n")
    print("     " + url)
    print("\nAfter sign-in the browser shows 'can't reach this page' for "
          "http://127.0.0.1:8765/callback — that is EXPECTED.")
    print("Copy the FULL URL from the address bar (contains ?code=...&state=...) "
          "and give it back.")
    print("Step 2 of 2 is then:")
    print(f'  python3 {HERE} consume "<PASTE_THE_URL_HERE>"')


# ---------- CLI entrypoint (Task 6) ----------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Shared Microsoft Graph delegated auth (PKCE, paste-back capture)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="1/2 print sign-in URL (stores PKCE nonce in .env)")
    p_con = sub.add_parser("consume", help="2/2 finish auth from the pasted redirect URL")
    p_con.add_argument("url", help="FULL redirect URL copied from the browser address bar")
    sub.add_parser("get-token", help="Print a valid access token (auto-refresh)")
    sub.add_parser("selftest", help="All offline self-tests")
    args = ap.parse_args(argv)

    if args.cmd == "selftest":
        selftest_pkce(); selftest_url(); selftest_authority_mode()
        selftest_parse(); selftest_flow()
        return 0
    if args.cmd == "login":
        login(); return 0
    if args.cmd == "consume":
        consume(args.url); return 0
    if args.cmd == "get-token":
        print(get_access_token()); return 0
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except NotAuthenticatedError as e:
        print(str(e), file=sys.stderr); sys.exit(3)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(4)
# ── CONSOLIDATION NOTE (2026-09-06 calendar-overview) ────────────────────
# This copy is the OWNED shipped auth core for the calendar-overview plugin.
# The source region (above this marker) is kept BYTE-IDENTICAL to the
# morning-digest copy and the standalone ~/.hermes/scripts copy; the three
# are diffed by scripts/verify-auth.sh (stripping this note first). Do NOT
# edit the source region here without editing the other two copies.
# ────────────────────────────────────────────────────────────
