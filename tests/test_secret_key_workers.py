"""Workers that boot together must sign sessions with the same key."""

import threading

import pytest

from app import _load_secret_key


class _FakeApp:
    def __init__(self, instance_path):
        self.instance_path = instance_path


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv('CR_SECRET_KEY', raising=False)
    monkeypatch.delenv('SECRET_KEY', raising=False)


def test_concurrent_workers_share_one_persisted_key(tmp_path, clean_env):
    fake = _FakeApp(str(tmp_path))
    barrier = threading.Barrier(8)
    found = []
    errors = []

    def load():
        try:
            barrier.wait()
            found.append(_load_secret_key(fake))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=load) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(found) == 8
    assert len(set(found)) == 1
    stored = (tmp_path / 'secret_key').read_text(encoding='utf-8').strip()
    assert stored == found[0]
    assert _load_secret_key(fake) == stored
    assert (tmp_path / 'secret_key').stat().st_mode & 0o777 == 0o600


def test_existing_key_is_kept(tmp_path, clean_env):
    key_path = tmp_path / 'secret_key'
    key_path.write_text('already-installed-key\n', encoding='utf-8')
    fake = _FakeApp(str(tmp_path))
    assert _load_secret_key(fake) == 'already-installed-key'
    assert key_path.read_text(encoding='utf-8').strip() == 'already-installed-key'


def test_env_key_is_used_without_writing_a_file(tmp_path, monkeypatch):
    monkeypatch.setenv('CR_SECRET_KEY', 'from-the-environment')
    fake = _FakeApp(str(tmp_path))
    assert _load_secret_key(fake) == 'from-the-environment'
    assert not (tmp_path / 'secret_key').exists()
