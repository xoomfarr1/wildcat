from wildcat.programming.algorithms import (
    NoAlgorithmConfiguredError,
    SecurityAlgorithmRegistry,
)


class _Algo:
    def compute_key(self, seed, level=1):
        return bytes(b ^ 0xAA for b in seed)


def test_registry_empty_by_default():
    reg = SecurityAlgorithmRegistry()
    assert not reg.has("ECU1", 1)
    assert reg.list_registered() == []


def test_registry_raises_when_unconfigured():
    reg = SecurityAlgorithmRegistry()
    try:
        reg.compute_key("ECU1", b"\x01\x02\x03\x04", 1)
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")


def test_registry_compute_key_when_registered():
    reg = SecurityAlgorithmRegistry()
    reg.register("ECU1", 1, _Algo())
    assert reg.has("ECU1", 1)
    assert reg.compute_key("ECU1", b"\x01\x02\x03\x04", 1) == bytes([0xAB, 0xA8, 0xA9, 0xAE])
    assert reg.list_registered() == [("ECU1", 1)]
