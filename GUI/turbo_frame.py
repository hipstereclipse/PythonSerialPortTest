"""
turbo_frame.py
Defines the TurboFrame class, which provides a GUI for controlling a Turbo Pump, e.g. "TC600".

This frame:
 - Lets the user pick a COM port dedicated to the turbo connection
 - Connects/disconnects using your existing GaugeCommunicator logic
 - Offers commands: Start, Stop, Vent, Read Speed
 - Logs all results to the main window's OutputFrame via main_app.log_message(...)

You must define "TC600" in GAUGE_PARAMETERS if you want real commands recognized by your communicator.
(This is not displayed in the main gauge dropdown, but you can still use it here.)
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse
import serial.tools.list_ports


class TurboFrame(ttk.Frame):
    """
    A specialized frame for controlling a Turbo Pump, using your existing communicator approach.
    Provides start/stop/vent and speed reading commands, logs output to main_app's OutputFrame.
    """

    def __init__(self, parent, main_app):
        """
        parent: the Toplevel or parent frame
        main_app: a reference to the GaugeApplication, so we can log or show messages in OutputFrame
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        # Store references
        self.parent = parent
        self.main_app = main_app  # so we can call main_app.log_message(...)
        self.connected = False

        # We'll store a dedicated communicator for the turbo if the user wants a separate device.
        self.turbo_comm: Optional[GaugeCommunicator] = None

        # Track user-chosen port, status text, speed
        self.turbo_port = tk.StringVar(value="")
        self.status_text = tk.StringVar(value="Disconnected")
        self.speed_var = tk.StringVar(value="--- rpm")

        # Creates all widgets
        self._create_widgets()

    def _create_widgets(self):
        """
        Lays out:
         1) Connection row for port selection and connect/disconnect
         2) Basic commands row: Start Pump, Stop Pump, Vent
         3) Speed read row: label + button + displayed speed
        """
        # === Row 1: Connection row ===
        row1 = ttk.Frame(self)
        row1.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(row1, text="Turbo Port:").pack(side=tk.LEFT, padx=5)
        # We fill combo with available ports
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo = ttk.Combobox(
            row1,
            textvariable=self.turbo_port,
            values=available_ports,
            width=15,
            state="readonly"
        )
        self.port_combo.pack(side=tk.LEFT, padx=5)
        if available_ports:
            self.turbo_port.set(available_ports[0])

        self.connect_button = ttk.Button(
            row1,
            text="Connect",
            command=self._toggle_connection
        )
        self.connect_button.pack(side=tk.LEFT, padx=10)

        ttk.Label(row1, textvariable=self.status_text).pack(side=tk.LEFT, padx=5)

        # === Row 2: Basic commands row ===
        row2 = ttk.Frame(self)
        row2.pack(fill=tk.X, padx=5, pady=5)

        self.start_btn = ttk.Button(
            row2,
            text="Start Pump",
            command=self._start_pump,
            state="disabled"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(
            row2,
            text="Stop Pump",
            command=self._stop_pump,
            state="disabled"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.vent_btn = ttk.Button(
            row2,
            text="Vent",
            command=self._vent_pump,
            state="disabled"
        )
        self.vent_btn.pack(side=tk.LEFT, padx=5)

        # === Row 3: Speed read row ===
        row3 = ttk.Frame(self)
        row3.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(row3, text="Speed:").pack(side=tk.LEFT, padx=5)
        self.speed_label = ttk.Label(row3, textvariable=self.speed_var)
        self.speed_label.pack(side=tk.LEFT, padx=5)

        self.readspeed_btn = ttk.Button(
            row3,
            text="Read Speed",
            command=self._read_speed,
            state="disabled"
        )
        self.readspeed_btn.pack(side=tk.LEFT, padx=10)

    def _toggle_connection(self):
        """
        Toggles between connect/disconnect states for the turbo pump.
        """
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
        """
        Creates a GaugeCommunicator (or a separate device communicator) for 'TC600' gauge_type,
        tries to connect, and logs results to main_app's OutputFrame.
        """
        port = self.turbo_port.get()
        if not port:
            messagebox.showerror("Turbo Error", "No port selected for Turbo connection.")
            return

        try:
            # We assume your config has "TC600" for turbo commands. This won't appear in main gauge dropdown.
            self.turbo_comm = GaugeCommunicator(
                port=port,
                gauge_type="TC600",
                logger=self.main_app  # so debug logs go to main_app.debug(...) if needed
            )
            if self.turbo_comm.connect():
                self.connected = True
                self.status_text.set("Connected")
                self.connect_button.config(text="Disconnect")
                # Enable command buttons
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="normal")
                self.vent_btn.config(state="normal")
                self.readspeed_btn.config(state="normal")

                self.main_app.log_message("Turbo: Connection established.")
            else:
                self.main_app.log_message("Turbo: Failed to connect.")
                self.turbo_comm = None
        except Exception as e:
            self.main_app.log_message(f"Turbo Connect error: {str(e)}")
            self.turbo_comm = None

    def _disconnect_turbo(self):
        """
        Disconnects from the turbo communicator if connected, logs result.
        """
        if self.turbo_comm:
            try:
                self.turbo_comm.disconnect()
            except Exception as e:
                self.main_app.log_message(f"Turbo Disconnect error: {str(e)}")

        self.turbo_comm = None
        self.connected = False
        self.status_text.set("Disconnected")
        self.connect_button.config(text="Connect")

        # Disable command buttons
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.vent_btn.config(state="disabled")
        self.readspeed_btn.config(state="disabled")

        self.main_app.log_message("Turbo: Disconnected.")

    def _start_pump(self):
        """
        Sends a "start pump" command (if your config has it defined for "TC600").
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="start_pump", command_type="!")
            resp = self.turbo_comm.send_command(cmd)
            self._log_result("Start Pump", resp)
        except Exception as e:
            self.main_app.log_message(f"Turbo Start Pump error: {str(e)}")

    def _stop_pump(self):
        """
        Sends a "stop pump" command.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="stop_pump", command_type="!")
            resp = self.turbo_comm.send_command(cmd)
            self._log_result("Stop Pump", resp)
        except Exception as e:
            self.main_app.log_message(f"Turbo Stop Pump error: {str(e)}")

    def _vent_pump(self):
        """
        Sends a "vent" command to the turbo pump.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="vent", command_type="!")
            resp = self.turbo_comm.send_command(cmd)
            self._log_result("Vent Pump", resp)
        except Exception as e:
            self.main_app.log_message(f"Turbo Vent Pump error: {str(e)}")

    def _read_speed(self):
        """
        Reads the turbo pump speed and displays it in the interface,
        logs the result to the main output frame.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="read_speed", command_type="?")
            resp = self.turbo_comm.send_command(cmd)
            if resp.success:
                # Suppose resp.formatted_data is a numeric string for rpm
                self.speed_var.set(resp.formatted_data)
                self._log_result("Read Speed", resp)
            else:
                self._log_result("Read Speed", resp)
        except Exception as e:
            self.main_app.log_message(f"Turbo Read Speed error: {str(e)}")

    def _check_connected(self) -> bool:
        """
        Checks if turbo is connected, logs an error if not.
        """
        if not self.connected or not self.turbo_comm:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    def _log_result(self, cmd_name: str, resp: GaugeResponse):
        """
        Logs the command result to the main application's OutputFrame via main_app.log_message(...).
        """
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name} => {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")
