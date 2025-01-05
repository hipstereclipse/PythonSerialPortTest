"""
turbo_frame.py
Enhanced TurboFrame class for controlling a Turbo Pump, e.g., "TC600".
Structures the UI similarly to the main window with labeled frames,
and ensures everything is clearly visible without cutoff.

Changes from previous:
 - We let the Toplevel auto-size or we can forcibly set geometry (like 400x350).
 - We add an individual "Retrieve" button on each status line to query that parameter.
 - We add a checkbox on each status line to choose if that parameter is included
   in the cyclical update cycle.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports

# Imports your existing communicator approach
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse


class TurboFrame(ttk.Frame):
    """
    Specialized frame for controlling a Turbo Pump, e.g. "TC600".
    Contains:
      1) Connection frame
      2) Command frame (like a mini command list)
      3) Status frame with speed/temperature/load
         - Each row has:
           [x] cyclical checkbox
           label name
           label current value
           [Retrieve] button
      4) A cyclical update mechanism with user-settable update interval,
         querying only those parameters whose checkboxes are checked.
    """

    def __init__(self, parent, main_app):
        """
        parent: The Toplevel or parent frame where this is placed.
        main_app: The main GaugeApplication to log messages and show results in the OutputFrame.
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        # References
        self.parent = parent
        self.main_app = main_app  # so we can log to the main OutputFrame
        self.connected = False

        # Internal communicator for the Turbo
        self.turbo_communicator: Optional[GaugeCommunicator] = None

        # Variables for connection
        self.turbo_port = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Disconnected")

        # Variables for cyclical reading
        self.cycle_var = tk.BooleanVar(value=False)
        self.update_interval = tk.StringVar(value="1000")  # default 1000 ms
        self.status_thread: Optional[threading.Thread] = None
        self.stop_thread = False  # A flag to stop the cyclical thread

        # Example status parameters: speed, temperature, load
        # Each has a variable to show current value, plus a BooleanVar for cyclical updates
        self.speed_var = tk.StringVar(value="---")
        self.speed_cyc = tk.BooleanVar(value=True)

        self.temp_var = tk.StringVar(value="---")
        self.temp_cyc = tk.BooleanVar(value=True)

        self.load_var = tk.StringVar(value="---")
        self.load_cyc = tk.BooleanVar(value=True)

        # Creates the UI
        self._create_widgets()

        # Forces the parent Toplevel to a suitable size for everything,
        # or let geometry managers auto-size.
        # If your Toplevel is pinned from the main app, you can do:
        # parent.geometry("400x350")
        # But we do it here for demonstration:
        if isinstance(self.parent, tk.Toplevel):
            self.parent.geometry("800x350")  # Enough space for all widgets

    def _create_widgets(self):
        """
        Builds the layout in 4 labeled frames:
          1) Turbo Connection
          2) Turbo Commands
          3) Turbo Status (with checkboxes and retrieve buttons)
          4) Cyclical reading controls
        """
        # 1) Connection Frame
        conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(conn_frame, text="Turbo Port:").pack(side=tk.LEFT, padx=5)
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo = ttk.Combobox(
            conn_frame,
            textvariable=self.turbo_port,
            values=available_ports,
            width=15,
            state="readonly"
        )
        self.port_combo.pack(side=tk.LEFT, padx=5)
        if available_ports:
            self.turbo_port.set(available_ports[0])

        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self._toggle_connection
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        ttk.Label(conn_frame, textvariable=self.status_text).pack(side=tk.LEFT, padx=10)

        # 2) Command Frame
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # A combobox to pick from known turbo commands
        self.turbo_cmd_var = tk.StringVar()
        self.turbo_cmd_combo = ttk.Combobox(
            cmd_frame,
            textvariable=self.turbo_cmd_var,
            values=["start_pump", "stop_pump", "vent", "read_speed"],  # Example commands
            state="readonly",
            width=20
        )
        self.turbo_cmd_combo.pack(side=tk.LEFT, padx=5)

        send_btn = ttk.Button(
            cmd_frame,
            text="Send",
            command=self._send_turbo_command
        )
        send_btn.pack(side=tk.LEFT, padx=5)

        # 3) Status Frame
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # We'll use a small helper to build each row:
        # row format:  [checkbox for cyc]   <Label>   <Value label>   [Retrieve button]
        # Speed row
        self._build_status_row(
            parent=status_frame,
            row_idx=0,
            param_label="Speed (rpm):",
            param_var=self.speed_var,
            cyc_var=self.speed_cyc,
            retrieve_callback=self._retrieve_speed
        )

        # Temperature row
        self._build_status_row(
            parent=status_frame,
            row_idx=1,
            param_label="Temperature (C):",
            param_var=self.temp_var,
            cyc_var=self.temp_cyc,
            retrieve_callback=self._retrieve_temp
        )

        # Load row
        self._build_status_row(
            parent=status_frame,
            row_idx=2,
            param_label="Load (%):",
            param_var=self.load_var,
            cyc_var=self.load_cyc,
            retrieve_callback=self._retrieve_load
        )

        # 4) Cyclical reading controls
        cycle_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        cycle_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(
            cycle_frame,
            text="Enable Cyclical Updates",
            variable=self.cycle_var,
            command=self._toggle_cycle
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(cycle_frame, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(cycle_frame, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            cycle_frame,
            text="Apply",
            command=self._apply_interval
        ).pack(side=tk.LEFT, padx=5)

        # Finally, we pack 'self' to fill
        self.pack(fill=tk.BOTH, expand=True)

    def _build_status_row(self, parent, row_idx, param_label, param_var, cyc_var, retrieve_callback):
        """
        Creates a row in the status frame with:
          - A checkbutton for cyc. updates
          - A label for param_label
          - A label for param_var
          - A retrieve button to query that param alone
        """
        cyc_cb = ttk.Checkbutton(
            parent,
            variable=cyc_var
        )
        cyc_cb.grid(row=row_idx, column=0, padx=5, pady=2, sticky=tk.W)

        lbl_name = ttk.Label(parent, text=param_label)
        lbl_name.grid(row=row_idx, column=1, padx=5, pady=2, sticky=tk.W)

        lbl_value = ttk.Label(parent, textvariable=param_var)
        lbl_value.grid(row=row_idx, column=2, padx=5, pady=2, sticky=tk.W)

        btn_retrieve = ttk.Button(parent, text="Retrieve", command=retrieve_callback)
        btn_retrieve.grid(row=row_idx, column=3, padx=5, pady=2)

    # =================== Connection Methods ===================
    def _toggle_connection(self):
        """
        Toggles connect/disconnect states.
        """
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
        """
        Connects to the turbo if user chose a port.
        Uses gauge_type='TC600' if that is in your GAUGE_PARAMETERS.
        """
        port = self.turbo_port.get()
        if not port:
            messagebox.showerror("Turbo Error", "No port selected for Turbo.")
            return

        try:
            self.turbo_communicator = GaugeCommunicator(
                port=port,
                gauge_type="TC600",  # or your turbo gauge type
                logger=self.main_app  # so debug logs go to main_app.debug(...)
            )
            if self.turbo_communicator.connect():
                self.connected = True
                self.status_text.set("Connected")
                self.connect_button.config(text="Disconnect")
                self.main_app.log_message("Turbo: Connection established.")
            else:
                self.main_app.log_message("Turbo: Failed to connect.")
                self.turbo_communicator = None
        except Exception as e:
            self.main_app.log_message(f"Turbo Connect error: {str(e)}")
            self.turbo_communicator = None

    def _disconnect_turbo(self):
        """
        Disconnects if connected, logs the result.
        If cyclical reading is active, stops it.
        """
        if self.turbo_communicator:
            try:
                self.turbo_communicator.disconnect()
            except Exception as e:
                self.main_app.log_message(f"Turbo Disconnect error: {str(e)}")

        self.turbo_communicator = None
        self.connected = False
        self.status_text.set("Disconnected")
        self.connect_button.config(text="Connect")

        # Also stop cyc updates if on
        if self.cycle_var.get():
            self.cycle_var.set(False)
            self._toggle_cycle()

        self.main_app.log_message("Turbo: Disconnected.")

    def _check_connected(self) -> bool:
        """
        Checks if turbo_communicator is connected, logs if not.
        """
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    # =================== Command Frame Methods ===================
    def _send_turbo_command(self):
        """
        Sends the command selected in self.turbo_cmd_combo to the turbo device.
        We guess a read or write command_type based on known commands.
        """
        if not self._check_connected():
            return

        cmd_name = self.turbo_cmd_var.get()
        if not cmd_name:
            messagebox.showerror("Turbo Error", "No command selected.")
            return

        # We guess read vs write.
        # If your config keys define them, you can do a more robust approach.
        command_type = "?" if cmd_name.startswith("read_") else "!"
        try:
            cmd = GaugeCommand(name=cmd_name, command_type=command_type)
            resp = self.turbo_communicator.send_command(cmd)
            self._log_cmd_result(cmd_name, resp)
        except Exception as e:
            self.main_app.log_message(f"Turbo command error for {cmd_name}: {str(e)}")

    def _log_cmd_result(self, cmd_name: str, resp: GaugeResponse):
        """
        Logs a command result to the main application's OutputFrame.
        """
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name}: {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")

    # =================== Status Row "Retrieve" Methods ===================
    def _retrieve_speed(self):
        """
        Manually queries only the speed parameter, updates self.speed_var, logs result.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_speed", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.speed_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo read_speed => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo read_speed failed => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_speed exception => {str(e)}")

    def _retrieve_temp(self):
        """
        Manually queries only the temperature parameter, updates self.temp_var, logs result.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_temp", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.temp_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo read_temp => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo read_temp failed => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_temp exception => {str(e)}")

    def _retrieve_load(self):
        """
        Manually queries only the load parameter, updates self.load_var, logs result.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_load", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.load_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo read_load => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo read_load failed => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_load exception => {str(e)}")

    # =================== Cyclical Reading Methods ===================
    def _toggle_cycle(self):
        """
        Called when user checks/unchecks "Enable Cyclical Updates".
        If user checks it, we start a background thread.
        If user unchecks it, we stop the thread.
        """
        if self.cycle_var.get():
            # Turn on cyc updates
            if not self._check_connected():
                # If not connected, revert
                self.cycle_var.set(False)
                return
            self._start_cycle_thread()
        else:
            # Turn off cyc updates
            self._stop_cycle_thread()

    def _apply_interval(self):
        """
        Called when user updates the interval and clicks "Apply."
        If cyc updates are active, we restart the thread with the new interval.
        """
        if self.cycle_var.get():
            self._stop_cycle_thread()
            self._start_cycle_thread()

    def _start_cycle_thread(self):
        """
        Launches a daemon thread that repeatedly queries selected parameters.
        """
        self.stop_thread = False
        self.status_thread = threading.Thread(target=self._cycle_read_loop, daemon=True)
        self.status_thread.start()

    def _stop_cycle_thread(self):
        """
        Stops the cyc read thread by setting stop_thread = True.
        """
        self.stop_thread = True
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        self.status_thread = None

    def _cycle_read_loop(self):
        """
        Worker function that repeatedly queries only the parameters whose cyc var is checked.
        E.g. if speed_cyc is True, we do read_speed, etc.
        """
        import time
        while not self.stop_thread and self.connected and self.turbo_communicator:
            try:
                interval_ms = int(self.update_interval.get())
            except ValueError:
                interval_ms = 1000

            # Check each param's cyc var. If True, query it
            if self.speed_cyc.get():
                self._retrieve_speed()
            if self.temp_cyc.get():
                self._retrieve_temp()
            if self.load_cyc.get():
                self._retrieve_load()

            time.sleep(interval_ms / 1000.0)

        # End of loop => thread done
