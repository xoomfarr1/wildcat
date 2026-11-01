from wildcat.programming.algorithms import (
    NoAlgorithmConfiguredError,
    SecurityAlgorithmRegistry,
    SecurityProviderRegistry,
)


def _provider(ecu, level):
    reg = SecurityProviderRegistry()
    ps = reg.lookup(ecu, level)
    assert ps, f"no provider for {ecu}/{level}"
    return ps[0]


def test_virtual_provider_me97_bosch():
    # Bosch Continental powertrain provider (Mercedes ME97).
    p = _provider("ME97", 1)
    assert p.provider == "PowertrainBoschContiSecurityAlgo1"
    assert p.seed_length == 2 and p.key_length == 2
    # No concrete algorithm registered -> honest failure, no fabricated key.
    algo_reg = SecurityAlgorithmRegistry()
    try:
        algo_reg.compute_key("ME97", b"\x00\x00", 1)
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")


def test_virtual_provider_daimler_standard():
    # Daimler standard security (Mercedes ANC_205M).
    p = _provider("ANC_205M", 11)
    assert p.provider == "DaimlerStandardSecurityAlgo"
    assert p.seed_length == 8 and p.key_length == 4
    algo_reg = SecurityAlgorithmRegistry()
    try:
        algo_reg.compute_key("ANC_205M", b"\x00" * 8, 11)
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")


def test_virtual_provider_honda():
    reg = SecurityProviderRegistry()
    # Find a Honda provider.
    honda = [ecu for ecu in {k[0] for k in reg._entries} if "honda" in ecu.lower() or "hmc" in ecu.lower()]
    assert honda, "no Honda ECU in provider db"
    ecu = honda[0]
    levels = [k[1] for k in reg._entries if k[0] == ecu]
    p = reg.lookup(ecu, levels[0])[0]
    assert p.provider  # non-empty
    algo_reg = SecurityAlgorithmRegistry()
    try:
        algo_reg.compute_key(ecu, b"\x00" * p.seed_length, levels[0])
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")


def test_virtual_provider_ford():
    reg = SecurityProviderRegistry()
    # Find a Ford-ish provider by provider name containing Ford? Use PowertrainDelphi (Ford).
    delphi_ecus = [ecu for (ecu, lvl) in reg._entries if any(
        pp.provider == "PowertrainDelphiSecurityAlgo" for pp in reg.lookup(ecu, lvl))]
    assert delphi_ecus, "no Delphi (Ford) provider"
    ecu = delphi_ecus[0]
    level = next(k[1] for k in reg._entries if k[0] == ecu)
    p = reg.lookup(ecu, level)[0]
    assert p.provider == "PowertrainDelphiSecurityAlgo"
    algo_reg = SecurityAlgorithmRegistry()
    try:
        algo_reg.compute_key(ecu, b"\x00" * p.seed_length, level)
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")


def test_virtual_unconfigured_raises():
    algo_reg = SecurityAlgorithmRegistry()
    try:
        algo_reg.compute_key("TOTALLY_UNKNOWN_ECU", b"\x00", 1)
    except NoAlgorithmConfiguredError:
        return
    raise AssertionError("expected NoAlgorithmConfiguredError")


def test_virtual_connector_security_access_honest():
    # On a virtual connector the car model refuses to fabricate seed/key.
    from wildcat.cars.mercedes_c300 import MercedesC300

    car = MercedesC300()
    assert car.security_access() is True
    try:
        car.send_seed(b"\x00\x00\x00\x00")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("expected NotImplementedError (no fabricated seed)")
