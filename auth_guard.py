"""Server-side session gate for ChoresRewards.

The master PIN used to be checked only in the browser. These helpers make the
Flask session the real boundary: reading or changing family data requires
``authenticated``, and the actions the padlock hides require ``adult_mode``.

``CR_READONLY_API_KEY``, when set to at least 32 characters, lets a trusted
automation read an allowlist of GET endpoints without a session. It cannot
change data, open a session, or trip the PIN lockout.

``CR_WRITE_API_KEY`` is a second key for everyday changes (chores, rewards,
meals, shopping lines, notes). It is disabled when unset, short, or equal to
the read-only key. It cannot open settings, manage family members, upload
files, or run the daily chore reset.
"""

import hashlib
import hmac
import json
import os
import re
import time
import fcntl
from urllib.parse import unquote, urlparse

import bcrypt
from flask import current_app, g, jsonify, make_response, redirect, render_template, request, session, url_for
from flask.sessions import SecureCookieSessionInterface

MIN_SECRET_LEN = 4
MAX_SECRET_LEN = 64
_BCRYPT_MAX_BYTES = 72

# A fixed hash so a missing PIN still costs a bcrypt comparison.
_DUMMY_PIN_HASH = bcrypt.hashpw(b'choresrewards-timing-pad', bcrypt.gensalt())

# POST actions the padlock hides in the UI. GET reads of the same areas stay
# available to a logged-in child session, because the page fetches them once
# and only reveals the controls after adult mode is unlocked.
_ADULT_POST_PATHS = frozenset({
    '/add_reward',
    '/edit_chore',
    '/edit_reward',
    '/edit_reward_image',
    '/add_person',
    '/delete_person',
    '/delete_reward',
    '/add_chore',
    '/add_daily_chore',
    '/edit_daily_chore',
    '/delete_daily_chore',
    '/delete_chore',
    '/reset_points',
    '/complete_reward',
    '/update_name',
    '/api/sounds/upload',
    '/api/sounds/delete',
    '/api/screensaver/upload',
    '/api/screensaver/delete',
    '/api/screensaver/rescan',
    '/api/screensaver/clear',
})

_PUBLIC_EXACT = frozenset({
    '/favicon.ico',
    '/apple-touch-icon.png',
    '/apple-touch-icon-precomposed.png',
    '/manifest.json',
    '/sw.js',
    '/robots.txt',
})

_LOGIN_POSTS = frozenset({
    '/api/login',
    '/api/adult_login',
    '/api/person_login',
})

_AVATAR_POST = re.compile(r'^/upload_avatar/\d+$')


def acceptable_secret(raw):
    """True for a PIN or passphrase an existing 4-digit PIN still satisfies."""
    if not isinstance(raw, str):
        return False
    text = raw.strip()
    if len(text) < MIN_SECRET_LEN or len(text) > MAX_SECRET_LEN:
        return False
    if any(ord(ch) < 32 for ch in text):
        return False
    try:
        return len(text.encode('utf-8')) <= _BCRYPT_MAX_BYTES
    except Exception:
        return False


def pin_matches(raw_pin, stored_hash):
    """Compare a PIN with bcrypt. Missing and malformed hashes still do the work."""
    if raw_pin is None:
        raw = b''
    else:
        raw = str(raw_pin).encode('utf-8', 'replace')[:_BCRYPT_MAX_BYTES]
    try:
        hashed = stored_hash.encode('utf-8') if isinstance(stored_hash, str) and stored_hash else b''
        if not hashed:
            bcrypt.checkpw(raw, _DUMMY_PIN_HASH)
            return False
        return bcrypt.checkpw(raw, hashed)
    except Exception:
        try:
            bcrypt.checkpw(raw, _DUMMY_PIN_HASH)
        except Exception:
            pass
        return False


def start_family_session(adult, adult_name=None, person_id=None, person_name=None):
    """Replace whatever was in the cookie with a fresh login session."""
    session.clear()
    session['authenticated'] = True
    session['adult_mode'] = bool(adult)
    if adult and adult_name:
        session['adult_name'] = adult_name
    if person_id is not None:
        session['person_id'] = person_id
        session['person_name'] = person_name
    session.permanent = False


def normalise_path(path):
    path = unquote(path or '/').split('?', 1)[0]
    if len(path) > 1 and path.endswith('/'):
        path = path[:-1]
    return path or '/'


def is_public_request(method, path):
    """True for the login shell's assets and the login endpoints themselves."""
    method = (method or 'GET').upper()
    path = normalise_path(path)
    lowered = path.lower()
    if lowered.startswith('/static/') and not lowered.startswith('/static/uploads/'):
        return True
    if path in _PUBLIC_EXACT:
        return True
    if path == '/api/check_auth' and method in ('GET', 'HEAD'):
        return True
    if path in _LOGIN_POSTS and method == 'POST':
        return True
    return False


def requires_adult(method, path):
    """True when the padlock (adult mode) must be on, not just a family session."""
    method = (method or 'GET').upper()
    path = normalise_path(path)
    if path == '/settings' or path.startswith('/settings/'):
        return True
    if path == '/usage' or path.startswith('/usage/'):
        return True
    if path == '/api/images':
        return True
    if method == 'POST' and path in _ADULT_POST_PATHS:
        return True
    if method == 'POST' and _AVATAR_POST.match(path):
        return True
    if path == '/api/organise' or path.startswith('/api/organise/'):
        return method in ('POST', 'PUT', 'PATCH', 'DELETE')
    return False


def _login_is_configured():
    """True once a master PIN or any family member exists.

    Before that, only the setup wizard should be reachable. A query failure
    fails closed so a broken database does not publish the app.
    """
    try:
        from models import AppSetting, Person
        if AppSetting.get('master_pin'):
            return True
        if Person.query.filter(Person.pin.isnot(None), Person.pin != '').first() is not None:
            return True
        return Person.query.first() is not None
    except Exception:
        return True


def _setup_is_open():
    """The first-run wizard stays available until an admin PIN or master PIN exists."""
    try:
        from models import AppSetting, Person
        if AppSetting.get('master_pin'):
            return False
        admin = Person.query.filter_by(is_admin=True).filter(
            Person.pin.isnot(None), Person.pin != ''
        ).first()
        return admin is None
    except Exception:
        return False


def _wants_json_denial(method, path):
    """API and fetch() calls get JSON. A browser navigation gets the login shell."""
    method = method.upper()
    if path.startswith('/api/') or path.startswith('/completed_chores_fragment'):
        return True
    if path.lower().startswith('/static/uploads/'):
        return True
    if path.startswith('/get_chores') or path.startswith('/get_column_color/'):
        return True
    if method in ('GET', 'HEAD', 'OPTIONS'):
        return False
    if request.is_json:
        return True
    if (request.headers.get('X-Requested-With') or '').lower() == 'xmlhttprequest':
        return True
    accept = request.headers.get('Accept') or ''
    if 'application/json' in accept and 'text/html' not in accept:
        return True
    if 'text/html' in accept:
        return False
    return True


def _request_hosts():
    hosts = set()
    host = (request.host or '').split(',')[0].strip().lower()
    if host:
        hosts.add(host)
    forwarded = (request.headers.get('X-Forwarded-Host') or '').split(',')[0].strip().lower()
    if forwarded:
        hosts.add(forwarded)
    extra = (os.environ.get('CR_PUBLIC_HOST') or '').strip().lower()
    if extra:
        hosts.add(extra)
    return hosts


def _origin_allowed():
    """Reject a state-changing request whose Origin or Referer is another site.

    SameSite=Lax already withholds the cookie on cross-site POST. This is a
    second check for browsers that send Origin. Requests with neither header
    (the test client, and some non-browser tools on the LAN) are allowed.
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return True
    origin = request.headers.get('Origin')
    if origin:
        if origin.strip().lower() == 'null':
            return False
        return (urlparse(origin).netloc or '').lower() in _request_hosts()
    referer = request.headers.get('Referer')
    if referer:
        return (urlparse(referer).netloc or '').lower() in _request_hosts()
    return True


def _json_error(message, status):
    response = jsonify({'success': False, 'error': message, 'authenticated': bool(session.get('authenticated'))})
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    return response


def _login_shell():
    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


class ProxyAwareSessionInterface(SecureCookieSessionInterface):
    """Mark the session cookie Secure on HTTPS, including behind Caddy or Cloudflare.

    ``CR_COOKIE_SECURE=0`` forces it off for a plain-HTTP LAN address.
    ``CR_COOKIE_SECURE=1`` forces it on. Otherwise the scheme follows
    ``X-Forwarded-Proto`` or the request itself, so ``http://localhost`` still
    keeps a working login.
    """

    def get_cookie_secure(self, app):
        override = (os.environ.get('CR_COOKIE_SECURE') or '').strip().lower()
        if override in ('0', 'false', 'no', 'off'):
            return False
        if override in ('1', 'true', 'yes', 'on'):
            return True
        try:
            proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or '')
        except RuntimeError:
            return bool(app.config.get('SESSION_COOKIE_SECURE'))
        return proto.split(',')[0].strip().lower() == 'https'

    def save_session(self, app, session, response):
        # An API key is not a browser login. Skip the cookie even if a view
        # touched the session object, so a key request cannot create or
        # refresh one.
        try:
            if getattr(g, 'cr_api_key_request', False):
                return
        except RuntimeError:
            pass
        return super().save_session(app, session, response)


_READONLY_API_KEY_ENV = 'CR_READONLY_API_KEY'
_WRITE_API_KEY_ENV = 'CR_WRITE_API_KEY'
_MIN_API_KEY_LEN = 32
# Compared only when a real key is not configured, so the number of digest
# compares does not reveal which key is enabled.
_API_KEY_DUMMY = 'choresrewards-api-key-timing-pad-not-a-secret'
_write_key_equal_warned = False
_API_KEY_MAX_FAILURES = 8
_API_KEY_WINDOW_SECONDS = 300
_API_KEY_MEMORY = {}

# GET/HEAD only. Kept exact so a new route is not readable until it is added
# here on purpose. /get_chores is intentionally absent: that handler redirects
# to the home page, which runs the daily chore reset.
_READONLY_API_EXACT = frozenset({
    '/api/screensaver/chore_summary',
    '/api/meal_planner',
    '/api/shopping_list',
    '/api/shopping_stores',
    '/api/meal_ingredients',
    '/api/notifications',
    '/api/notes',
    '/api/dashboard_notes',
    '/api/organise',
})

_READONLY_SERVICE_PATH = re.compile(r'^/api/organise/\d+/services$')


def readonly_api_allows(method, path):
    """True for a read of an allowlisted path. The key is checked separately."""
    method = (method or 'GET').upper()
    if method not in ('GET', 'HEAD'):
        return False
    path = normalise_path(path)
    if path in _READONLY_API_EXACT:
        return True
    return _READONLY_SERVICE_PATH.match(path) is not None


# Everyday changes only. Settings, logins, family-member management, uploads,
# and the whole-document saves (they wipe a list when the body is partial)
# are intentionally absent. GET / is absent because that page runs the reset.
_WRITE_API_EXACT = frozenset({
    ('POST', '/add_chore'),
    ('POST', '/edit_chore'),
    ('POST', '/add_daily_chore'),
    ('POST', '/edit_daily_chore'),
    ('POST', '/delete_chore'),
    ('POST', '/delete_daily_chore'),
    ('POST', '/complete_chore'),
    ('POST', '/undo_complete_chore'),
    ('POST', '/api/extra_chores/claim'),
    ('POST', '/add_reward'),
    ('POST', '/edit_reward'),
    ('POST', '/delete_reward'),
    ('POST', '/complete_reward'),
    ('POST', '/award_bonus_points'),
    ('POST', '/reset_points'),
    ('POST', '/api/meal_planner/slot'),
    ('POST', '/api/meal_planner/recurring'),
    ('POST', '/api/meal_planner/suggestions/items'),
    ('POST', '/api/meal_planner/suggestions/remove'),
    ('POST', '/api/meal_ingredients/items'),
    ('POST', '/api/meal_ingredients/items/remove'),
    ('POST', '/api/shopping_list/items'),
    ('POST', '/api/shopping_list/items/check'),
    ('POST', '/api/shopping_list/items/remove'),
    ('POST', '/api/notes/cards'),
    ('POST', '/api/notes/cards/update'),
    ('POST', '/api/notes/cards/remove'),
    ('POST', '/api/dashboard_notes/notes'),
    ('POST', '/api/dashboard_notes/notes/update'),
    ('POST', '/api/dashboard_notes/notes/remove'),
})


def write_api_allows(method, path):
    """True for one everyday change. The write key is checked separately."""
    method = (method or 'GET').upper()
    path = normalise_path(path)
    return (method, path) in _WRITE_API_EXACT


def _configured_readonly_api_key():
    """The key, or None when the feature is off.

    Unset, blank, and anything shorter than 32 characters all disable it.
    """
    raw = os.environ.get(_READONLY_API_KEY_ENV)
    if raw is None:
        return None
    key = raw.strip()
    if len(key) < _MIN_API_KEY_LEN:
        return None
    return key


def _announce_readonly_api_key():
    raw = os.environ.get(_READONLY_API_KEY_ENV)
    if raw is None or not str(raw).strip():
        return
    if _configured_readonly_api_key() is None:
        print(
            '[auth] Ignoring CR_READONLY_API_KEY because it is shorter than '
            '32 characters. The read-only API is disabled.'
        )
        return
    print('[auth] Read-only API key is enabled for allowlisted GET requests.')


def _configured_write_api_key():
    """The write key, or None when that feature is off.

    Unset, blank, and short values disable it. The same string as the
    read-only key also disables it, so one leaked read key cannot be reused
    to change family data.
    """
    global _write_key_equal_warned
    raw = os.environ.get(_WRITE_API_KEY_ENV)
    if raw is None:
        return None
    key = str(raw).strip()
    if len(key) < _MIN_API_KEY_LEN:
        return None
    read_key = _configured_readonly_api_key()
    if read_key is not None and _api_key_matches(key, read_key):
        if not _write_key_equal_warned:
            print(
                '[auth] CR_WRITE_API_KEY matches CR_READONLY_API_KEY. '
                'The write key is disabled until the two values differ.'
            )
            _write_key_equal_warned = True
        return None
    _write_key_equal_warned = False
    return key


def _announce_write_api_key():
    raw = os.environ.get(_WRITE_API_KEY_ENV)
    if raw is None or not str(raw).strip():
        return
    key = str(raw).strip()
    if len(key) < _MIN_API_KEY_LEN:
        print(
            '[auth] Ignoring CR_WRITE_API_KEY because it is shorter than '
            '32 characters. The write API is disabled.'
        )
        return
    if _configured_write_api_key() is None:
        return
    print('[auth] Write API key is enabled for allowlisted family changes.')


def _presented_matches(presented, expected):
    """Constant-time match. A missing key still pays for one digest compare."""
    if not expected:
        _api_key_matches(presented, _API_KEY_DUMMY)
        return False
    return _api_key_matches(presented, expected)


def _presented_api_key():
    """Return the key sent in a header, or None when the client did not try.

    Query strings are never read. ``Authorization: Bearer`` and ``X-API-Key``
    are the only accepted places. If both are sent they have to match.
    """
    found = []
    header_key = request.headers.get('X-API-Key')
    if header_key is not None and header_key.strip():
        found.append(header_key.strip())
    authorization = request.headers.get('Authorization')
    if authorization:
        scheme, _, rest = authorization.partition(' ')
        if scheme.lower() == 'bearer' and rest.strip():
            found.append(rest.strip())
    if not found:
        return None
    first = found[0]
    if any(item != first for item in found):
        return ''
    return first


def _api_key_matches(presented, expected):
    """Constant-time compare. Digests are fixed length, so a short guess does not return early."""
    try:
        presented_bytes = presented.encode('utf-8')
        expected_bytes = expected.encode('utf-8')
    except Exception:
        # Keep the digest compare, and make sure a coding failure cannot match.
        presented_bytes = b''
        expected_bytes = b'\x00'
    if len(presented_bytes) > 8192:
        presented_bytes = presented_bytes[:8192]
    return hmac.compare_digest(
        hashlib.sha256(presented_bytes).digest(),
        hashlib.sha256(expected_bytes).digest(),
    )


def _api_key_client_ip():
    for header in ('CF-Connecting-IP', 'X-Real-IP', 'X-Forwarded-For'):
        value = (request.headers.get(header) or '').split(',')[0].strip()
        if value:
            return value[:200]
    return (request.remote_addr or '0.0.0.0')[:200]


def _api_key_attempt_path():
    try:
        folder = current_app.instance_path
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, 'readonly_api_key_attempts.json')
    except Exception:
        return None


def _prune_api_key_attempts(data, now, window):
    if len(data) <= 500:
        return
    stale = []
    for key, entry in list(data.items()):
        fails = entry.get('fails') if isinstance(entry, dict) else None
        if not fails or not any(
            isinstance(stamp, (int, float)) and now - float(stamp) < window
            for stamp in fails
        ):
            stale.append(key)
    for key in stale:
        data.pop(key, None)


def _api_key_attempt_update(mutator):
    """Share failed-key counts across Gunicorn workers. Separate from the PIN file."""
    path = _api_key_attempt_path()
    if not path:
        return mutator(_API_KEY_MEMORY)
    lock_path = path + '.lock'
    with open(lock_path, 'a+', encoding='utf-8') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as handle:
                        loaded = json.load(handle)
                    if isinstance(loaded, dict):
                        data = loaded
                except Exception:
                    data = {}
            result = mutator(data)
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(data, handle)
            os.replace(tmp, path)
            return result
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _note_bad_api_key():
    """Count a wrong key. Returns retry-after seconds once the window is full, else 0.

    A correct key does not come through here, so guessing cannot lock the
    owner out. This store is not the PIN lockout.
    """
    now = time.time()
    ip = _api_key_client_ip()
    window = _API_KEY_WINDOW_SECONDS
    limit = _API_KEY_MAX_FAILURES

    def mutate(data):
        entry = data.get(ip) if isinstance(data.get(ip), dict) else {}
        fails = [
            float(stamp) for stamp in entry.get('fails', [])
            if isinstance(stamp, (int, float)) and now - float(stamp) < window
        ]
        if len(fails) >= limit:
            oldest = min(fails) if fails else now
            data[ip] = {'fails': fails}
            _prune_api_key_attempts(data, now, window)
            return max(1, int(window - (now - oldest)) + 1)
        fails.append(now)
        data[ip] = {'fails': fails}
        _prune_api_key_attempts(data, now, window)
        if len(fails) >= limit:
            oldest = min(fails)
            return max(1, int(window - (now - oldest)) + 1)
        return 0

    try:
        return _api_key_attempt_update(mutate)
    except Exception:
        return 0


def _api_key_error(message, status, retry_after=None):
    body = {'success': False, 'error': message}
    if retry_after:
        body['retry_after'] = int(retry_after)
    response = jsonify(body)
    response.status_code = status
    response.headers['Cache-Control'] = 'no-store'
    if retry_after:
        response.headers['Retry-After'] = str(int(retry_after))
    return response


def _audit_api_key_write(response):
    """One stdout line per write the write key was allowed to attempt.

    The line names the endpoint, method, time, and key type. It never includes
    the key, the body, or the query string.
    """
    if not getattr(g, 'cr_write_api', False):
        return
    method = (request.method or '').upper()
    if method in ('GET', 'HEAD', 'OPTIONS'):
        return
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    path = normalise_path(request.path)
    status = getattr(response, 'status_code', 0)
    print(
        f'[api-key] write method={method} path={path} key_type=write at={stamp} status={status}',
        flush=True,
    )


def _api_key_gate(method, path):
    """Authorise a key, refuse anything else it tries, or stay out of the way.

    Returns a response when this request must stop. Returns None when the
    normal session rules should run, or when a key already allowed it.
    A matching write key sets ``g.cr_write_api``. A matching read sets
    ``g.cr_readonly_api``. Either sets ``g.cr_api_key_request`` so the
    session cookie is not saved.
    """
    presented = _presented_api_key()
    read_key = _configured_readonly_api_key()
    write_key = _configured_write_api_key()
    if presented is None or (read_key is None and write_key is None):
        return None
    g.cr_api_key_request = True
    # Always compare both slots so a disabled key does not return early.
    read_ok = _presented_matches(presented, read_key)
    write_ok = _presented_matches(presented, write_key)
    if write_ok and (write_api_allows(method, path) or readonly_api_allows(method, path)):
        g.cr_write_api = True
        g.cr_readonly_api = True
        return None
    if read_ok and readonly_api_allows(method, path):
        g.cr_readonly_api = True
        return None
    if read_ok and not write_ok:
        return _api_key_error('API key is read-only', 403)
    if write_ok or read_ok:
        return _api_key_error('API key cannot access this', 403)
    retry_after = _note_bad_api_key()
    if retry_after:
        return _api_key_error('Too many attempts. Try again shortly.', 429, retry_after)
    return _api_key_error('Invalid API key', 401)


def _readonly_api_key_gate(method, path):
    """Backwards-compatible name for the combined key gate."""
    return _api_key_gate(method, path)


def sees_adult_alerts():
    """Adult sessions and the read-only key can see rego and service alerts.

    The key is the owner's. It does not turn adult mode on in the browser
    cookie, and a child session that did not send the key still has those
    alerts removed.
    """
    if getattr(g, 'cr_readonly_api', False):
        return True
    return bool(session.get('adult_mode', False))


def install_auth(app):
    """Attach the session gate. Call this after the other before_request hooks."""
    _announce_readonly_api_key()
    _announce_write_api_key()

    @app.before_request
    def _require_family_session():
        if request.method == 'OPTIONS':
            return None

        path = normalise_path(request.path)
        method = request.method.upper()
        # A presented key is the credential for this request. It is checked
        # before the public-login shortcuts so it cannot open a session, post
        # the PIN, or land on the home page (that page runs the daily reset).
        # A key that was actually accepted skips the Origin check. A browser
        # session, a missing key, and a rejected key do not.
        denial = _api_key_gate(method, path)
        if denial is not None:
            return denial
        if getattr(g, 'cr_write_api', False) or getattr(g, 'cr_readonly_api', False):
            return None
        if not _origin_allowed():
            return _json_error('Cross-site request blocked', 403)
        if is_public_request(method, path):
            return None
        if path == '/setup' and _setup_is_open():
            return None
        if path == '/' and _setup_is_open() and not _login_is_configured():
            return None

        if not session.get('authenticated'):
            if _wants_json_denial(method, path):
                return _json_error('Login required', 401)
            return _login_shell()

        if requires_adult(method, path) and not session.get('adult_mode'):
            # Settings and usage are whole pages. A locked session is sent back
            # to the board, including a form post, which is what the pages did
            # before this gate existed.
            if path == '/settings' or path.startswith('/settings/') or path == '/usage' or path.startswith('/usage/'):
                return redirect(url_for('routes.index'))
            return _json_error('Adult authorisation required', 403)
        return None

    @app.after_request
    def _keep_family_responses_private(response):
        _audit_api_key_write(response)
        path = normalise_path(request.path).lower()
        if path.startswith('/static/') and not path.startswith('/static/uploads/'):
            return response
        if path in _PUBLIC_EXACT:
            return response
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        return response
