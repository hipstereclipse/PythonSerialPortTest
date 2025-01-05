"""
turbo_frame.py
Defines the TurboFrame class which provides a GUI for communicating with a Turbo controller (e.g., "TC600").
This frame is structured similarly to the main window, using labeled frames and a "command frame" style
for selecting and issuing commands, plus a section to cyclically update statuses.

How it works:
 - The user picks a COM port for the Turbo, connects, then sees sections:
    1) Connection & Basic Info
    2) Command Section (like a mini 'CommandFrame' for Turbo commands)
    3) A "Status" section that displays various parameter values (speed, temperature, etc.)
    4) An "Update Interval" approach to cycle queries of the Turbo's statuses, similarly
      to how the main window has "continuous reading."

All logs and command results are displayed in the main window's OutputFrame via main_app.log_message(...).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue

from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse
import serial.tools.list_ports


class TurboFrame(ttk.Frame):
    """
    A specialized frame for controlling a Turbo controller (like "TC600").
    It imitates the structure of the main window:
      - A top section for connection
      - A 'command frame' style list of possible commands
      - A status section with multiple parameters
      - An update interval to cyclically refresh status if desired
    """

    def __init__(self, parent, main_app):
        """
        parent: Toplevel or parent frame
        main_app: reference to the main GaugeApplication, so we can log or show outputs
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        # References
        self.parent = parent
        self.main_app = main_app  # so we can call main_app.log_message()

        # Internal communicator for the Turbo
        self.turbo_communicator: Optional[GaugeCommunicator] = None
        self.connected = False

        # Variables for COM port, status text, update interval, and a reading thread if cycling
        self.turbo_port = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Disconnected")
        self.update_interval = tk.StringVar(value="1000")  # ms
        self.cycle_var = tk.BooleanVar(value=False)

        # We also store some example turbo parameters to display in the status section
        self.speed_var = tk.StringVar(value="---")
        self.temp_var = tk.StringVar(value="---")
        self.load_var = tk.StringVar(value="---")

        # A queue for status updates if we do cyclical reading
        self.status_queue = queue.Queue()
        self.status_thread: Optional[threading.Thread] = None

        self._create_widgets()

    def _create_widgets(self):
        """
        Creates the entire layout, structured similarly to the main window:
          1) Connection Frame
          2) Command Frame (like the main window's CommandFrame for turbo)
          3) Status Frame (shows speed, temperature, load, etc.)
          4) Update Interval & cyclical toggle
        """

        # === 1) Connection Frame ===
        conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Row for port selection
        port_label = ttk.Label(conn_frame, text="Turbo Port:")
        port_label.pack(side=tk.LEFT, padx=5)

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

        # Connect/Disconnect button
        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self._toggle_connection
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # A label to display connection status
        status_label = ttk.Label(conn_frame, textvariable=self.status_text)
        status_label.pack(side=tk.LEFT, padx=10)

        # === 2) Command Frame (like main_app command_frame) ===
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # We create a "commands" Combobox that lists possible Turbo commands
        # For instance, "start_pump", "stop_pump", "vent", "read_speed", etc.
        self.turbo_cmd_var = tk.StringVar()
        self.turbo_cmd_combo = ttk.Combobox(
            cmd_frame,
            textvariable=self.turbo_cmd_var,
            values=["start_pump", "stop_pump", "vent", "read_speed"],
            state="readonly",
            width=20
        )
        self.turbo_cmd_combo.pack(side=tk.LEFT, padx=5)

        # A button to "Send" the selected command
        send_button = ttk.Button(
            cmd_frame,
            text="Send",
            command=self._send_turbo_command
        )
        send_button.pack(side=tk.LEFT, padx=5)

        # === 3) Status Frame for parameters ===
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # We show e.g. Speed, Temperature, Load
        ttk.Label(status_frame, text="Speed (rpm):").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        ttk.Label(status_frame, textvariable=self.speed_var).grid(row=0, column=1, padx=5, pady=3, sticky=tk.W)

        ttk.Label(status_frame, text="Temperature (C):").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
        ttk.Label(status_frame, textvariable=self.temp_var).grid(row=1, column=1, padx=5, pady=3, sticky=tk.W)

        ttk.Label(status_frame, text="Load (%):").grid(row=2, column=0, padx=5, pady=3, sticky=tk.W)
        ttk.Label(status_frame, textvariable=self.load_var).grid(row=2, column=1, padx=5, pady=3, sticky=tk.W)

        # === 4) Update Interval & cyclical toggle, similar to main window's approach
        update_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        update_frame.pack(fill=tk.X, padx=5, pady=5)

        # A checkbutton to turn cyclical updates on/off
        ttk.Checkbutton(
            update_frame,
            text="Enable Cyclical Updates",
            variable=self.cycle_var,
            command=self._toggle_cycle
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(update_frame, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)

        ttk.Entry(
            update_frame,
            textvariable=self.update_interval,
            width=6
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            update_frame,
            text="Apply",
            command=self._apply_cycle_interval
        ).pack(side=tk.LEFT, padx=5)

    def _toggle_connection(self):
        """
        Toggles connect/disconnect to the Turbo communicator
        """
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
        """
        Creates a GaugeCommunicator for "TC600" if user selects a port, tries to connect,
        logs results in the main app's OutputFrame.
        """
        port = self.turbo_port.get()
        if not port:
            messagebox.showerror("Turbo Error", "No port selected for Turbo.")
            return

        try:
            self.turbo_communicator = GaugeCommunicator(
                port=port,
                gauge_type="TC600",   # or whatever your turbo gauge type is
                logger=self.main_app  # so debug lines go to main_app.debug(...)
            )
            if self.turbo_communicator.connect():
                self.connected = True
                self.status_text.set("Connected")
                self.connect_button.config(text="Disconnect")

                # We log a message
                self.main_app.log_message("Turbo: Connection established.")
            else:
                self.main_app.log_message("Turbo: Failed to connect.")
                self.turbo_communicator = None
        except Exception as e:
            self.main_app.log_message(f"Turbo Connection error: {str(e)}")
            self.turbo_communicator = None

    def _disconnect_turbo(self):
        """
        Disconnects from turbo communicator if connected, logs the result.
        """
        if self.turbo_communicator:
            try:
                self.turbo_communicator.disconnect()
            except Exception as e:
                self.main_app.log_message(f"Turbo Disconnection error: {str(e)}")

        self.turbo_communicator = None
        self.connected = False
        self.status_text.set("Disconnected")
        self.connect_button.config(text="Connect")

        # If cyclical reading was active, we turn it off
        if self.cycle_var.get():
            self.cycle_var.set(False)
            self._toggle_cycle()

        self.main_app.log_message("Turbo: Disconnected.")

    def _send_turbo_command(self):
        """
        Sends the selected command from the command combo box to the turbo communicator.
        """
        if not self._check_connection():
            return

        cmd_name = self.turbo_cmd_var.get().strip()
        if not cmd_name:
            messagebox.showerror("Turbo Error", "No turbo command selected.")
            return

        # Determine whether it's a read (?) or write (!)
        # For example, if your gauge parameters define read vs write. We guess "?" or "!" here:
        # In reality, you'd map command_name => command_type from your config.
        command_type = "?"
        # We guess that commands like "start_pump", "stop_pump", "vent" are write commands
        if cmd_name in ["start_pump", "stop_pump", "vent"]:
            command_type = "!"

        try:
            cmd = GaugeCommand(name=cmd_name, command_type=command_type)
            response = self.turbo_communicator.send_command(cmd)
            self._log_cmd_result(cmd_name, response)
        except Exception as e:
            self.main_app.log_message(f"Turbo command error for {cmd_name}: {str(e)}")

    def _check_connection(self) -> bool:
        """
        Checks if turbo_communicator is available and connected, logs an error if not.
        """
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    def _log_cmd_result(self, cmd_name: str, resp: GaugeResponse):
        """
        Logs the result of a command to the main OutputFrame via main_app.log_message(...).
        """
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name}: {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")

    def _toggle_cycle(self):
        """
        Called when user toggles "Enable Cyclical Updates".
        If on => starts a thread to cycle read statuses.
        If off => stops it.
        """
        if self.cycle_var.get():
            if not self._check_connection():
                # If not connected, revert the check
                self.cycle_var.set(False)
                return

            # Start a cyclical reading thread
            self._start_cycle_thread()
        else:
            # Stop it if on
            self._stop_cycle_thread()

    def _apply_cycle_interval(self):
        """
        Called when user updates the interval and hits "Apply".
        If cyclical reading is on, we restart the cycle thread with new interval.
        """
        if self.cycle_var.get():
            self._stop_cycle_thread()
            self._start_cycle_thread()

    def _start_cycle_thread(self):
        """
        Creates and starts a background thread that periodically updates turbo statuses
        by reading speed, temperature, load, etc.
        """
        self.status_thread = threading.Thread(target=self._cycle_thread_loop, daemon=True)
        self.status_thread.start()

    def _stop_cycle_thread(self):
        """
        Signals the cyclical reading thread to stop by toggling cycle_var to False
        and letting the thread exit.
        """
        if self.status_thread and self.status_thread.is_alive():
            # We'll rely on cycle_var to stop the loop
            self.status_thread = None

    def _cycle_thread_loop(self):
        """
        Worker function that repeatedly queries the turbo for updated statuses
        (speed, temperature, etc.), then updates self.*_var and logs results.
        Similar to your continuous reading approach in the main window.
        """
        import time

        while self.cycle_var.get() and self.connected and self.turbo_communicator:
            # We read speed, temp, load as examples
            self._query_speed()
            self._query_temp()
            self._query_load()

            # Sleep for interval (in ms)
            try:
                interval_ms = int(self.update_interval.get())
            except ValueError:
                interval_ms = 1000

            time.sleep(interval_ms / 1000.0)

    def _query_speed(self):
        """
        Example function that sends "read_speed" and updates speed_var if success.
        """
        if not self._check_connection():
            return
        try:
            cmd = GaugeCommand(name="read_speed", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.speed_var.set(resp.formatted_data)
            else:
                self.main_app.log_message(f"Turbo read_speed error => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_speed exception => {str(e)}")

    def _query_temp(self):
        """
        Example function that sends "read_temp" and updates temp_var if success.
        (You must define "read_temp" in GAUGE_PARAMETERS if you want this.)
        """
        if not self._check_connection():
            return
        try:
            cmd = GaugeCommand(name="read_temp", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.temp_var.set(resp.formatted_data)
            else:
                self.main_app.log_message(f"Turbo read_temp error => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_temp exception => {str(e)}")

    def _query_load(self):
        """
        Example function that sends "read_load" and updates load_var if success.
        (Again, define "read_load" in your GAUGE_PARAMETERS if desired.)
        """
        if not self._check_connection():
            return
        try:
            cmd = GaugeCommand(name="read_load", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.load_var.set(resp.formatted_data)
            else:
                self.main_app.log_message(f"Turbo read_load error => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_load exception => {str(e)}")
