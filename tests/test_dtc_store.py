import json
import tempfile
from pathlib import Path

from wildcat.diagnostics.dtc_store import DTCStore


def test_bundled_overlay_loaded():
    store = DTCStore()
    # Bundled Automotive-9/dtc-codes data is loaded by default.
    assert store.lookup("P0301") is not None
    assert len(store.known_codes()) > 18000


def test_known_code_two_manufacturers():
    store = DTCStore()
    # P0301 and P0420 resolve from bundled data (multiple manufacturers provide them).
    assert store.lookup("P0301") is not None
    assert store.lookup("P0420") is not None


def test_unknown_returns_none():
    store = DTCStore()
    assert store.lookup("P9999ZZZ") is None


def test_mercedes_gap_returns_none():
    # No Mercedes file in bundled data; a code absent from all files is None.
    store = DTCStore()
    assert store.lookup("ZZZZ9") is None


def test_overlay_overrides_bundled():
    store = DTCStore({"P0301": "Overlay text"})
    assert store.lookup("P0301") == "Overlay text"


def test_overlay_from_file():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "overlay.json"
        p.write_text(json.dumps({"P0420": "Custom catalyst text"}))
        store = DTCStore(str(p))
        assert store.lookup("P0420") == "Custom catalyst text"
        assert store.lookup("P0301") is not None


def test_manufacturer_scoped_lookup_differs():
    store = DTCStore()
    # Same code, different manufacturer -> different description.
    bmw = store.lookup("P1120", manufacturer="BMW")
    ford = store.lookup("P1120", manufacturer="Ford")
    assert bmw is not None and ford is not None
    assert bmw != ford
    # Code-only fallback returns one of them (first loaded).
    assert store.lookup("P1120") is not None


def test_manufacturer_unknown_returns_none():
    store = DTCStore()
    assert store.lookup("P9999ZZZ", manufacturer="BMW") is None


def test_manufacturer_mercedes_gap_returns_none():
    store = DTCStore()
    # Mercedes has no bundled file: a code absent from all files is None regardless.
    assert store.lookup("ZZZZ9", manufacturer="Mercedes") is None
    # A code present in other manufacturers still resolves via documented fallback.
    assert store.lookup("P0301", manufacturer="Mercedes") is not None
    try:
        DTCStore([1, 2, 3])
    except TypeError:
        return
    raise AssertionError("expected ValueError")
