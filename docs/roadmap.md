# Wildcat Roadmap

## Phase 0 — Foundation
- [x] Project skeleton (pyproject, poetry, ruff/mypy)
- [x] Connector abstract base
- [x] CAN frame model
- [x] Car model abstract base

## Phase 1 — Connector Drivers
- [ ] J2534 pass-thru driver (OEM protocol)
- [ ] PT3G VCI driver (user's hardware)
- [ ] ELM327 OBD-II driver
- [ ] USB-CAN adapter driver

## Phase 2 — Protocol Layer
- [ ] CAN framing / ISO 15765-4
- [ ] KWP2000 (ISO 9141-2)
- [ ] J1850
- [ ] Protocol negotiation handshake

## Phase 3 — Car Models
- [x] `CarModel` abstract base
- [ ] Mercedes C300 (2008)
- [ ] BMW
- [ ] Ford
- [ ] VW/Audi

## Phase 4 — Diagnostics
- [x] DTC reading
- [x] Live data
- [ ] Freeze frame
- [ ] Suppliers
- [ ] Actuator control

## Phase 5 — Programming
- [ ] Security access
- [ ] ECU identification
- [ ] Flash/calibration updates

## Phase 6 — GUI & Packaging
- [ ] PySide6 desktop UI
- [ ] Dark-themed dashboard
- [ ] PyInstaller Windows .exe
- [ ] Documentation + release

## Dev tooling

- **odxtools** (dev-only, optional): reverse-engineer Mercedes/ODX diagnostic sessions.
  - `odxtools snoop <pdx> --can <interface>` — live-decode a diagnostic session
  - `odxtools decode <pdx> <hex>` — decode raw hex to named parameters
  - `odxtools list <pdx> --services` — enumerate services for an ECU
  - Use a Mercedes PDX to inform `cars/mercedes_c300.py` service definitions.
  - Not a production dependency; `core/uds.py` stays hand-rolled until a PDX is sourced.

## MVP Scope (first release)

A working first release should include:
1. One connector (J2534 or PT3G)
2. One protocol (CAN)
3. One car (Mercedes C300)
4. Read DTCs + live data
5. Basic desktop GUI

Everything else is phase 2+.

## Xentry-Portal integration (2026-10-28)
Implemented from https://github.com/Xentry-Portal/mercedes-xentry-diagnosis-portal:
- `protocol/uds_services.py`: UDS service-id map, session types, ReadDTCInformation sub-functions, TesterPresent constants, DTC status-bit decoder (adapted from Caring Caribou).
- `protocol/kline.py`: `KLineSession.tester_present()` (0x3E keepalive) and `KLineSession.read_dtcs_uds()` (UDS 0x19 0x02 ReadDTCInformation decoder).

Deferred (need CAN hardware / Rust toolchain / larger refactor):
- ISO-TP segmented transport (`iso15765_2.py`) — needs raw CAN frames; not applicable to serial ELM327/K-line.
- UDS discovery / ECU auto-scan (`caringcaribou_uds.py`, `ecu_scanner.py`) — CAN arbitration-id scanning.
- Mercedes CBF diagnostic-container parsing (`rust/cbf_parser.rs`, `cbf_dtc.rs`) — requires Rust build; would give MercedesC300 real DTC descriptions.
- J2534 passthru hardware abstraction (`rust/passthru_api.rs`) — only if a J2534 adapter is acquired.
- `transport_interface.py` generalization — future refactor when CAN transport lands.
