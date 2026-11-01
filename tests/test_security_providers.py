from wildcat.programming.algorithms import (
    NoAlgorithmConfiguredError,
    SecurityAlgorithmRegistry,
    SecurityProviderRegistry,
)


def test_provider_registry_loaded():
    reg = SecurityProviderRegistry()
    assert reg.count() == 3038
    assert reg.unique_ecus() > 0
    assert len(reg.unique_providers()) == 41


def test_provider_lookup_known():
    reg = SecurityProviderRegistry()
    providers = reg.lookup("ME97", 1)
    assert len(providers) >= 1
    p = providers[0]
    assert p.provider == "PowertrainBoschContiSecurityAlgo1"
    assert p.seed_length == 2
    assert p.key_length == 2


def test_provider_lookup_unknown():
    reg = SecurityProviderRegistry()
    assert reg.lookup("NO_SUCH_ECU", 1) == []
    assert not reg.has("NO_SUCH_ECU", 1)


def test_no_algorithm_configured_still_raises():
    # Definitions alone do not compute keys.
    reg = SecurityAlgorithmRegistry()
    try:
        reg.compute_key("ME97", b"\x00\x00", 1)
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")
