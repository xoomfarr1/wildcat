from wildcat.protocol.uds_services import dtc_status_name, service_name


def test_service_name_known():
    assert service_name(0x10) == "DiagnosticSessionControl"
    assert service_name(0x19) == "ReadDTCInformation"
    assert service_name(0x3E) == "TesterPresent"


def test_service_name_unknown():
    assert service_name(0xAB) == "Unknown(0xAB)"


def test_dtc_status_name_none():
    assert dtc_status_name(0x00) == "none"


def test_dtc_status_name_single_bit():
    assert dtc_status_name(0x08) == "confirmedDTC"


def test_dtc_status_name_multiple_bits():
    result = dtc_status_name(0x09)
    assert "testFailed" in result
    assert "confirmedDTC" in result
