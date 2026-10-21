# Architecture

Wildcat uses a **layered, pluggable architecture** so new connectors, protocols, and
vehicles can be added without touching the core logic.

```
┌─────────────────────────────────────────────┐
│  GUI  (PySide6 / Electron)                  │
├─────────────────────────────────────────────┤
│  Application  (diagnostics, programming)    │
├─────────────────────────────────────────────┤
│  Service  (sessions, logging, config)       │
├─────────────────────────────────────────────┤
│  Protocol   (CAN, KWP2000, J1850)           │
├─────────────────────────────────────────────┤
│  Connector  (J2534, PT3G, ELM327, USB-CAN)  │
├─────────────────────────────────────────────┤
│  Hardware   (USB, serial)                   │
└─────────────────────────────────────────────┘
```

## Core Concepts

### Connector
Abstracts the physical hardware. Every connector implements:
- `open()` / `close()` — lifecycle
- `send(data)` / `recv(timeout)` — raw byte I/O

Concrete connectors: `J2534Connector`, `PT3GConnector`, `ELM327Connector`,
`UsbCANConnector`.

### Protocol
The command & response language. Each protocol is negotiated over the connector:
- `CANProtocol` — ISO 15765-4 (CAN diagnostics)
- `KWP2000Protocol` — ISO 9141-2
- `J1850Protocol`

### Car
The vehicle abstraction. Wraps protocol messages into car-specific logic:
- `MercedesC300` — the 2008 C300 (user's car)
- `BMW`, `Ford`, etc. — extensible brand base

### Diagnostics / Programming
The feature layer:
- **Diagnostics**: DTC reading, live data, freeze frame, suppliers, actuation
- **Programming**: security access, ECU identification, flash/calibration updates

## Data Flow

1. GUI or app calls a service (e.g. `read_dtc()`).
2. Service resolves the `Car` for the connected hardware.
3. Car issues protocol messages through the `Connector`.
4. Connector serializes to bytes and writes to the hardware.
5. Responses travel back through the layers, parsed by the `Protocol`, and
    returned to the caller as domain objects (`DTC`, `LiveData`).

## Extensibility

- **New connector**: subclass `connectors.Connector` and implement I/O.
- **New protocol**: subclass `protocol.Protocol` and implement `send()`/`recv()`.
- **New car**: subclass `cars.CarModel` and implement ECU-specific tables.
