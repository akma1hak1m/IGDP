"""Separate admin (/admin) authentication from the normal user login (/).

The admin site stores its own auth state in the session under dedicated keys
with the ``_admin_auth`` prefix, never touching Django's default
``_auth_user_*`` keys used by the user-facing login. Each interface can
therefore be logged in/out independently within the same browser session.
"""

from django.contrib.auth import load_backend
from django.contrib.auth.models import AnonymousUser
from django.utils.crypto import constant_time_compare

ADMIN_SESSION_PREFIX = "_admin_auth"
ADMIN_SESSION_ID_KEY = f"{ADMIN_SESSION_PREFIX}_user_id"
ADMIN_SESSION_BACKEND_KEY = f"{ADMIN_SESSION_PREFIX}_user_backend"
ADMIN_SESSION_HASH_KEY = f"{ADMIN_SESSION_PREFIX}_hash"

# URL prefix where the custom admin site is mounted (dgp_system/urls.py).
ADMIN_URL_PREFIX = "/admin/"


def set_admin_auth(request, user):
    """Authenticate *user* for the admin interface only."""
    backend = getattr(user, "backend", None) or "django.contrib.auth.backends.ModelBackend"
    request.session.cycle_key()
    request.session[ADMIN_SESSION_ID_KEY] = str(user.pk)
    request.session[ADMIN_SESSION_BACKEND_KEY] = backend
    request.session[ADMIN_SESSION_HASH_KEY] = user.get_session_auth_hash()


def clear_admin_auth(request):
    for key in (ADMIN_SESSION_ID_KEY, ADMIN_SESSION_BACKEND_KEY, ADMIN_SESSION_HASH_KEY):
        request.session.pop(key, None)


def get_admin_user(request):
    """Return the admin-authenticated user for this request, or None.

    The result is cached on the request to avoid repeated DB lookups.
    Invalid/stale admin state (deleted user, changed password) is cleared.
    """
    if hasattr(request, "_admin_auth_user_cache"):
        return request._admin_auth_user_cache
    user = None
    user_id = request.session.get(ADMIN_SESSION_ID_KEY)
    stored_hash = request.session.get(ADMIN_SESSION_HASH_KEY)
    backend_path = request.session.get(ADMIN_SESSION_BACKEND_KEY)
    if user_id and stored_hash and backend_path:
        try:
            backend = load_backend(backend_path)
            user = backend.get_user(user_id)
        except Exception:
            user = None
        if user is not None and not constant_time_compare(stored_hash, user.get_session_auth_hash()):
            user = None
    if user is None:
        clear_admin_auth(request)
    request._admin_auth_user_cache = user
    return user


def preserve_keys(request, keep_prefixes):
    """Flush the session, re-saving only keys matching the given prefixes."""
    preserved = {k: v for k, v in request.session.items() if k.startswith(keep_prefixes)}
    request.session.flush()
    request.session.update(preserved)


def preserve_all_except(request, drop_prefixes):
    """Flush the session, re-saving only keys NOT matching the given prefixes."""
    preserved = {k: v for k, v in request.session.items() if not k.startswith(drop_prefixes)}
    request.session.flush()
    request.session.update(preserved)


class AdminSessionMiddleware:
    """Resolve ``request.user`` for /admin/ requests from the admin session.

    Normal-user requests keep using Django's default AuthenticationMiddleware
    (``_auth_user_*`` keys). For admin paths, ``request.user`` is replaced by
    the admin-authenticated user — or AnonymousUser when there is no valid
    admin login — so a normal-user session never grants admin access, and an
    admin login never grants user-interface access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(ADMIN_URL_PREFIX):
            user = get_admin_user(request)
            request.user = user if user is not None else AnonymousUser()
        return self.get_response(request)
