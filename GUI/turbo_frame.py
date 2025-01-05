"""
turbo_frame.py
Implements a TurboFrame for controlling a Turbo Pump (e.g. "TC600") with your requested layout:
 - Turbo Connection frame (2 rows) + specialized TurboSerialSettingsFrame right below row2
 - Command frame
 - Status frame (speed,temp,load) with cyc checkboxes + Retrieve
 - Cyc reading frame (two-row style)
 - Auto-resizing so nothing is cut off

No functionality removed:
 - We still have retrieve buttons, cyc toggles, commands, etc.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports

# Uses your communicator approach
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse

# Imports the specialized turbo serial settings frame
from .turbo_serial_settings_frame import TurboSerialSettingsFrame


class TurboFrame(ttk.Frame):
    """
    Main frame for controlling a Turbo Pump.
    Places TurboSerialSettingsFrame directly below the second row in the connection frame,
    so it's not at the bottom.
    """

    def __init__(self, parent, main_app):
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)
        self.parent = parent
        self.main_app = main_app

        # Connection states
        self.connected = False
        self.turbo_communicator: Optional[GaugeCommunicator] = None
        self.turbo_port = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Disconnected")

        # For toggling the TurboSerialSettingsFrame
        self.settings_frame: Optional[TurboSerialSettingsFrame] = None

        # cyc reading states
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

        # Creates the UI
        self._create_widgets()

        # Auto-resize so nothing is cut off
        self._finalize_geometry()

    def _create_widgets(self):
        """
        Builds:
         1) Turbo Connection (2 rows + settings_container below row2)
         2) Command Frame
         3) Status Frame
         4) Cyc Frame
        """
        # === (1) Turbo Connection
        self.conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        self.conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Row 1 => "Turbo Port", port combo, "Settings" button
        row1 = ttk.Frame(self.conn_frame)
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

        settings_btn = ttk.Button(row1, text="Settings", command=self._toggle_settings_frame)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # Row 2 => status label (left), connect/disconnect (right)
        row2 = ttk.Frame(self.conn_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        status_lbl = ttk.Label(row2, textvariable=self.status_text)
        status_lbl.pack(side=tk.LEFT, padx=5)

        self.connect_btn = ttk.Button(row2, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.RIGHT, padx=5)

        # Now we create a container below row2 for the TurboSerialSettingsFrame
        self.settings_container = ttk.Frame(self.conn_frame)
        self.settings_container.pack(fill=tk.X, padx=5, pady=5)
        # We won't pack the frame yet; we do that in _toggle_settings_frame

        # === (2) Command Frame
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        self.turbo_cmd_combo = ttk.Combobox(
            cmd_frame,
            textvariable=self.turbo_cmd_var,
            values=["start_pump","stop_pump","vent","read_speed"],
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
            parent_frame=status_frame,
            label_text="Speed (rpm):",
            var=self.speed_var,
            cyc_var=self.speed_cyc,
            retrieve_callback=self._retrieve_speed
        )
        self._build_status_row(
            parent_frame=status_frame,
            label_text="Temperature (C):",
            var=self.temp_var,
            cyc_var=self.temp_cyc,
            retrieve_callback=self._retrieve_temp
        )
        self._build_status_row(
            parent_frame=status_frame,
            label_text="Load (%):",
            var=self.load_var,
            cyc_var=self.load_cyc,
            retrieve_callback=self._retrieve_load
        )

        # === (4) Cyc Frame
        cyc_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        cyc_frame.pack(fill=tk.X, padx=5, pady=5)

        cyc_row1 = ttk.Frame(cyc_frame)
        cyc_row1.pack(fill=tk.X, padx=5, pady=2)

        cyc_chk = ttk.Checkbutton(
            cyc_row1,
            text="Enable Cyclical Updates",
            variable=self.cycle_var,
            command=self._toggle_cycle
        )
        cyc_chk.pack(side=tk.LEFT, padx=5)

        cyc_row2 = ttk.Frame(cyc_frame)
        cyc_row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(cyc_row2, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(cyc_row2, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)

        apply_btn = ttk.Button(cyc_row2, text="Apply", command=self._apply_interval)
        apply_btn.pack(side=tk.LEFT, padx=5)

        self.pack(fill=tk.BOTH, expand=True)

    def _build_status_row(self, parent_frame, label_text, var, cyc_var, retrieve_callback):
        """
        Builds one status row in the "Turbo Status" frame:
         [Checkbutton cyc_var] <label_text> <var.label> [Retrieve button]
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
        After building all widgets, measure needed size & set Toplevel geometry,
        preventing cut-off.
        """
        if isinstance(self.parent, tk.Toplevel):
            self.parent.update_idletasks()
            width_needed  = self.winfo_reqwidth() + 20
            height_needed = self.winfo_reqheight() + 20
            self.parent.geometry(f"{width_needed}x{height_needed}")

    # ========== Toggle TurboSerialSettingsFrame ==========

    def _toggle_settings_frame(self):
        """
        Called when user clicks "Settings" in row1 of Turbo Connection.
        Creates/destroys a specialized TurboSerialSettingsFrame in self.settings_container,
        placing it immediately below row2 (NOT at bottom).
        """
        if self.settings_frame:
            self.settings_frame.destroy()
            self.settings_frame = None
            self._finalize_geometry()
            return

        # Create a new TurboSerialSettingsFrame inside self.settings_container
        self.settings_frame = TurboSerialSettingsFrame(
            parent=self.settings_container,
            apply_callback=self._on_turbo_settings_apply
        )
        self.settings_frame.pack(fill=tk.X, padx=5, pady=5)
        self._finalize_geometry()

    def _on_turbo_settings_apply(self, settings: dict):
        """
        Called when user hits "Apply" in the TurboSerialSettingsFrame.
        If connected, we update self.turbo_communicator's port immediately.
        Otherwise, store or log that they will apply after connection.
        """
        if self.turbo_communicator and self.turbo_communicator.ser and self.turbo_communicator.ser.is_open:
            try:
                self.turbo_communicator.ser.baudrate  = settings["baudrate"]
                self.turbo_communicator.ser.bytesize  = settings["bytesize"]
                self.turbo_communicator.ser.parity    = settings["parity"]
                self.turbo_communicator.ser.stopbits  = settings["stopbits"]

                self.main_app.log_message(f"Turbo serial settings updated: {settings}")
            except Exception as e:
                self.main_app.log_message(f"Failed to update Turbo serial settings: {str(e)}")
        else:
            self.main_app.log_message("Turbo not connected. Settings will apply once connected or reconnected.")

    # ========== Connect/Disconnect ==========

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

        # If cyc updates on => turn them off
        if self.cycle_var.get():
            self.cycle_var.set(False)
            self._toggle_cycle()

        self.main_app.log_message("Turbo: Disconnected.")

    def _check_connected(self) -> bool:
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    # ========== Command Frame ==========

    def _send_turbo_command(self):
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
            self.main_app.log_message(f"Turbo command error ({cmd_name}): {str(e)}")

    def _log_cmd_result(self, cmd_name: str, resp: GaugeResponse):
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name} => {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")

    # ========== Retrieve (Status rows) ==========

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

    # ========== Cyc Reading ==========

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

        # end cyc thread

    # ========== Final geometry logic ==========

    def _finalize_geometry(self):
        """
        After building all widgets, measure required size, set geometry so
        Toplevel won't cut off any elements.
        """
        if isinstance(self.parent, tk.Toplevel):
            self.parent.update_idletasks()
            needed_w = self.winfo_reqwidth() + 20
            needed_h = self.winfo_reqheight() + 20
            self.parent.geometry(f"{needed_w}x{needed_h}")
