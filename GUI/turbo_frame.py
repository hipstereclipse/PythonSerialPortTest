"""
turbo_frame.py
Implements a compact TurboFrame for controlling a Turbo Pump (e.g. "TC600"),
with the second row in the connection frame showing:
 [Connection Status] [Connect Button] [Settings Button].
Toggling the TurboSerialSettingsFrame on/off forces the Toplevel to auto-resize
to a minimal (or expanded) layout, re-centering on the right side of the main window.

Additionally, the Parameter entry in the quick commands is disabled
unless the command is in "Set" (!) state.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports

# Import your communicator approach
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse

# Import the specialized TurboSerialSettingsFrame
from .turbo_serial_settings_frame import TurboSerialSettingsFrame


class TurboFrame(ttk.Frame):
    """
    Main TurboFrame with:
     - A 2-row connection frame:
       Row 1: [Port: OptionMenu + Refresh] [Turbo: Combobox]
       Row 2: [Status label, Connect button, Settings button]
       Below row2 => toggled TurboSerialSettingsFrame
     - A commands frame (manual + quick) with the Parameter entry disabled unless command_type is "!"
     - A status frame for speed/temp/load
     - A cyc update frame
     - A geometry approach that resets Toplevel geometry to "" to let it auto-resize
       each time we show/hide the settings frame, then re-centers on the right of main window.
    """

    def __init__(self, parent, main_app):
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        self.parent = parent
        self.main_app = main_app

        # Connection states
        self.connected = False
        self.turbo_communicator: Optional[GaugeCommunicator] = None

        # Port and turbo selections
        self.selected_port = tk.StringVar(value="")
        self.selected_turbo = tk.StringVar(value="TC600")
        self.status_text = tk.StringVar(value="Disconnected")

        # The toggled TurboSerialSettingsFrame
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

        # Commands (manual + quick)
        self.manual_command_var = tk.StringVar()

        self.quick_cmd_var = tk.StringVar()
        self.cmd_type_var = tk.StringVar(value="?")  # "?" => Query, "!" => Set
        self.param_var = tk.StringVar()
        self.desc_var = tk.StringVar(value="")

        # Build UI
        self._create_widgets()

        # Auto-resize to minimal after creation
        self._finalize_geometry()

    def _create_widgets(self):
        """
        Builds 4 main sections:
         1) Turbo Connection (row1 => port + refresh + turbo, row2 => status, connect, settings)
            Below row2 => container for the settings frame
         2) Turbo Commands (manual + quick)
         3) Status
         4) Cyc update
        """
        # (1) Turbo Connection
        conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Row 1 => "Port:", port menu + Refresh, "Turbo:", turbo combo
        row1 = ttk.Frame(conn_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row1, text="Port:").pack(side=tk.LEFT, padx=2)
        self.port_menu = ttk.OptionMenu(row1, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=2)

        refresh_btn = ttk.Button(row1, text="Refresh", command=self._refresh_ports)
        refresh_btn.pack(side=tk.LEFT, padx=5)

        ttk.Label(row1, text="Turbo:").pack(side=tk.LEFT, padx=5)
        turbos = ["TC600","TC1200","TC700"]
        self.turbo_combo = ttk.Combobox(row1, textvariable=self.selected_turbo,
                                        values=turbos, state="readonly", width=10)
        self.turbo_combo.pack(side=tk.LEFT, padx=5)
        if turbos:
            self.selected_turbo.set(turbos[0])

        # Row 2 => [Status, Connect, Settings]
        row2 = ttk.Frame(conn_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(row2, textvariable=self.status_text).pack(side=tk.LEFT, padx=5)
        self.connect_btn = ttk.Button(row2, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        settings_btn = ttk.Button(row2, text="Settings", command=self._toggle_settings_frame)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # container for the specialized TurboSerialSettingsFrame
        self.settings_container = ttk.Frame(conn_frame)
        self.settings_container.pack(fill=tk.X, padx=5, pady=5)

        # (2) Turbo Commands (manual + quick)
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

        # We attach a trace to cmd_type_var so we can enable/disable param entry
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

        # Initially call _update_param_state so the param entry is correct if default is "?"
        self._update_param_state()

        # (3) Status frame
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        self._build_status_row(status_frame, "Speed (rpm):", self.speed_var, self.speed_cyc, self._retrieve_speed)
        self._build_status_row(status_frame, "Temperature (C):", self.temp_var, self.temp_cyc, self._retrieve_temp)
        self._build_status_row(status_frame, "Load (%):", self.load_var, self.load_cyc, self._retrieve_load)

        # (4) cyc update
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
        self._refresh_ports()

    def _build_status_row(self, parent, label_text, var, cyc_var, retrieve_callback):
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

    # ========== Refresh Ports ==========

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(label=port, command=lambda p=port: self.selected_port.set(p))
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    # ========== Param state updating ==========

    def _update_param_state(self, *args):
        """
        Called whenever cmd_type_var changes.
        If it's "!", we enable the param entry. If it's "?", we disable it.
        """
        if self.cmd_type_var.get() == "!":
            self.param_entry.config(state="normal")
        else:
            self.param_entry.config(state="disabled")

    # ========== Toggling TurboSerialSettingsFrame ==========

    def _toggle_settings_frame(self):
        if self.settings_frame:
            # Destroy => shrink layout
            self.settings_frame.destroy()
            self.settings_frame = None
            self._finalize_geometry()
            return

        # Create => expand layout
        self.settings_frame = TurboSerialSettingsFrame(self.settings_container, self._on_turbo_settings_apply)
        self.settings_frame.pack(fill=tk.X, padx=5, pady=5)
        self._finalize_geometry()

    def _on_turbo_settings_apply(self, settings: dict):
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
            self.main_app.log_message("Turbo not connected. Settings apply after connect.")

    # ========== Connect/Disconnect ==========

    def _toggle_connection(self):
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
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

    # ========== Manual/Quick Commands ==========

    def _send_manual_command(self):
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
        if not self._check_connected():
            return

        quick_val = self.quick_cmd_var.get()
        if not quick_val:
            self.main_app.log_message("No quick command selected.")
            return

        # e.g. "start_pump - Start turbo"
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
        if resp.success:
            self.main_app.log_message(f"Turbo {cmd_name} => {resp.formatted_data}")
        else:
            self.main_app.log_message(f"Turbo {cmd_name} failed => {resp.error_message}")

    # ========== Retrieve (Status Rows) ==========

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

    # ========== Final geometry logic ==========

    def _finalize_geometry(self):
        """
        Re-check geometry to allow Toplevel to auto-size tightly,
        then re-center on the right side of the main window.
        This is called after toggling settings or initial build.
        """
        if isinstance(self.parent, tk.Toplevel):
            # Let geometry manager auto-fit
            # Setting geometry("") tells Tk to recalc minimal size
            self.parent.geometry("")
            self.parent.update_idletasks()

            # Now measure the new final size
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()

            # Re-center on right side
            main_x = self.main_app.root.winfo_x()
            main_y = self.main_app.root.winfo_y()
            main_w = self.main_app.root.winfo_width()
            main_h = self.main_app.root.winfo_height()

            offset_x = main_x + main_w + 30
            offset_y = main_y + (main_h - h)//2

            self.parent.geometry(f"{w}x{h}+{offset_x}+{offset_y}")
