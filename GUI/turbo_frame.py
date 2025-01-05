"""
turbo_frame.py
Provides a TurboFrame class that manages a Turbo Pump (e.g., "TC600") in a layout akin to your main GUI:
 - Connection frame with two rows:
   Row 1: "Turbo Port", dropdown, "Settings" button
   Row 2: status label (left), connect/disconnect button (right)
 - "TurboSerialSettingsFrame" toggles open in the same window when user clicks "Settings",
   similar to your main serial settings approach (but specialized for the turbo).
 - Command frame (combobox + "Send" button).
 - Status frame (speed, temperature, load) each with cyc checkbox + "Retrieve" button.
 - Cyclical status update frame with two rows:
   Row 1: "Enable Cyc Updates" checkbox
   Row 2: "Update Interval (ms)", entry, "[Apply]" button
 - Auto-resizes to show all content using a finalize_geometry method so nothing is cut off.

This file does NOT remove any prior functionality (retrieve buttons, cyc toggles, etc.)—only adds
a specialized "TurboSerialSettingsFrame" in a clean, modular manner.

All logs and command results go to main_app.log_message(...),
and it uses your existing communicator approach with "TC600" if defined in GAUGE_PARAMETERS.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports

# Your existing communicator
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse


class TurboSerialSettingsFrame(ttk.LabelFrame):
    """
    A specialized serial settings frame for Turbo, similar to your main SerialSettingsFrame approach.
    Provides comboboxes for baud, data bits, parity, stop bits, plus an "Apply" button.
    We place it under the "Settings" button in the TurboFrame, toggling it open/closed.
    """

    def __init__(self, parent, apply_callback):
        """
        parent: the parent widget (TurboFrame)
        apply_callback: function to call when user clicks "Apply"—
                       passes the current settings dict, so TurboFrame can do something with them.
        """
        super().__init__(parent, text="Turbo Serial Config")

        self.apply_callback = apply_callback
        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")

        self._create_widgets()

    def _create_widgets(self):
        """
        Places comboboxes for baud, bits, parity, stop, plus an "Apply" button.
        """
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=5, pady=5)

        # Baud
        ttk.Label(frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_combo = ttk.Combobox(
            frame,
            textvariable=self.baud_var,
            values=["1200","2400","4800","9600","19200","38400","57600","115200"],
            width=7,
            state="readonly"
        )
        baud_combo.pack(side=tk.LEFT, padx=2)

        # Data bits
        ttk.Label(frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bits_combo = ttk.Combobox(
            frame,
            textvariable=self.bytesize_var,
            values=["5","6","7","8"],
            width=2,
            state="readonly"
        )
        bits_combo.pack(side=tk.LEFT, padx=2)

        # Parity
        ttk.Label(frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_combo = ttk.Combobox(
            frame,
            textvariable=self.parity_var,
            values=["N","E","O","M","S"],
            width=2,
            state="readonly"
        )
        parity_combo.pack(side=tk.LEFT, padx=2)

        # Stop bits
        ttk.Label(frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stop_combo = ttk.Combobox(
            frame,
            textvariable=self.stopbits_var,
            values=["1","1.5","2"],
            width=3,
            state="readonly"
        )
        stop_combo.pack(side=tk.LEFT, padx=2)

        # "Apply" button
        apply_btn = ttk.Button(
            frame,
            text="Apply",
            command=self._on_apply
        )
        apply_btn.pack(side=tk.LEFT, padx=5)

    def _on_apply(self):
        """
        Called when user clicks "Apply."
        We gather the settings and call the apply_callback with the dict.
        """
        settings = {
            "baudrate": int(self.baud_var.get()),
            "bytesize": int(self.bytesize_var.get()),
            "parity": self.parity_var.get(),
            "stopbits": float(self.stopbits_var.get())
        }
        self.apply_callback(settings)


class TurboFrame(ttk.Frame):
    """
    The main TurboFrame, featuring:
      - Two-row Turbo Connection
      - A togglable TurboSerialSettingsFrame for advanced config
      - Command frame
      - Status frame
      - Cyc status update
      - Auto-resizing to fit all
    """

    def __init__(self, parent, main_app):
        """
        parent: Toplevel or parent container
        main_app: reference to the main application
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        self.parent = parent
        self.main_app = main_app  # for logging to OutputFrame, etc.

        # Connection
        self.connected = False
        self.turbo_communicator: Optional[GaugeCommunicator] = None
        self.turbo_port = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Disconnected")

        # We can open/close the specialized TurboSerialSettingsFrame
        self.settings_frame: Optional[TurboSerialSettingsFrame] = None

        # cyc reading toggles
        self.cycle_var = tk.BooleanVar(value=False)
        self.update_interval = tk.StringVar(value="1000")
        self.stop_thread = False
        self.status_thread: Optional[threading.Thread] = None

        # status data
        self.speed_var = tk.StringVar(value="---")
        self.speed_cyc = tk.BooleanVar(value=True)
        self.temp_var = tk.StringVar(value="---")
        self.temp_cyc = tk.BooleanVar(value=True)
        self.load_var = tk.StringVar(value="---")
        self.load_cyc = tk.BooleanVar(value=True)

        # commands
        self.turbo_cmd_var = tk.StringVar()

        # create UI
        self._create_widgets()

        # finalize geometry
        self._finalize_geometry()

    def _create_widgets(self):
        """
        Builds the 4 main frames:
         1) Turbo Connection (two rows) + togglable TurboSerialSettingsFrame
         2) Command frame
         3) Status frame
         4) Cyc reading
        """

        # === (1) Turbo Connection Frame ===
        conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # row 1
        row1 = ttk.Frame(conn_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row1, text="Turbo Port:").pack(side=tk.LEFT, padx=5)

        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo = ttk.Combobox(
            row1,
            textvariable=self.turbo_port,
            values=ports,
            width=15,
            state="readonly"
        )
        self.port_combo.pack(side=tk.LEFT, padx=5)
        if ports:
            self.turbo_port.set(ports[0])

        # "Settings" button toggles a TurboSerialSettingsFrame below
        settings_btn = ttk.Button(
            row1,
            text="Settings",
            command=self._toggle_settings_frame
        )
        settings_btn.pack(side=tk.LEFT, padx=5)

        # row 2
        row2 = ttk.Frame(conn_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        status_lbl = ttk.Label(row2, textvariable=self.status_text)
        status_lbl.pack(side=tk.LEFT, padx=5)

        self.connect_btn = ttk.Button(
            row2,
            text="Connect",
            command=self._toggle_connection
        )
        self.connect_btn.pack(side=tk.RIGHT, padx=5)

        # We'll place the specialized settings frame below row2 if toggled
        # (we won't create it here yet; we do that in _toggle_settings_frame)

        # === (2) Command Frame
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        self.turbo_cmd_combo = ttk.Combobox(
            cmd_frame,
            textvariable=self.turbo_cmd_var,
            values=["start_pump", "stop_pump", "vent", "read_speed"],
            state="readonly",
            width=20
        )
        self.turbo_cmd_combo.pack(side=tk.LEFT, padx=5)

        send_btn = ttk.Button(cmd_frame, text="Send", command=self._send_turbo_command)
        send_btn.pack(side=tk.LEFT, padx=5)

        # === (3) Status Frame
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self._build_status_row(
            status_frame,
            label_text="Speed (rpm):",
            var=self.speed_var,
            cyc_var=self.speed_cyc,
            retrieve_callback=self._retrieve_speed
        )
        self._build_status_row(
            status_frame,
            label_text="Temperature (C):",
            var=self.temp_var,
            cyc_var=self.temp_cyc,
            retrieve_callback=self._retrieve_temp
        )
        self._build_status_row(
            status_frame,
            label_text="Load (%):",
            var=self.load_var,
            cyc_var=self.load_cyc,
            retrieve_callback=self._retrieve_load
        )

        # === (4) Cyclical Status Update
        cyc_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        cyc_frame.pack(fill=tk.X, padx=5, pady=5)

        cyc_row1 = ttk.Frame(cyc_frame)
        cyc_row1.pack(fill=tk.X, padx=5, pady=2)

        cyc_check = ttk.Checkbutton(
            cyc_row1,
            text="Enable Cyclical Updates",
            variable=self.cycle_var,
            command=self._toggle_cycle
        )
        cyc_check.pack(side=tk.LEFT, padx=5)

        cyc_row2 = ttk.Frame(cyc_frame)
        cyc_row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(cyc_row2, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(cyc_row2, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)

        apply_btn = ttk.Button(cyc_row2, text="Apply", command=self._apply_interval)
        apply_btn.pack(side=tk.LEFT, padx=5)

        # pack self
        self.pack(fill=tk.BOTH, expand=True)

    def _build_status_row(self, parent_frame, label_text, var, cyc_var, retrieve_callback):
        """
        Creates a row in the status frame:
          [Checkbutton cyc_var] label_text var(label) [Retrieve button]
        """
        row = ttk.Frame(parent_frame)
        row.pack(fill=tk.X, padx=5, pady=3)

        cyc_cb = ttk.Checkbutton(row, variable=cyc_var)
        cyc_cb.pack(side=tk.LEFT, padx=5)

        lbl = ttk.Label(row, text=label_text)
        lbl.pack(side=tk.LEFT, padx=5)

        val_lbl = ttk.Label(row, textvariable=var)
        val_lbl.pack(side=tk.LEFT, padx=5)

        rtv_btn = ttk.Button(row, text="Retrieve", command=retrieve_callback)
        rtv_btn.pack(side=tk.LEFT, padx=5)

    def _finalize_geometry(self):
        """
        After creating widgets, measure required size and set geometry
        so the Toplevel doesn't cut off any part of the UI.
        """
        if isinstance(self.parent, tk.Toplevel):
            self.parent.update_idletasks()
            needed_w = self.winfo_reqwidth() + 20
            needed_h = self.winfo_reqheight() + 20
            self.parent.geometry(f"{needed_w}x{needed_h}")

    # ========== Turbo Connection "Settings" Toggle ==========
    def _toggle_settings_frame(self):
        """
        Called when user clicks the "Settings" button in row 1 of the TurboConnection frame.
        Toggles a specialized TurboSerialSettingsFrame below row2 if it's not there, or destroys it if it is.
        """
        # If we already have one, destroy
        if self.settings_frame:
            self.settings_frame.destroy()
            self.settings_frame = None
            self._finalize_geometry()
            return

        # Otherwise, create
        # We place it inside "conn_frame" area =>
        # But we only have references to self here, so let's create a sub-frame
        self.settings_frame = TurboSerialSettingsFrame(self, apply_callback=self._on_turbo_settings_apply)
        # We place it *after* the connection frame, or we can do it right here.
        # Let's just pack it right below the parent frame:
        self.settings_frame.pack(fill=tk.X, padx=5, pady=5)

        self._finalize_geometry()

    def _on_turbo_settings_apply(self, settings: dict):
        """
        Called when user clicks "Apply" in the TurboSerialSettingsFrame.
        This is analogous to how your main GUI updates serial settings for the gauge.
        """
        # If we have a communicator and it's open, apply these settings
        if self.turbo_communicator and self.turbo_communicator.ser and self.turbo_communicator.ser.is_open:
            try:
                self.turbo_communicator.ser.baudrate = settings["baudrate"]
                self.turbo_communicator.ser.bytesize = settings["bytesize"]
                self.turbo_communicator.ser.parity   = settings["parity"]
                self.turbo_communicator.ser.stopbits = settings["stopbits"]

                # we can log that the turbo settings changed
                self.main_app.log_message(f"Turbo serial settings updated: {settings}")
            except Exception as e:
                self.main_app.log_message(f"Failed to update Turbo serial settings: {str(e)}")
        else:
            self.main_app.log_message("Turbo not connected. Settings will apply after connect?")

    # ========== Connect/Disconnect Methods ==========
    def _toggle_connection(self):
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
        port = self.turbo_port.get()
        if not port:
            messagebox.showerror("Turbo Error", "No port selected for Turbo.")
            return

        try:
            self.turbo_communicator = GaugeCommunicator(
                port=port,
                gauge_type="TC600",  # or your actual turbo gauge
                logger=self.main_app
            )
            if self.turbo_communicator.connect():
                self.connected = True
                self.status_text.set("Connected")
                self.connect_btn.config(text="Disconnect")
                self.main_app.log_message("Turbo: Connection established.")
            else:
                self.main_app.log_message("Turbo: Failed to connect.")
                self.turbo_communicator = None
        except Exception as e:
            self.main_app.log_message(f"Turbo Connect error: {str(e)}")
            self.turbo_communicator = None

    def _disconnect_turbo(self):
        if self.turbo_communicator:
            try:
                self.turbo_communicator.disconnect()
            except Exception as e:
                self.main_app.log_message(f"Turbo Disconnect error: {str(e)}")

        self.turbo_communicator = None
        self.connected = False
        self.status_text.set("Disconnected")
        self.connect_btn.config(text="Connect")

        if self.cycle_var.get():
            self.cycle_var.set(False)
            self._toggle_cycle()

        self.main_app.log_message("Turbo: Disconnected.")

    def _check_connected(self) -> bool:
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    # ========== Command Frame Methods ==========
    def _send_turbo_command(self):
        """
        Sends whichever command is selected in turbo_cmd_var (start_pump, stop_pump, etc.).
        """
        if not self._check_connected():
            return
        cmd_name = self.turbo_cmd_var.get().strip()
        if not cmd_name:
            messagebox.showerror("Turbo Error", "No turbo command selected.")
            return

        cmd_type = "?" if cmd_name.startswith("read_") else "!"
        try:
            cmd = GaugeCommand(name=cmd_name, command_type=cmd_type)
            resp = self.turbo_communicator.send_command(cmd)
            self._log_cmd_result(cmd_name, resp)
        except Exception as e:
            self.main_app.log_message(f"Turbo command error for {cmd_name}: {str(e)}")

    def _log_cmd_result(self, cmd_name: str, resp: GaugeResponse):
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name} => {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")

    # ========== Retrieve Methods for each Status row ==========
    def _retrieve_speed(self):
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_speed", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.speed_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo read_speed => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo read_speed => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_speed exception => {str(e)}")

    def _retrieve_temp(self):
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_temp", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.temp_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo read_temp => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo read_temp => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_temp exception => {str(e)}")

    def _retrieve_load(self):
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_load", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.load_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo read_load => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo read_load => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_load exception => {str(e)}")

    # ========== Cyclical Reading Methods ==========
    def _toggle_cycle(self):
        if self.cycle_var.get():
            if not self._check_connected():
                self.cycle_var.set(False)
                return
            self._start_cycle_thread()
        else:
            self._stop_cycle_thread()

    def _apply_interval(self):
        if self.cycle_var.get():
            self._stop_cycle_thread()
            self._start_cycle_thread()

    def _start_cycle_thread(self):
        self.stop_thread = False
        self.status_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self.status_thread.start()

    def _stop_cycle_thread(self):
        self.stop_thread = True
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        self.status_thread = None

    def _cycle_loop(self):
        import time

        while not self.stop_thread and self.connected and self.turbo_communicator:
            try:
                interval = int(self.update_interval.get())
            except ValueError:
                interval = 1000

            if self.speed_cyc.get():
                self._retrieve_speed()
            if self.temp_cyc.get():
                self._retrieve_temp()
            if self.load_cyc.get():
                self._retrieve_load()

            time.sleep(interval / 1000.0)

        # done
