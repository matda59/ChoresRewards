"""Feature tests talk to the app as a logged-in adult.

Security tests that need a stranger clear the session after creating the client.
"""

from app import app

_original_test_client = app.test_client


def _authenticated_test_client(*args, **kwargs):
    client = _original_test_client(*args, **kwargs)
    with client.session_transaction() as sess:
        if 'authenticated' not in sess:
            sess['authenticated'] = True
        if 'adult_mode' not in sess:
            sess['adult_mode'] = True
    return client


app.test_client = _authenticated_test_client
