# Wildcat

Open-source, multi-connector, multi-vehicle diagnostic and programming toolchain.

Wildcat talks to many different hardware interfaces (J2534 pass-thru, Actia PT3G VCI,
ELM327 OBD-II, USB-CAN) and decodes protocols for many different vehicle brands and
platforms — with a unified API for reading fault codes, live data, and performing
control-unit programming.

## Scope

- **Connectors**: J2534 (OEM pass-thru), PT3G VCI, ELM327 OBD-II, USB-CAN
- **Protocols**: CAN (ISO 15765-4), KWP2000 (ISO 9141-2), J1850
- **Cars**: Mercedes, BMW, Ford, VW/Audi, and extensible brand base
- **Capabilities**: DTC reading, live data, freeze frame, suppliers, actuation,
  security access, and control-unit programming
- **Platform**: Windows-native desktop (.exe via PyInstaller), optional cross-platform

## Development

```bash
poetry install
poetry run pytest
```

## Architecture

See [docs/architecture.md](docs/architecture.md).

## Roadmap

See [docs/roadmap.md](docs/roadmap.md).
