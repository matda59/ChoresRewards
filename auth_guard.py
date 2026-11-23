"""Server-side session gate for ChoresRewards.

The master PIN used to be checked only in the browser. These helpers make the
Flask session the real boundary: reading or changing family data requires
``authenticated``, and the actions the padlock hides require ``adult_mode``.
"""

import os
import re
from urllib.parse import unquote, urlparse

import bcrypt
from flask import jsonify, make_response, redirect, render_template, request, session, url_for
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


def install_auth(app):
    """Attach the session gate. Call this after the other before_request hooks."""

    @app.before_request
    def _require_family_session():
        if request.method == 'OPTIONS':
            return None
        if not _origin_allowed():
            return _json_error('Cross-site request blocked', 403)

        path = normalise_path(request.path)
        method = request.method.upper()
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
        path = normalise_path(request.path).lower()
        if path.startswith('/static/') and not path.startswith('/static/uploads/'):
            return response
        if path in _PUBLIC_EXACT:
            return response
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        return response
