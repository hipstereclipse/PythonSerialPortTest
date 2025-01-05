"""
turbo_frame.py
Provides a compact TurboFrame for controlling a Turbo Pump (e.g. "TC600").

Features:
 - Connection frame (2 rows):
   Row 1: "Port:" + OptionMenu + "Refresh", "Turbo:" + combobox
   Row 2: [Connection Status], [Connect Button], [Settings Button]
   => We store self.conn_frame as an instance attribute so we can resize it in _toggle_settings_frame.
 - A specialized TurboSerialSettingsFrame toggled below row2, forcing geometry recalcs.
 - Manual & Quick Commands, cyc toggles, retrieve, logs remain unchanged.
 - Example usage of self.conn_frame.config(width=..., height=...) + pack_propagate(False)
   inside _toggle_settings_frame to forcibly adjust the connection frame size.
 - Parameter entry is disabled unless the command is in "Set" (!) mode.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports

# Your communicator
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse

# Adjust if needed for your TurboSerialSettingsFrame location
from .turbo_serial_settings_frame import TurboSerialSettingsFrame


class TurboFrame(ttk.Frame):
    """
    TurboFrame: A compact GUI for controlling a Turbo Pump.
    Stores self.conn_frame as an instance attribute so we can forcibly resize
    it in _toggle_settings_frame if desired.
    """

    def __init__(self, parent, main_app):
        """
        parent   : Toplevel or container
        main_app : the main application, so we can log to output
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        # References
        self.parent = parent
        self.main_app = main_app

        # Tracks the connection & communicator
        self.connected = False
        self.turbo_communicator: Optional[GaugeCommunicator] = None

        # StringVars for port, turbo, status
        self.selected_port = tk.StringVar(value="")
        self.selected_turbo = tk.StringVar(value="TC600")
        self.status_text = tk.StringVar(value="Disconnected")

        # A specialized settings frame reference
        self.settings_frame: Optional[TurboSerialSettingsFrame] = None

        # cyc reading
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
        Creates the layout in four main sections:
         1) self.conn_frame for the connection (2 rows)
         2) Commands frame
         3) Status frame
         4) Cyc reading
        """
        # We store the connection frame as an instance attribute
        self.conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        # We pack it so it is displayed
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

        # Row 2 => [status, connect, settings]
        row2 = ttk.Frame(self.conn_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row2, textvariable=self.status_text).pack(side=tk.LEFT, padx=5)
        self.connect_btn = ttk.Button(row2, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        settings_btn = ttk.Button(row2, text="Settings", command=self._toggle_settings_frame)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # A container for the specialized settings frame if toggled
        self.settings_container = ttk.Frame(self.conn_frame)
        self.settings_container.pack(fill=tk.X, padx=5, pady=5)

        # Commands
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Manual command
        manual_frame = ttk.LabelFrame(cmd_frame, text="Manual Command")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(manual_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        manual_entry = ttk.Entry(manual_frame, textvariable=self.manual_command_var, width=40)
        manual_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        manual_send_btn = ttk.Button(manual_frame, text="Send", command=self._send_manual_command)
        manual_send_btn.pack(side=tk.LEFT, padx=5)

        # Quick commands
        quick_frame = ttk.LabelFrame(cmd_frame, text="Quick Commands")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(quick_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        self.quick_cmd_combo = ttk.Combobox(
            quick_frame,
            textvariable=self.quick_cmd_var,
            values=["start_pump - Start turbo",
                    "stop_pump - Stop turbo",
                    "vent - Vent turbo",
                    "read_speed - Read speed"],
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
        quick_send_btn.pack(side=tk.LEFT, padx=5)

        self.desc_label = ttk.Label(cmd_frame, textvariable=self.desc_var, wraplength=400)
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

        # Status
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self._build_status_row(status_frame, "Speed (rpm):", self.speed_var, self.speed_cyc, self._retrieve_speed)
        self._build_status_row(status_frame, "Temperature (C):", self.temp_var, self.temp_cyc, self._retrieve_temp)
        self._build_status_row(status_frame, "Load (%):", self.load_var, self.load_cyc, self._retrieve_load)

        # cyc
        cyc_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        cyc_frame.pack(fill=tk.X, padx=5, pady=5)

        cyc_row1 = ttk.Frame(cyc_frame)
        cyc_row1.pack(fill=tk.X, padx=5, pady=2)
        cyc_chk = ttk.Checkbutton(cyc_row1, text="Enable Cyclical Updates",
                                  variable=self.cycle_var,
                                  command=self._toggle_cycle)
        cyc_chk.pack(side=tk.LEFT, padx=5)

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
        rtv_btn.pack(side=tk.LEFT, padx=5)

    # ========== Updating param entry state ==========
    def _update_param_state(self, *args):
        """
        Disables param_entry if cmd_type_var == "?"
        Enables if cmd_type_var == "!".
        """
        if self.cmd_type_var.get() == "!":
            self.param_entry.config(state="normal")
        else:
            self.param_entry.config(state="disabled")

    # ========== Toggling specialized settings & forcibly resizing conn_frame ==========
    def _toggle_settings_frame(self):
        """
        Called when user clicks 'Settings' in row2 of the connection frame.
        We forcibly resize the conn_frame by calling .config(width=..., height=...).
        We also call pack_forget/destroy if the settings frame is present, or create it if not.
        Then we call _finalize_geometry to recalc everything.
        """
        if self.settings_frame:
            # Removes from layout
            self.settings_frame.pack_forget()
            # Destroys it
            self.settings_frame.destroy()
            self.settings_frame = None

            # Example forcibly resizing the conn_frame to a smaller size
            self.conn_frame.config(width=200, height=80)
            # Tells Tk not to override the forced size
            self.conn_frame.pack_propagate(False)

            # Recalc geometry
            self._finalize_geometry()
        else:
            # Creates the specialized settings frame
            self.settings_frame = TurboSerialSettingsFrame(
                parent=self.settings_container,
                apply_callback=self._on_turbo_settings_apply
            )
            self.settings_frame.pack(fill=tk.X, padx=5, pady=5)

            # Forces the conn_frame to a bigger size
            self.conn_frame.config(width=500, height=150)
            self.conn_frame.pack_propagate(False)

            # Recalc geometry
            self._finalize_geometry()

    def _on_turbo_settings_apply(self, settings: dict):
        """
        Called when user hits 'Apply' in TurboSerialSettingsFrame.
        We apply these settings if connected, or log that they apply on connect.
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
            self.main_app.log_message("Turbo not connected. Settings will apply after connect.")

    # ========== Refresh Ports logic ==========
    def _refresh_ports(self):
        """
        Gathers available COM ports, populates OptionMenu to let user pick one.
        """
        ports = [p.device for p in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(label=port, command=lambda p=port: self.selected_port.set(p))
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    # ========== Connect/Disconnect ==========
    def _toggle_connection(self):
        """
        Toggles between connected and disconnected states.
        """
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
        """
        Attempts to create a GaugeCommunicator with the selected port and turbo,
        connects, updates status & logs.
        """
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
        """
        Disconnects if present, updates status & logs, stops cyc if needed.
        """
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
        """
        Returns True if we are connected, logs if not.
        """
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    # ========== Manual + Quick Commands ==========

    def _send_manual_command(self):
        """
        Sends a manual command if connected, logs the result.
        """
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
        """
        Sends the selected quick command from quick_cmd_combo.
        Uses cmd_type_var to decide query vs set, uses param_var if set.
        """
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
                cmd = GaugeCommand(
                    name=cmd_name,
                    command_type="!",
                    parameters={"value": param_value} if param_value else None
                )
            else:
                cmd = GaugeCommand(name=cmd_name, command_type="?")

            resp = self.turbo_communicator.send_command(cmd)
            self._log_cmd_result(cmd_name, resp)
        except Exception as e:
            self.main_app.log_message(f"Quick command error: {str(e)}")

    def _log_cmd_result(self, cmd_name: str, resp: GaugeResponse):
        """
        Logs the result of sending a command. Called by both manual and quick command methods.
        """
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name} => {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")

    def _retrieve_speed(self):
        """
        Attempts to read the speed if connected, logs the result or any error.
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
                self.main_app.log_message(f"Turbo read_speed => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_speed exception => {str(e)}")

    def _retrieve_temp(self):
        """
        Attempts to read the temperature if connected, logs the result or any error.
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
                self.main_app.log_message(f"Turbo read_temp => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_temp exception => {str(e)}")

    def _retrieve_load(self):
        """
        Attempts to read the load if connected, logs the result or any error.
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
                self.main_app.log_message(f"Turbo read_load => {resp.error_message}")
        except Exception as e:
            self.main_app.log_message(f"Turbo read_load exception => {str(e)}")

    # ========== Cyc Reading ==========

    def _toggle_cycle(self):
        """
        Toggles cyc reading. If cyc is on and we are connected, we start a thread;
        if off, we stop the thread.
        """
        if self.cycle_var.get():
            if not self._check_connected():
                self.cycle_var.set(False)
                return
            self._start_cycle_thread()
        else:
            self._stop_cycle_thread()

    def _apply_interval(self):
        """
        Applies new cyc reading interval if cyc is on.
        """
        if self.cycle_var.get():
            self._stop_cycle_thread()
            self._start_cycle_thread()

    def _start_cycle_thread(self):
        """
        Launches a background thread that repeatedly calls retrieve
        methods if cyc toggles are on, sleeping for update_interval ms between.
        """
        self.stop_thread = False
        self.status_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self.status_thread.start()

    def _stop_cycle_thread(self):
        """
        Signals the cyc read thread to stop, then joins it briefly.
        """
        self.stop_thread = True
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        self.status_thread = None

    def _cycle_loop(self):
        """
        Worker function for cyc reading, sleeping for update_interval ms between
        speed/temp/load reads if those toggles are on.
        """
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

    # ========== Final geometry logic ==========

    def _finalize_geometry(self):
        """
        Called after building or toggling the settings frame.
        If parent is a Toplevel, we can reset geometry and recenter
        the window to the right side of the main app.
        """
        if isinstance(self.parent, tk.Toplevel):
            # Asks the Toplevel to recalc minimal size
            self.parent.geometry("")
            # Updates layout so we can measure final size
            self.parent.update_idletasks()

            # Gets the new width/height
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()

            # Reads main window coords to place this on the right
            main_x = self.main_app.root.winfo_x()
            main_y = self.main_app.root.winfo_y()
            main_w = self.main_app.root.winfo_width()
            main_h = self.main_app.root.winfo_height()

            # Offsets: place on right side
            offset_x = main_x + main_w + 30
            offset_y = main_y + (main_h - h)//2

            # Applies final geometry
            self.parent.geometry(f"{w}x{h}+{offset_x}+{offset_y}")
