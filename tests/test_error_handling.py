from wildcat.core.exceptions import (
    CarError,
    ConnectorError,
    DiagnosticError,
    ProgrammingError,
    ProtocolError,
    WildcatError,
)


def test_hierarchy():
    for cls in (ConnectorError, ProtocolError, CarError, DiagnosticError, ProgrammingError):
        assert issubclass(cls, WildcatError)
        assert issubclass(cls, Exception)


def test_instantiation():
    e = ConnectorError("boom")
    assert str(e) == "boom"
    assert isinstance(e, WildcatError)
