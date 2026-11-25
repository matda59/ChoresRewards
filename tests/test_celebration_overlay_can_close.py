"""The all-done celebration must not trap the page under an untappable card."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shimmer_does_not_steal_taps_and_continue_stays_available():
    page = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')
    shimmer = page.split('.celebration-content::before', 1)[1].split('}', 1)[0]
    assert 'pointer-events: none' in shimmer
    assert 'id="celebration-quiz-btn"' in page
    assert 'style="display:none;" onclick="closeCelebration()"' not in page
    assert 'celebration.js' in page
    assert 'function closeCelebration()' in page
    assert "event.key !== 'Escape'" in page
    assert 'alreadyCelebrated' in page
    script = (ROOT / 'static' / 'js' / 'celebration.js').read_text(encoding='utf-8')
    assert 'DISMISS_MS = 8000' in script
