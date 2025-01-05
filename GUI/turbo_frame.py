"""
turbo_frame.py
Implements a compact TurboFrame for controlling a Turbo Pump (e.g., "TC600").
Uses thorough, active-voice comments on almost every line, as requested.

Key Layout/Functionality:
 1) Turbo Connection Frame (two rows):
    - Row 1: "Port:" label + OptionMenu + "Refresh" button, "Turbo:" label + combo
    - Row 2: [Connection Status], [Connect Button], [Settings Button]
      -> Below row2, toggles a TurboSerialSettingsFrame (specialized for COM settings).
 2) Turbo Commands Frame, which includes:
    - Manual Command section
    - Quick Commands section with parameter disabled unless command_type == "!"
 3) Status Frame for speed/temp/load with cyc toggles + retrieve
 4) Cyclical Status Update Frame (two-row approach)
 5) _finalize_geometry() calls geometry("") on the Toplevel each time the settings frame is shown or hidden,
    letting Tk shrink or expand to fit tightly, and repositions on the right side of the main window.

This code does not remove any existing functionality, and preserves manual commands,
quick commands, cyc toggles, retrieve, and logging to the main_app's OutputFrame.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import threading
import queue
import serial.tools.list_ports

# Imports your existing communicator
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.models import GaugeCommand, GaugeResponse

# Adjust this import if your specialized TurboSerialSettingsFrame is stored elsewhere
from .turbo_serial_settings_frame import TurboSerialSettingsFrame


class TurboFrame(ttk.Frame):
    """
    TurboFrame: Main GUI frame for controlling a Turbo Pump in a compact layout.

    Highlights:
     - Second row in the connection frame has [Status Label, Connect Button, Settings Button].
     - Toggles a TurboSerialSettingsFrame below row2, forcing a geometry recalc (shrinking or growing).
     - Disables parameter entry for quick commands unless we are in "Set" mode ("!").
     - Preserves cyc toggles, manual commands, retrieve buttons, and logs to main_app.
    """

    def __init__(self, parent, main_app):
        """
        Initializes the TurboFrame with references to its parent and the main_app.
        parent   : The Toplevel or containing widget
        main_app : The main application, so we can call main_app.log_message(...)
        """
        # Calls the superclass initializer
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        # Stores references to parent and main application
        self.parent = parent
        self.main_app = main_app

        # Tracks whether we are connected to the turbo
        self.connected = False
        self.turbo_communicator: Optional[GaugeCommunicator] = None

        # Creates StringVars for port, turbo, and status text
        self.selected_port = tk.StringVar(value="")
        self.selected_turbo = tk.StringVar(value="TC600")
        self.status_text = tk.StringVar(value="Disconnected")

        # A reference to the specialized settings frame, which we can create/destroy
        self.settings_frame: Optional[TurboSerialSettingsFrame] = None

        # Variables for cyc reading
        self.cycle_var = tk.BooleanVar(value=False)
        self.update_interval = tk.StringVar(value="1000")
        self.stop_thread = False
        self.status_thread: Optional[threading.Thread] = None

        # Variables for status data (speed, temperature, load)
        self.speed_var = tk.StringVar(value="---")
        self.speed_cyc = tk.BooleanVar(value=True)
        self.temp_var = tk.StringVar(value="---")
        self.temp_cyc = tk.BooleanVar(value=True)
        self.load_var = tk.StringVar(value="---")
        self.load_cyc = tk.BooleanVar(value=True)

        # Variables for manual/quick commands
        self.manual_command_var = tk.StringVar()
        self.quick_cmd_var = tk.StringVar()
        self.cmd_type_var = tk.StringVar(value="?")  # "?" => Query, "!" => Set
        self.param_var = tk.StringVar()
        # We must specify a master for StringVar if we want to avoid potential errors:
        self.desc_var = tk.StringVar(self, value="")

        # Builds all the GUI widgets
        self._create_widgets()

        # After building, forces geometry to shrink or expand to minimal
        self._finalize_geometry()

    def _create_widgets(self):
        """
        Builds four main sections:
          1) Turbo Connection Frame (two rows)
          2) Turbo Commands (manual + quick)
          3) Status Frame
          4) Cyclical Status Update
        """
        # Creates a labeled frame for the connection
        conn_frame = ttk.LabelFrame(self, text="Turbo Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Row 1 => "Port:", OptionMenu + Refresh, "Turbo:", turbo combobox
        row1 = ttk.Frame(conn_frame)
        row1.pack(fill=tk.X, padx=5, pady=2)

        # Adds label "Port:"
        ttk.Label(row1, text="Port:").pack(side=tk.LEFT, padx=2)

        # Adds an OptionMenu for ports
        self.port_menu = ttk.OptionMenu(row1, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=2)

        # Adds a Refresh button to re-scan COM ports
        refresh_btn = ttk.Button(row1, text="Refresh", command=self._refresh_ports)
        refresh_btn.pack(side=tk.LEFT, padx=5)

        # Adds a label "Turbo:"
        ttk.Label(row1, text="Turbo:").pack(side=tk.LEFT, padx=5)

        # Creates a combobox for selecting which turbo type (e.g., "TC600")
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

        # Row 2 => [Status, Connect, Settings]
        row2 = ttk.Frame(conn_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)

        # Adds a label to show the current status (Disconnected/Connected)
        ttk.Label(row2, textvariable=self.status_text).pack(side=tk.LEFT, padx=5)

        # Adds a connect/disconnect button
        self.connect_btn = ttk.Button(row2, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # Adds a button to toggle the specialized settings frame
        settings_btn = ttk.Button(row2, text="Settings", command=self._toggle_settings_frame)
        settings_btn.pack(side=tk.LEFT, padx=5)

        # Creates a container below row2 where we can pack the specialized settings frame if toggled
        self.settings_container = ttk.Frame(conn_frame)
        self.settings_container.pack(fill=tk.X, padx=5, pady=5)

        # Creates the "Turbo Commands" frame
        cmd_frame = ttk.LabelFrame(self, text="Turbo Commands")
        cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Inside "Turbo Commands", we create a "Manual Command" sub-frame
        manual_frame = ttk.LabelFrame(cmd_frame, text="Manual Command")
        manual_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds a label "Command:" and an Entry for the manual command
        ttk.Label(manual_frame, text="Command:").pack(side=tk.LEFT, padx=5)
        manual_entry = ttk.Entry(manual_frame, textvariable=self.manual_command_var, width=40)
        manual_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Adds a "Send" button that calls _send_manual_command
        manual_send_btn = ttk.Button(manual_frame, text="Send", command=self._send_manual_command)
        manual_send_btn.pack(side=tk.LEFT, padx=5)

        # Creates a "Quick Commands" sub-frame
        quick_frame = ttk.LabelFrame(cmd_frame, text="Quick Commands")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds label "Command:" and a combobox for picking a known quick command
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

        # Creates a small frame to hold radio buttons for "Query (?)" or "Set (!)"
        radio_frame = ttk.Frame(quick_frame)
        radio_frame.pack(side=tk.LEFT, padx=2)

        # Adds two radio buttons that modify cmd_type_var
        self.query_radio = ttk.Radiobutton(radio_frame, text="Query (?)", variable=self.cmd_type_var, value="?")
        self.set_radio   = ttk.Radiobutton(radio_frame, text="Set (!)",   variable=self.cmd_type_var, value="!")
        self.query_radio.pack(side=tk.LEFT, padx=2)
        self.set_radio.pack(side=tk.LEFT, padx=2)

        # Ties a callback to cmd_type_var changes so we can enable/disable param entry
        self.cmd_type_var.trace("w", self._update_param_state)

        # Next row in the commands frame for parameter
        param_frame = ttk.Frame(cmd_frame)
        param_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds label "Parameter:" and an entry for param_var
        ttk.Label(param_frame, text="Parameter:").pack(side=tk.LEFT, padx=5)
        self.param_entry = ttk.Entry(param_frame, textvariable=self.param_var, width=20)
        self.param_entry.pack(side=tk.LEFT, padx=5)

        # Adds a "Send" button that calls _send_quick_command
        quick_send_btn = ttk.Button(param_frame, text="Send", command=self._send_quick_command)
        quick_send_btn.pack(side=tk.LEFT, padx=5)

        # Creates a label to show descriptions for the quick command
        self.desc_label = ttk.Label(cmd_frame, textvariable=self.desc_var, wraplength=400)
        self.desc_label.pack(fill=tk.X, padx=5, pady=5)

        # Calls the param state update once initially
        self._update_param_state()

        # Creates the "Turbo Status" frame
        status_frame = ttk.LabelFrame(self, text="Turbo Status")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds speed, temp, load rows, each with cyc toggles + retrieve
        self._build_status_row(status_frame,"Speed (rpm):",self.speed_var,self.speed_cyc,self._retrieve_speed)
        self._build_status_row(status_frame,"Temperature (C):",self.temp_var,self.temp_cyc,self._retrieve_temp)
        self._build_status_row(status_frame,"Load (%):",self.load_var,self.load_cyc,self._retrieve_load)

        # Creates the cyc reading frame
        cyc_frame = ttk.LabelFrame(self, text="Cyclical Status Update")
        cyc_frame.pack(fill=tk.X, padx=5, pady=5)

        # Row 1 => "Enable Cyc Updates" checkbox
        cyc_row1 = ttk.Frame(cyc_frame)
        cyc_row1.pack(fill=tk.X, padx=5, pady=2)
        cyc_chk = ttk.Checkbutton(
            cyc_row1,
            text="Enable Cyclical Updates",
            variable=self.cycle_var,
            command=self._toggle_cycle
        )
        cyc_chk.pack(side=tk.LEFT, padx=5)

        # Row 2 => "Update Interval" + entry + "Apply" button
        cyc_row2 = ttk.Frame(cyc_frame)
        cyc_row2.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(cyc_row2, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(cyc_row2, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)
        apply_btn = ttk.Button(cyc_row2, text="Apply", command=self._apply_interval)
        apply_btn.pack(side=tk.LEFT, padx=5)

        # Finally pack the main frame
        self.pack(fill=tk.BOTH, expand=True)

        # Refresh the port menu initially
        self._refresh_ports()

    def _build_status_row(self, parent, label_text, var, cyc_var, retrieve_callback):
        """
        Builds a single row in the "Turbo Status" frame, with a cyc toggle, a label,
        a variable display, and a 'Retrieve' button to query that parameter.
        """
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=5, pady=3)

        # Adds a checkbutton for cyc toggles
        cyc_cb = ttk.Checkbutton(row, variable=cyc_var)
        cyc_cb.pack(side=tk.LEFT, padx=5)

        # Adds a label for the row name
        lbl = ttk.Label(row, text=label_text)
        lbl.pack(side=tk.LEFT, padx=5)

        # Adds a label that shows the current value from var
        val_lbl = ttk.Label(row, textvariable=var)
        val_lbl.pack(side=tk.LEFT, padx=5)

        # Adds a Retrieve button to call retrieve_callback
        rtv_btn = ttk.Button(row, text="Retrieve", command=retrieve_callback)
        rtv_btn.pack(side=tk.LEFT, padx=5)

    def _refresh_ports(self):
        """
        Scans for available COM ports and populates the OptionMenu so the user can pick a port.
        """
        # Lists all detected COM ports
        ports = [p.device for p in serial.tools.list_ports.comports()]

        # Clears the old menu items
        menu = self.port_menu["menu"]
        menu.delete(0, "end")

        # Adds each detected port to the menu
        for port in ports:
            menu.add_command(label=port, command=lambda p=port: self.selected_port.set(p))

        # If there are ports, set the first one; otherwise set empty
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    def _update_param_state(self, *args):
        """
        Enables the param entry if cmd_type_var == "!", otherwise disables it (for "?" = Query).
        This ensures the Parameter can only be typed if the user is setting a command.
        """
        if self.cmd_type_var.get() == "!":
            self.param_entry.config(state="normal")
        else:
            self.param_entry.config(state="disabled")

    def _toggle_settings_frame(self):
        """
        Called when the user clicks "Settings" in row2 of the connection frame.
        If the settings frame is showing, we remove it and recalc geometry so the
        connection frame shrinks. If it is hidden, we create it and expand.
        """
        # Checks if the settings frame is currently present
        if self.settings_frame:
            # Removes it from layout
            self.settings_frame.pack_forget()
            # Destroys the frame
            self.settings_frame.destroy()
            self.settings_frame = None
            # Forces geometry to recalc for a smaller layout
            self._finalize_geometry()
            return

        # If no settings frame, we create and pack it inside the container
        self.settings_frame = TurboSerialSettingsFrame(self.settings_container, self._on_turbo_settings_apply)
        self.settings_frame.pack(fill=tk.X, padx=5, pady=5)
        # Forces geometry to recalc for a bigger layout
        self._finalize_geometry()

    def _on_turbo_settings_apply(self, settings: dict):
        """
        Called when user clicks 'Apply' inside the TurboSerialSettingsFrame.
        If we are connected, we apply these settings to the communicator's serial port.
        Otherwise we simply log that they will apply upon next connect.
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

    def _toggle_connection(self):
        """
        Toggles between connected and disconnected states when the user clicks the connect button.
        """
        if not self.connected:
            self._connect_turbo()
        else:
            self._disconnect_turbo()

    def _connect_turbo(self):
        """
        Creates a GaugeCommunicator with the chosen port and turbo type, then attempts to connect.
        If successful, updates status to 'Connected', changes the button text, and logs.
        If it fails, logs the error and keeps communicator = None.
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
        Disconnects from the turbo if connected, updates status to 'Disconnected',
        resets the connect button text, stops cyc reading if active, logs the event.
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
        Checks if we have an active communicator. Logs if not.
        Returns True if connected, False if disconnected.
        """
        if not self.connected or not self.turbo_communicator:
            self.main_app.log_message("Turbo is not connected.")
            return False
        return True

    def _send_manual_command(self):
        """
        Sends a raw manual command from manual_command_var if we are connected.
        Logs the result or any errors.
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
        Sends the selected quick command from quick_cmd_combo. The user picks query or set
        via cmd_type_var, and optionally enters a param if in set mode.
        Logs the result or errors.
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

    def _toggle_cycle(self):
        """
        Called when the user toggles "Enable Cyclical Updates."
        If on and we're connected, we start a reading thread. If off, we stop it.
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
        Called when user clicks "Apply" next to the cyc update interval.
        If cyc is on, we restart the thread with the new interval.
        """
        if self.cycle_var.get():
            self._stop_cycle_thread()
            self._start_cycle_thread()

    def _start_cycle_thread(self):
        """
        Starts a background thread that repeatedly reads speed/temp/load
        if their cyc toggles are on, waiting update_interval ms between cycles.
        """
        self.stop_thread = False
        self.status_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self.status_thread.start()

    def _stop_cycle_thread(self):
        """
        Signals the cyc read thread to stop by setting stop_thread = True
        and optionally joining the thread.
        """
        self.stop_thread = True
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=1.0)
        self.status_thread = None

    def _cycle_loop(self):
        """
        Worker function for cyc reading, repeatedly calling retrieve methods
        if their cyc toggles are on, sleeping for update_interval ms between cycles.
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

    def _finalize_geometry(self):
        """
        Forces the Toplevel to auto-resize to minimal by calling geometry(""),
        then re-centers the window on the right side of the main window.
        Called whenever we toggle the settings frame or finish building.
        """
        # Only do this if our parent is a Toplevel
        if isinstance(self.parent, tk.Toplevel):
            # Asks Tk to recalc geometry to minimal
            self.parent.geometry("")
            # Updates the layout so we get the final size
            self.parent.update_idletasks()

            # Measures the final width/height
            w = self.parent.winfo_width()
            h = self.parent.winfo_height()

            # Retrieves main window geometry to center us on the right
            main_x = self.main_app.root.winfo_x()
            main_y = self.main_app.root.winfo_y()
            main_w = self.main_app.root.winfo_width()
            main_h = self.main_app.root.winfo_height()

            # We place ourselves at (main_x + main_w + 30, vertical center)
            offset_x = main_x + main_w + 30
            offset_y = main_y + (main_h - h)//2

            # Applies new geometry
            self.parent.geometry(f"{w}x{h}+{offset_x}+{offset_y}")
