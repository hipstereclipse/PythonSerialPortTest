"""
turbo_frame.py
Provides a compact TurboFrame for controlling a Turbo Pump (e.g. "TC600").

Now includes a more comprehensive status frame, adding:
 - Electronics temperature
 - Bearing temperature
 - Error code
 - Warning code
 - Operating hours

Retains the same structural approach as before.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports
import logging

# Import your communicator
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse

# Adjust if needed for your TurboSerialSettingsFrame location
from .turbo_serial_settings_frame import TurboSerialSettingsFrame


class TurboFrame(ttk.Frame):
    """
    TurboFrame: A compact GUI for controlling a Turbo Pump (like the TC600).
    Now includes a more comprehensive 'Turbo Status' frame with multiple rows for bearing temp,
    electronics temp, error code, warning code, and operating hours.
    """

    def __init__(self, parent, main_app):
        """
        parent   : Toplevel or container
        main_app : the main application (GaugeApplication), so we can log to output
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        # References
        self.parent = parent
        self.main_app = main_app
        # Tracks whether we want to see logs in the console
        self.show_log_var = tk.BooleanVar(value=True)

        # Tracks the connection & communicator
        self.connected = False
        self.turbo_communicator: Optional[GaugeCommunicator] = None

        # StringVars for port, turbo, status
        self.selected_port = tk.StringVar(value="")
        self.selected_turbo = tk.StringVar(value="TC600")
        self.status_text = tk.StringVar(value="Disconnected")

        # A specialized settings frame reference (toggled on/off)
        self.settings_frame: Optional[TurboSerialSettingsFrame] = None

        # cyc reading
        self.cycle_var = tk.BooleanVar(value=False)      # Master on/off for cyc read
        self.update_interval = tk.StringVar(value="1000") # In milliseconds
        self.stop_thread = False
        self.status_thread: Optional[threading.Thread] = None

        # ----------------------
        # STATUS DATA VARIABLES
        # ----------------------
        # Speed
        self.speed_var = tk.StringVar(value="---")
        self.speed_cyc = tk.BooleanVar(value=True)

        # Motor temp (already in your code)
        self.temp_var = tk.StringVar(value="---")
        self.temp_cyc = tk.BooleanVar(value=True)

        # We'll keep 'load_var' from your code, but rename to 'current_var' or similar if you prefer
        self.load_var = tk.StringVar(value="---")
        self.load_cyc = tk.BooleanVar(value=True)

        # Electronics temperature
        self.temp_electr_var = tk.StringVar(value="---")
        self.temp_electr_cyc = tk.BooleanVar(value=True)  # default off or on, your choice

        # Bearing temperature
        self.temp_bearing_var = tk.StringVar(value="---")
        self.temp_bearing_cyc = tk.BooleanVar(value=True)

        # Error code
        self.error_code_var = tk.StringVar(value="---")
        self.error_code_cyc = tk.BooleanVar(value=True)

        # Warning code
        self.warning_code_var = tk.StringVar(value="---")
        self.warning_code_cyc = tk.BooleanVar(value=True)

        # Operating hours
        self.hours_var = tk.StringVar(value="---")
        self.hours_cyc = tk.BooleanVar(value=True)

        # commands
        self.manual_command_var = tk.StringVar()
        self.quick_cmd_var = tk.StringVar()
        self.cmd_type_var = tk.StringVar(value="?")  # "?" => Query, "!" => Set
        self.param_var = tk.StringVar()
        self.desc_var = tk.StringVar(self, value="")

        # Builds all widgets
        self._create_widgets()

        # Finalize geometry if needed
        self._finalize_geometry()


    def _create_widgets(self):
        """
        Builds the layout in these main sections:
         1) self.conn_frame for the connection (2 rows)
         2) Commands frame (Manual + Quick Commands)
         3) Status frame (expanded to show many parameters)
         4) Cyc reading frame
        """
        # --------------------
        # CONNECTION FRAME
        # --------------------
        self.conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        self.conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Row 1 => "Port" + refresh, "Turbo" combo
        row1 = ttk.Frame(self.conn_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row1, text="Port:").pack(side=tk.LEFT, padx=2)
        self.port_menu = ttk.OptionMenu(row1, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=2)

        refresh_btn = ttk.Button(row1, text="Refresh", command=self._refresh_ports)
        refresh_btn.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="Turbo:").pack(side=tk.LEFT, padx=5)
        turbo_list = ["TC600", "TC1200", "TC700"]
        self.turbo_combo = ttk.Combobox(
            row1,
            textvariable=self.selected_turbo,
            values=turbo_list,
            state="readonly",
            width=10
        )
        self.turbo_combo.pack(side=tk.LEFT, padx=5)
        if turbo_list:
            self.selected_turbo.set(turbo_list[0])

        settings_btn = ttk.Button(row1, text="Settings", command=self._toggle_settings_frame)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # Row 2 => [status, connect, settings]
        row2 = ttk.Frame(self.conn_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row2, textvariable=self.status_text).pack(side=tk.LEFT, padx=5)
        self.connect_btn = ttk.Button(row2, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # Container for the specialized settings frame
        self.settings_container = ttk.Frame(self.conn_frame)
        self.settings_container.pack(fill=tk.X, padx=5, pady=5)

        # --------------------
        # COMMANDS FRAME
        # --------------------
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Manual command
        manual_frame = ttk.LabelFrame(cmd_frame, text="Manual Command")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(manual_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        manual_entry = ttk.Entry(manual_frame, textvariable=self.manual_command_var, width=40)
        manual_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        manual_send_btn = ttk.Button(manual_frame, text="Send", command=self._send_manual_command)
        manual_send_btn.pack(side=tk.RIGHT, padx=5)

        # Quick commands
        quick_frame = ttk.LabelFrame(cmd_frame, text="Quick Commands")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(quick_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.quick_cmd_combo = ttk.Combobox(
            quick_frame,
            textvariable=self.quick_cmd_var,
            values=[
                "start_pump - Start turbo",
                "stop_pump - Stop turbo",
                "vent - Vent turbo",
                "get_speed - Read speed",
                "get_temp_motor - Read motor temperature",
                "get_current - Read current",
                "get_error - Read error status",
                # You can add more as you see fit...
            ],
            state="readonly",
            width=30
        )
        self.quick_cmd_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        radio_frame = ttk.Frame(quick_frame)
        radio_frame.pack(side=tk.LEFT, padx=2)
        self.query_radio = ttk.Radiobutton(radio_frame, text="Query (?)", variable=self.cmd_type_var, value="?")
        self.set_radio   = ttk.Radiobutton(radio_frame, text="Set (!)",   variable=self.cmd_type_var, value="!")
        self.query_radio.pack(side=tk.LEFT, padx=2)
        self.set_radio.pack(side=tk.LEFT, padx=2)

        self.cmd_type_var.trace("w", self._update_param_state)

        param_frame = ttk.Frame(cmd_frame)
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(param_frame, text="Parameter:").pack(side=tk.LEFT, padx=5)
        self.param_entry = ttk.Entry(param_frame, textvariable=self.param_var, width=20)
        self.param_entry.pack(side=tk.LEFT, padx=5)

        quick_send_btn = ttk.Button(param_frame, text="Send", command=self._send_quick_command)
        quick_send_btn.pack(side=tk.RIGHT, padx=5)

        self.desc_label = ttk.Label(cmd_frame, textvariable=self.desc_var, wraplength=400)
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

        # --------------------
        # STATUS FRAME
        # --------------------
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # Reuse your build_status_row for each parameter we want to show
        self._build_status_row(status_frame, "Speed (rpm):",       self.speed_var,       self.speed_cyc,       self._retrieve_speed)
        self._build_status_row(status_frame, "Current (A):",       self.load_var,        self.load_cyc,        self._retrieve_load) # or rename "Load" to "Current"
        self._build_status_row(status_frame, "Motor Temp (C):",    self.temp_var,        self.temp_cyc,        self._retrieve_temp)
        self._build_status_row(status_frame, "Electronics Temp (C):", self.temp_electr_var,    self.temp_electr_cyc,    self._retrieve_temp_electronics)
        self._build_status_row(status_frame, "Bearing Temp (C):",     self.temp_bearing_var,   self.temp_bearing_cyc,   self._retrieve_temp_bearing)
        self._build_status_row(status_frame, "Error Code:",           self.error_code_var,     self.error_code_cyc,     self._retrieve_error_code)
        self._build_status_row(status_frame, "Warning Code:",         self.warning_code_var,   self.warning_code_cyc,   self._retrieve_warning_code)
        self._build_status_row(status_frame, "Operating Hours:",      self.hours_var,          self.hours_cyc,         self._retrieve_hours)

        # --------------------
        # CYC FRAME
        # --------------------
        cyc_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        cyc_frame.pack(fill=tk.X, padx=5, pady=5)

        cyc_row1 = ttk.Frame(cyc_frame)
        cyc_row1.pack(fill=tk.X, padx=5, pady=2)

        # Creates a Checkbutton for enabling cyc reading
        cyc_chk = ttk.Checkbutton(
            cyc_row1,
            text="Enable Cyclical Updates",
            variable=self.cycle_var,
            command=self._toggle_cycle
        )
        cyc_chk.pack(side=tk.LEFT, padx=5)

        # Creates a second Checkbutton to show/hide logs in the console
        show_log_chk = ttk.Checkbutton(
            cyc_row1,
            text="Show Logs",
            variable=self.show_log_var,
            command=self._toggle_logs
        )
        show_log_chk.pack(side=tk.LEFT, padx=15)

        cyc_row2 = ttk.Frame(cyc_frame)
        cyc_row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(cyc_row2, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(cyc_row2, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)

        apply_btn = ttk.Button(cyc_row2, text="Apply", command=self._apply_interval)
        apply_btn.pack(side=tk.LEFT, padx=5)

        self.pack(fill=tk.BOTH, expand=True)
        self._refresh_ports()

        # Calls once so param is correct if default is "?"
        self._update_param_state()


    def _build_status_row(self, parent, label_text, var, cyc_var, retrieve_callback):
        """
        Builds a row with a cyc toggle, a label, a variable label, and a 'Retrieve' button.
        We pass in:
          - parent: the parent frame to hold this row
          - label_text: the text describing the parameter
          - var: a StringVar that will show the current value
          - cyc_var: a BooleanVar toggle for cyc reading
          - retrieve_callback: the function that retrieves & updates 'var'
        """
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=5, pady=3)

        cyc_cb = ttk.Checkbutton(row, variable=cyc_var)
        cyc_cb.pack(side=tk.LEFT, padx=5)

        lbl = ttk.Label(row, text=label_text)
        lbl.pack(side=tk.LEFT, padx=5)

        val_lbl = ttk.Label(row, textvariable=var)
        val_lbl.pack(side=tk.LEFT, padx=5)

        rtv_btn = ttk.Button(row, text="Retrieve", command=retrieve_callback)
        rtv_btn.pack(side=tk.RIGHT, padx=5)


    # --------
    # RETRIEVE METHODS (New ones below)
    # --------
    def _retrieve_temp_electronics(self):
        """
        Reads electronics temperature (C) if the turbo is connected,
        logs success or failure, and updates self.temp_electr_var.
        """
        if not self._check_connected():
            return
        try:
            # According to your protocol, "get_temp_electronic" is the dictionary key
            cmd = GaugeCommand(name="get_temp_electronic", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.temp_electr_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_temp_electronic => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_temp_electronic => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_temp_electronic exception => {str(e)}", level="ERROR")


    def _retrieve_temp_bearing(self):
        """
        Reads bearing temperature (C) if connected,
        logs success or failure, and updates self.temp_bearing_var.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="get_temp_bearing", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.temp_bearing_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_temp_bearing => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_temp_bearing => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_temp_bearing exception => {str(e)}", level="ERROR")


    def _retrieve_error_code(self):
        """
        Reads the current error code if connected,
        logs success or failure, and updates self.error_code_var.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="get_error", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.error_code_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_error => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_error => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_error exception => {str(e)}", level="ERROR")


    def _retrieve_warning_code(self):
        """
        Reads the current warning code if connected,
        logs success or failure, and updates self.warning_code_var.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="get_warning", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.warning_code_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_warning => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_warning => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_warning exception => {str(e)}", level="ERROR")


    def _retrieve_hours(self):
        """
        Reads the operating hours if connected,
        logs success or failure, and updates self.hours_var.
        """
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="operating_hours", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.hours_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo operating_hours => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo operating_hours => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo operating_hours exception => {str(e)}", level="ERROR")


    # -------------
    # Everything below here remains the same as your existing code
    # (connect/disconnect, cyc reading, etc.)
    # -------------


    def _update_param_state(self, *args):
        """
        Disables param_entry if cmd_type_var == "?", enables if cmd_type_var == "!".
        """
        if self.cmd_type_var.get() == "!":
            self.param_entry.config(state="normal")
        else:
            self.param_entry.config(state="disabled")


    def _toggle_settings_frame(self):
        """[Unchanged] Toggles the specialized TurboSerialSettingsFrame."""
        if self.settings_frame:
            self.settings_frame.pack_forget()
            self.settings_frame.destroy()
            self.settings_frame = None
            self.conn_frame.config(width=200, height=80)
            self.conn_frame.pack_propagate(False)
            self._finalize_geometry()
        else:
            self.settings_frame = TurboSerialSettingsFrame(
                parent=self.settings_container,
                apply_callback=self._on_turbo_settings_apply
            )
            self.settings_frame.pack(fill=tk.X, padx=5, pady=5)
            self.conn_frame.config(width=400, height=150)
            self.conn_frame.pack_propagate(False)
            self._finalize_geometry()


    def _on_turbo_settings_apply(self, settings: dict):
        """[Unchanged] Called when user hits 'Apply' in TurboSerialSettingsFrame."""
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
            self.main_app.log_message("Turbo not connected. Settings will apply after connect.")


    def _refresh_ports(self):
        """[Unchanged] Gathers available COM ports, populates OptionMenu."""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(label=port, command=lambda p=port: self.selected_port.set(p))
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")


    def _toggle_connection(self):
        """[Unchanged] Toggles between connected and disconnected states."""
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()


    def _connect_turbo(self):
        """[Unchanged] Attempts to create a GaugeCommunicator, connect, and update status."""
        port = self.selected_port.get()
        if not port:
            messagebox.showerror("Turbo Error", "No port selected for Turbo.")
            return
        try:
            self.turbo_communicator = GaugeCommunicator(
                port=port,
                gauge_type=self.selected_turbo.get(),
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
        """[Unchanged] Disconnects if present, updates status, stops cyc if needed."""
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
        """[Unchanged] Returns True if connected, logs if not."""
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True


    def _send_manual_command(self):
        """[Unchanged] Sends a manual command if connected, logs the result."""
        if not self._check_connected():
            return
        cmd_str = self.manual_command_var.get().strip()
        if not cmd_str:
            self.main_app.log_message("No manual command entered.")
            return
        try:
            cmd = GaugeCommand(name=cmd_str, command_type="!")
            resp = self.turbo_communicator.send_command(cmd)
            self._log_cmd_result(cmd_str, resp)
        except Exception as e:
            self.main_app.log_message(f"Manual command error: {str(e)}")


    def _send_quick_command(self):
        """[Unchanged] Sends quick commands from the combo."""
        if not self._check_connected():
            return
        quick_val = self.quick_cmd_var.get()
        if not quick_val:
            self.main_app.log_message("No quick command selected.")
            return
        cmd_name = quick_val.split(" - ")[0]
        command_type = self.cmd_type_var.get()
        param_value = self.param_var.get().strip()

        try:
            if command_type == "!":
                command = GaugeCommand(
                    name=cmd_name,
                    command_type="!",
                    parameters={"value": param_value} if param_value else None
                )
            else:
                command = GaugeCommand(name=cmd_name, command_type="?")

            response = self.turbo_communicator.send_command(command)
            self._log_cmd_result(cmd_name, response)

        except Exception as e:
            self.main_app.log_message(f"Quick command error: {str(e)}", level="ERROR")


    def _log_cmd_result(self, cmd_name: str, resp: GaugeResponse):
        """[Unchanged] Logs the result of sending a turbo command."""
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name} => {resp.formatted_data}")
        else:
            self.main_app.log_message(
                f"Turbo {cmd_name} failed => {resp.error_message}",
                level="ERROR"
            )


    def _retrieve_speed(self):
        """[Unchanged] Reads speed from 'get_speed' and updates self.speed_var."""
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="get_speed", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.speed_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_speed => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_speed => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_speed exception => {str(e)}", level="ERROR")


    def _retrieve_temp(self):
        """[Unchanged] Reads motor temp from 'get_temp_motor'."""
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="get_temp_motor", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.temp_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_temp_motor => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_temp_motor => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_temp_motor exception => {str(e)}", level="ERROR")


    def _retrieve_load(self):
        """[Unchanged] Reads current from 'get_current' and updates self.load_var."""
        if not self._check_connected():
            return
        try:
            cmd = GaugeCommand(name="get_current", command_type="?")
            resp = self.turbo_communicator.send_command(cmd)
            if resp.success:
                self.load_var.set(resp.formatted_data)
                self.main_app.log_message(f"Turbo get_current => {resp.formatted_data}")
            else:
                self.main_app.log_message(f"Turbo get_current => {resp.error_message}", level="ERROR")
        except Exception as e:
            self.main_app.log_message(f"Turbo get_current exception => {str(e)}", level="ERROR")


    # --------------------
    # CYC READING
    # --------------------
    def _toggle_logs(self):
        """
        Called when the user toggles the 'Show Logs' checkbox.
        If 'show_log_var' is True, we set the main_app logger to DEBUG (or INFO).
        If False, we set it to CRITICAL so console output is minimized (virtually off).
        """
        if self.show_log_var.get():
            # The user wants to see logs => set logging level to DEBUG (or INFO if you prefer).
            self.main_app.logger.setLevel(logging.DEBUG)
            self.main_app.log_message("Console logging is now ON (DEBUG).")
        else:
            # The user wants to hide logs => set logging level to CRITICAL, so only critical errors appear.
            self.main_app.logger.setLevel(logging.CRITICAL)
            self.main_app.log_message("Console logging is now OFF (CRITICAL).")

    def _toggle_cycle(self):
        """
        Toggles cyc reading. If cyc is on and we are connected, starts a thread.
        If off, stops the thread.
        """
        if self.cycle_var.get():
            if not self._check_connected():
                self.cycle_var.set(False)
                return
            self._start_cycle_thread()
        else:
            self._stop_cycle_thread()

    def _apply_interval(self):
        """[Unchanged] Re-applies new cyc reading interval if cyc is on."""
        if self.cycle_var.get():
            self._stop_cycle_thread()
            self._start_cycle_thread()


    def _start_cycle_thread(self):
        """[Unchanged] Launches background cyc reading thread."""
        self.stop_thread = False
        self.status_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self.status_thread.start()


    def _stop_cycle_thread(self):
        """[Unchanged] Signals cyc read thread to stop, then joins it."""
        self.stop_thread = True
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        self.status_thread = None


    def _cycle_loop(self):
        """
        Worker function for cyc reading, sleeping for update_interval ms between
        checks. If each cyc var is ON, calls its respective retrieval method.
        """
        import time
        while not self.stop_thread and self.connected and self.turbo_communicator:
            try:
                interval = int(self.update_interval.get())
            except ValueError:
                interval = 1000

            # Speed
            if self.speed_cyc.get():
                self._retrieve_speed()

            # Motor Temp
            if self.temp_cyc.get():
                self._retrieve_temp()

            # Current
            if self.load_cyc.get():
                self._retrieve_load()

            # Electronics Temp
            if self.temp_electr_cyc.get():
                self._retrieve_temp_electronics()

            # Bearing Temp
            if self.temp_bearing_cyc.get():
                self._retrieve_temp_bearing()

            # Error Code
            if self.error_code_cyc.get():
                self._retrieve_error_code()

            # Warning Code
            if self.warning_code_cyc.get():
                self._retrieve_warning_code()

            # Operating Hours
            if self.hours_cyc.get():
                self._retrieve_hours()

            # Sleep
            time.sleep(interval / 1000.0)


    def _finalize_geometry(self):
        """[Unchanged] Called after toggling the settings frame. Re-centers if parent is a Toplevel."""
        if isinstance(self.parent, tk.Toplevel):
            self.parent.geometry("")
            self.parent.update_idletasks()

            w = self.parent.winfo_width()
            h = self.parent.winfo_height()

            main_x = self.main_app.root.winfo_x()
            main_y = self.main_app.root.winfo_y()
            main_w = self.main_app.root.winfo_width()
            main_h = self.main_app.root.winfo_height()

            offset_x = main_x + main_w + 30
            offset_y = main_y + (main_h - h)//2

            self.parent.geometry(f"{w}x{h}+{offset_x}+{offset_y}")
