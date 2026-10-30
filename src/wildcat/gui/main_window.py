"""Main application window.

Owns the single shared :class:`~wildcat.gui.connection.ConnectionModel` and the
top connection bar. The bar offers two ways to pick a vehicle:

* **VIN decode** -- type (or paste) a 17-character VIN and click *Decode*. The
  VIN is parsed into year/make/model and the cascade is pre-filled; clicking
  *Connect* then opens the session (resolved via the VIN).
* **Manual selector** -- pick a year, then a make, then a model from the
  cascading dropdowns. This is the fallback when no VIN is available.

Both paths resolve through :mod:`wildcat.cars.vin`, the single catalogue of
supported vehicles, so the VIN reader and the manual selector can never
disagree on what is wired up. Every connector offered is virtual-first, so the
GUI is fully usable with no adapter attached.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wildcat.cars import vin
from wildcat.gui.connection import ConnectionModel
from wildcat.gui.sparkle import GlassPanel
from wildcat.gui.theme import GLASS_STYLE
from wildcat.gui.views.diagnostics_view import DiagnosticsView
from wildcat.gui.views.live_data_view import LiveDataView
from wildcat.gui.views.programming_view import ProgrammingView


def _repo_root() -> Path | None:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists():
            return parent
    return None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wildcat Diagnostics")
        self.resize(1150, 740)
        self.setStyleSheet(GLASS_STYLE)

        # One shared session for the whole window.
        self.connection = ConnectionModel()
        self.connection.status_changed.connect(self._on_status)
        self.connection.error.connect(self._on_error)

        # --- connection bar -------------------------------------------------
        self._conn_combo = QComboBox()
        self._conn_combo.addItems(self.connection.available_connectors())

        detect_btn = QPushButton("Detect Cables")
        detect_btn.clicked.connect(self._detect_cables)

        push_log_btn = QPushButton("Push Log")
        push_log_btn.clicked.connect(self._push_log)

        read_vin_btn = QPushButton("Read VIN")
        read_vin_btn.clicked.connect(self._read_vin_from_car)

        self._vin_edit = QLineEdit()
        self._vin_edit.setPlaceholderText("VIN (auto-decode)")
        self._vin_edit.setMaxLength(17)
        self._vin_edit.editingFinished.connect(self._on_decode_vin)

        decode_btn = QPushButton("Decode")
        decode_btn.clicked.connect(self._on_decode_vin)

        self._year_combo = QComboBox()
        self._year_combo.currentIndexChanged.connect(self._on_year_changed)
        self._make_combo = QComboBox()
        self._make_combo.currentIndexChanged.connect(self._on_make_changed)
        self._model_combo = QComboBox()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.status_label = QLabel("Not connected")
        self.status_label.setObjectName("hint")

        bar = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Connector:"))
        row1.addWidget(self._conn_combo, 2)
        row1.addWidget(detect_btn)
        row1.addSpacing(12)
        row1.addWidget(QLabel("VIN:"))
        row1.addWidget(self._vin_edit, 2)
        row1.addWidget(decode_btn)
        row1.addSpacing(12)
        row1.addWidget(self.connect_btn)
        row1.addWidget(push_log_btn)
        row1.addWidget(read_vin_btn)
        row2 = QHBoxLayout()
        row2.addWidget(self.status_label)
        row2.addSpacing(12)
        row2.addWidget(QLabel("Year:"))
        row2.addWidget(self._year_combo, 1)
        row2.addWidget(QLabel("Make:"))
        row2.addWidget(self._make_combo, 1)
        row2.addWidget(QLabel("Model:"))
        row2.addWidget(self._model_combo, 1)
        bar.addLayout(row1)
        bar.addLayout(row2)

        self._populate_cascade()

        # Frosted-glass bar with an animated sparkle overlay.
        self._bar_panel = GlassPanel(children_layout=bar)

        # --- tabs -----------------------------------------------------------
        tabs = QTabWidget()
        tabs.addTab(DiagnosticsView(self.connection), "Diagnostics")
        tabs.addTab(LiveDataView(self.connection), "Live Data")
        tabs.addTab(ProgrammingView(self.connection), "Programming")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self._bar_panel)
        layout.addWidget(tabs)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setObjectName("hint")
        layout.addWidget(QLabel("Connection log:"))
        layout.addWidget(self._log)
        self.setCentralWidget(container)

    # --------------------------------------------------- vehicle selection --- #
    @staticmethod
    def _set_current(combo: QComboBox, value: str) -> None:
        """Set a combo to ``value`` (falls back to index 0)."""
        idx = combo.findText(value)
        combo.setCurrentIndex(max(idx, 0))

    def _populate_cascade(self) -> None:
        """Fill the Year/Make/Model combos and default to a supported car.

        Defaults to a 2008 Mercedes C-Class (the MercedesC300 platform) so a
        fresh window is ready to connect to a typical customer without extra
        clicks; falls back to the first catalogue entry if absent.
        """
        years = vin.list_years()
        self._year_combo.blockSignals(True)
        self._year_combo.clear()
        self._year_combo.addItems([str(y) for y in years])
        self._year_combo.blockSignals(False)

        # Default to the user's car when possible: 2008 Mercedes C-Class
        # (resolves to the MercedesC300 platform) so a fresh window is ready to
        # connect without extra clicks; fall back to the first catalogue entry
        # if that triplet is absent.
        first = next(
            (
                e
                for e in vin.CATALOG
                if e["make"] == "Mercedes-Benz"
                and e["year"] == 2008
                and e["model"] == "C-Class"
            ),
            vin.CATALOG[0],
        )
        # _set_vehicle drives the whole cascade under blocked signals so the
        # population is deterministic (combobox auto-selection does not fire
        # currentIndexChanged, which previously left Model empty).
        self._set_vehicle(first["year"], first["make"], first["model"])

    def _int_year(self) -> int | None:
        try:
            return int(self._year_combo.currentText())
        except ValueError:
            return None

    def _load_makes(self, year: int | None) -> None:
        """Populate the Make combo for a year without signal feedback."""
        makes = vin.makes_for_year(year) if year is not None else []
        self._make_combo.blockSignals(True)
        self._make_combo.clear()
        self._make_combo.addItems(makes)
        self._make_combo.blockSignals(False)

    def _load_models(self, year: int | None, make: str) -> None:
        """Populate the Model combo for a year+make without signal feedback."""
        models = vin.list_models(year, make) if (year is not None and make) else []
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(models)
        self._model_combo.blockSignals(False)
        if models:
            self._model_combo.setCurrentIndex(0)

    def _on_year_changed(self, index: int = -1) -> None:
        """Repopulate Make and Model when the user changes the year."""
        year = self._int_year()
        self._load_makes(year)
        # addItems auto-selects the first make; derive models from that.
        self._load_models(year, self._make_combo.currentText())

    def _on_make_changed(self, index: int = -1) -> None:
        """Repopulate Model when the user changes the make."""
        self._load_models(self._int_year(), self._make_combo.currentText())

    def _set_vehicle(self, year: int, make: str, model: str | None = None) -> None:
        """Programmatically set the year/make/model cascade in one shot."""
        self._year_combo.blockSignals(True)
        self._make_combo.blockSignals(True)
        self._model_combo.blockSignals(True)
        try:
            self._set_current(self._year_combo, str(year))
            self._load_makes(year)
            self._set_current(self._make_combo, make)
            self._load_models(year, make)
            if model:
                self._set_current(self._model_combo, model)
        finally:
            self._model_combo.blockSignals(False)
            self._make_combo.blockSignals(False)
            self._year_combo.blockSignals(False)

    def _on_decode_vin(self) -> None:
        """Decode the VIN field and pre-fill the year/make/model cascade."""
        text = self._vin_edit.text().strip().upper()
        if not text:
            return
        decoded = vin.decode_vin(text)
        if not decoded.valid:
            self.status_label.setText(f"Invalid VIN: {decoded.reason}")
            return
        triplet = vin.vehicle_triplet(text)
        if triplet is None:
            self.status_label.setText(
                f"VIN decodes to {decoded.make} {decoded.year}: no Wildcat profile"
            )
            return
        year, make, model = triplet
        self._set_vehicle(year, make, model)
        car = vin.find_vehicle(year, make, model)
        self.status_label.setText(f"VIN decoded: {car.name if car else make}")

    def _detect_cables(self) -> None:
        """Auto-detect connected serial adapters and select a connector."""
        from wildcat.connectors.detect import detect_cables

        cables = detect_cables()
        if not cables:
            self.status_label.setText("No serial adapters detected")
            return
        # Prefer the first detected cable's suggested connector type.
        first = cables[0]
        idx = self._conn_combo.findText(first.suggested_connector)
        if idx >= 0:
            self._conn_combo.setCurrentIndex(idx)
        summary = "; ".join(f"{c.port} ({c.description})" for c in cables)
        self.status_label.setText(f"Detected {len(cables)} cable(s): {summary}")
        self.log(f"Detected {len(cables)} cable(s): {summary}")

    def log(self, msg: str) -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self._log.append(line)
        # persist to repo log file so it can be pushed to GitHub
        root = _repo_root()
        if root is not None:
            log_dir = root / "logs"
            log_dir.mkdir(exist_ok=True)
            with (log_dir / "connection.log").open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def _read_vin_from_car(self) -> None:
        if not self.connection.is_connected:
            self.log("Read VIN: not connected")
            return
        conn = getattr(self.connection, "connector", None)
        if conn is None:
            self.log("Read VIN: no connector")
            return
        vin_str = None
        try:
            from wildcat.connectors.elm327 import Elm327Connector
            from wildcat.connectors.serial import SerialConnector
            from wildcat.diagnostics import obd2 as _obd2

            if isinstance(conn, Elm327Connector):
                vin_str = _obd2.read_vin(conn)
            elif isinstance(conn, SerialConnector):
                # UDS ReadDataByIdentifier 0xF190 (VIN)
                try:
                    conn.send(bytes([0x22, 0xF1, 0x90]))
                    buf = bytearray()
                    import time as _t

                    deadline = _t.monotonic() + 1.0
                    while _t.monotonic() < deadline:
                        try:
                            chunk = conn.recv(timeout=0.1)
                        except Exception:  # noqa: BLE001
                            chunk = b""
                        if chunk:
                            buf += chunk
                            if b">" in buf:
                                break
                        else:
                            _t.sleep(0.02)
                    text = buf.decode("ascii", errors="replace")
                    hexstr = "".join(c for c in text if c in "0123456789abcdefABCDEF")
                    # response: 62 F1 90 <17 ASCII bytes>
                    if hexstr.startswith("62F190"):
                        payload = hexstr[6:]
                        chars = []
                        for i in range(0, len(payload) - 1, 2):
                            try:
                                b = int(payload[i : i + 2], 16)
                            except ValueError:
                                break
                            if 32 <= b < 127:
                                chars.append(chr(b))
                        cand = "".join(chars).strip()
                        if len(cand) == 17:
                            vin_str = cand
                except Exception:  # noqa: BLE001
                    vin_str = None
        except Exception as e:  # noqa: BLE001
            self.log(f"Read VIN error: {e}")
            return
        if vin_str:
            self._vin_edit.setText(vin_str)
            self._on_decode_vin()
            self.log(f"Read VIN from car: {vin_str}")
            self.status_label.setText(f"VIN read from car: {vin_str}")
        else:
            self.log("Read VIN: no response / unsupported")
            self.status_label.setText("Could not read VIN from car")

    def _purge_cables(self) -> None:
        self.log("Purged disconnected cable state")
        self.status_label.setText("Not connected")

    def _push_log(self) -> None:
        import subprocess

        root = _repo_root()
        if root is None:
            self.log("Push Log: not a git checkout")
            return
        try:
            subprocess.run(["git", "-C", str(root), "add", "logs/connection.log"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "log: connection session"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "push"], check=True, capture_output=True, text=True)
            self.log("Pushed connection log to GitHub")
        except subprocess.CalledProcessError as e:
            self.log(f"Push Log failed: {e.stderr.strip() if e.stderr else e}")

    # ------------------------------------------------------------------ events
    def _toggle_connection(self) -> None:
        """Connect or disconnect from the selected connector + vehicle."""
        if self.connection.is_connected:
            self.connection.disconnect()
            self.connect_btn.setText("Connect")
            self._purge_cables()
            return
        connector = self._conn_combo.currentText()
        vin_text = self._vin_edit.text().strip().upper()
        try:
            if vin_text:
                # VIN-driven: let the model decode and resolve the vehicle.
                self.connection.connect_by_vin(connector, vin_text)
            else:
                # Manual cascade path.
                year_text = self._year_combo.currentText()
                year = int(year_text) if year_text else None
                if year is None:
                    self.status_label.setText("Select a supported vehicle")
                    return
                car = vin.find_vehicle(
                    year, self._make_combo.currentText(), self._model_combo.currentText()
                )
                if car is None:
                    self.status_label.setText("Select a supported vehicle")
                    return
                self.connection.connect(connector, car.name)
            self.connect_btn.setText("Disconnect")
            self.log(f"Connected via {connector}")
            # Auto-detect VIN from the vehicle when none was entered.
            if not vin_text:
                try:
                    from wildcat.diagnostics import obd2 as _obd2
                    conn = getattr(self.connection, "connector", None)
                    if conn is not None:
                        detected = _obd2.read_vin(conn)
                        if detected:
                            self._vin_edit.setText(detected)
                            self._on_decode_vin()
                            self.status_label.setText(f"Auto-detected VIN: {detected}")
                except Exception:  # noqa: BLE001,S110
                    pass
        except Exception:  # noqa: BLE001,S110 - error signal shows the dialog
            pass

    def _on_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_error(self, message: str) -> None:
        self.status_label.setText("Error")
        QMessageBox.warning(self, "Wildcat", message)
