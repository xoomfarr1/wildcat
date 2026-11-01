import json
import tempfile
from pathlib import Path

from wildcat.diagnostics.dtc_store import DTCStore


def test_generic_lookup():
    store = DTCStore()
    assert store.lookup("P0301") == "Cylinder 1 Misfire Detected"
    assert store.lookup("p0301") == "Cylinder 1 Misfire Detected"


def test_unknown_returns_none():
    store = DTCStore()
    assert store.lookup("P9999") is None


def test_overlay_overrides_generic():
    store = DTCStore({"P0301": "Overlay text"})
    assert store.lookup("P0301") == "Overlay text"


def test_overlay_from_file():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "overlay.json"
        p.write_text(json.dumps({"P0420": "Custom catalyst text"}))
        store = DTCStore(str(p))
        assert store.lookup("P0420") == "Custom catalyst text"
        assert store.lookup("P0301") == "Cylinder 1 Misfire Detected"


def test_overlay_bad_type_raises():
    try:
        DTCStore([1, 2, 3])
    except TypeError:
        return
    raise AssertionError("expected ValueError")
