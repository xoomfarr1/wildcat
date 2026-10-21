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

## MVP Scope (first release)

A working first release should include:
1. One connector (J2534 or PT3G)
2. One protocol (CAN)
3. One car (Mercedes C300)
4. Read DTCs + live data
5. Basic desktop GUI

Everything else is phase 2+.
