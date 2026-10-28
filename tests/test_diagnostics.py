from wildcat.cars import MercedesC300
from wildcat.diagnostics import (
    Diagnostics,
)


def test_diagnostics_dtc():
    car = MercedesC300()
    d = Diagnostics(car)
    assert d.read_dtc() == []
    d.clear_dtc()
    assert d.read_dtc() == []


def test_live_data():
    car = MercedesC300()
    d = Diagnostics(car)
    data = d.read_live_data()
    assert data == []


def test_freeze_frame():
    car = MercedesC300()
    ff = Diagnostics(car).read_freeze_frame()
    assert ff.data == []


def test_supplier():
    car = MercedesC300()
    si = Diagnostics(car).read_supplier_info()
    assert si.name


def test_actuator():
    car = MercedesC300()
    assert Diagnostics(car).actuate("fan", True) is True
