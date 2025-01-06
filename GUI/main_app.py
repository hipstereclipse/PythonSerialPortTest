#!/usr/bin/env python3
"""
Main entry point for the Vacuum Gauge Communication Program.
Initializes the GUI and starts the application, preserving all functionality,
and adding a "Turbo" checkbutton that toggles a Toplevel window containing TurboFrame.

Removes "TC600" from the gauge dropdown so it does not appear among normal gauges,
but still allows the TurboFrame to internally use "TC600" if defined in GAUGE_PARAMETERS.
"""

import sys
import tkinter as tk
from tkinter import messagebox, ttk  # <-- IMPORTANT: We import ttk here
import logging
from pathlib import Path
import queue
import threading
from typing import Optional

import serial.tools.list_ports

# Imports your config items
from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS, setup_logging
# Imports main communicator and tester
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.gauge_tester import GaugeTester
# Imports data models for commands/responses
from serial_communication.models import GaugeCommand, GaugeResponse
# Imports optional protocol factory if needed
from serial_communication.communicator.protocol_factory import PPGProtocol

# Imports your frames
from GUI.serial_settings_frame import SerialSettingsFrame
from GUI.command_frame import CommandFrame
from GUI.debug_frame import DebugFrame
from GUI.output_frame import OutputFrame

# NEW: We import TurboFrame so we can open it in a Toplevel.
from GUI.turbo_frame import TurboFrame

def setup_exception_handling(root, logger):
    """
    Configures a global exception handler to log errors and show user-friendly messages.
    (Your original docstring style.)
    """
    def show_error(msg):
        """Shows an error dialog to the user."""
        messagebox.showerror("Error", f"An error occurred: {msg}\n\nCheck the log for details.")

    def handle_exception(exc_type, exc_value, exc_traceback):
        """Logs unhandled exceptions and shows a dialog."""
        if issubclass(exc_type, KeyboardInterrupt):
            root.quit()
            return

        logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        root.after(100, lambda: show_error(str(exc_value)))

    sys.excepthook = handle_exception

def create_app_directories():
    """
    Creates necessary application directories if they do not exist.
    """
    app_dir = Path.home() / ".gauge_communicator"
    log_dir = app_dir / "logs"
    config_dir = app_dir / "config"

    for directory in [app_dir, log_dir, config_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return app_dir, log_dir, config_dir

def main():
    """
    Main entry point of the application. Preserves original logic for starting the GUI.
    """
    # Creates directories
    app_dir, log_dir, config_dir = create_app_directories()

    # Initializes logging
    logger = setup_logging("GaugeCommunicator")
    logger.info("Starting Gauge Communication Program")

    # Creates the main Tk window
    root = tk.Tk()

    # Sets up exception handling
    setup_exception_handling(root, logger)

    # Attempts to initialize and run the main application
    try:
        app = GaugeApplication(root)
        logger.info("Application initialized successfully")

        # Centers the main window
        window_width = 800
        window_height = 650
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

        # Starts the main loop
        root.mainloop()

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        messagebox.showerror("Startup Error",
                             f"Failed to start application: {str(e)}\n\nCheck the log for details.")
        sys.exit(1)

def on_closing(root, app):
    """
    Handles application shutdown.
    """
    try:
        app.on_closing()
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)
    finally:
        root.destroy()

class GaugeApplication:
    """
    Main application class for the Vacuum Gauge Communication Interface.
    Preserves all code, removing "TC600" from gauge dropdown,
    and adding a "Turbo" checkbutton that toggles a Toplevel window with TurboFrame.
    """

    def __init__(self, root: tk.Tk):
        """
        Initializes the GaugeApplication with all original features (continuous reading, debug, commands),
        plus a "Turbo" checkbutton to open a Toplevel window with TurboFrame.
        """
        self.root = root
        self.root.title("Vacuum Gauge Communication Interface")
        self.root.geometry("800x650")

        # Variables for user-chosen port, gauge, output format
        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="PPG550")  # Example default
        self.output_format = tk.StringVar(value="ASCII")

        # Variables controlling continuous reading
        self.continuous_var = tk.BooleanVar(value=False)
        self.continuous_thread = None
        self.response_queue = queue.Queue()
        self.update_interval = tk.StringVar(value="1000")

        # Stores current serial settings
        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        # The main communicator object
        self.communicator: Optional[GaugeCommunicator] = None

        # For toggling debug logs
        self.show_debug = True

        # For toggling a Toplevel window containing the TurboFrame
        self.turbo_window: Optional[tk.Toplevel] = None
        self.turbo_var = tk.BooleanVar(value=False)

        # Creates a logger for the app
        self.logger = setup_logging("GaugeApplication")

        # Builds the GUI
        self._create_gui()

        # Trace changes in gauge or output format
        self.output_format.trace('w', self._on_output_format_change)
        self.selected_gauge.trace('w', self._on_gauge_change)

        # Refresh ports
        self.refresh_ports()

    def _create_gui(self):
        """
        Builds frames:
         1) Connection frame (no "TC600") + Turbo checkbutton
         2) SerialSettingsFrame
         3) CommandFrame
         4) DebugFrame
         5) OutputFrame
         6) Continuous reading frame
        """
        # === Connection Frame ===
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            conn_frame,
            text="Refresh",
            command=self.refresh_ports
        ).pack(side=tk.LEFT, padx=5)

        # Build a dictionary WITHOUT "TC600"
        gauge_dict = {
            "Capacitive": ["CDG025D", "CDG045D"],
            "Pirani/Capacitive": ["PCG550", "PSG550"],
            "MEMS Pirani": ["PPG550", "PPG570"],
            "Cold Cathode": ["MAG500", "MPG500"],
            "Hot Cathode": ["BPG40x", "BPG552"],
            "Combination": ["BCG450", "BCG552"]
        }

        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)

        gauge_list = []
        for cat, arr in gauge_dict.items():
            gauge_list.extend(arr)

        self.gauge_combo = ttk.Combobox(
            conn_frame,
            textvariable=self.selected_gauge,
            values=gauge_list,
            state="readonly",
            width=20
        )
        self.gauge_combo.pack(side=tk.LEFT, padx=5)
        if gauge_list:
            self.selected_gauge.set(gauge_list[0])

        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self.connect_disconnect
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # A "Turbo" checkbutton that toggles a Toplevel with TurboFrame
        self.turbo_check = ttk.Checkbutton(
            conn_frame,
            text="Turbo",
            variable=self.turbo_var,
            command=self._toggle_turbo_window
        )
        self.turbo_check.pack(side=tk.LEFT, padx=5)

        # === Serial Settings Frame ===
        # Creates and configures serial settings frame
        self.serial_frame = SerialSettingsFrame(
            self.root,
            self.apply_serial_settings,
            self.send_manual_command
        )
        # Sets parent reference for logging
        self.serial_frame.set_parent(self)
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # === Command Frame ===
        self.cmd_frame = CommandFrame(
            self.root,
            self.selected_gauge,
            self.send_command
        )
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # === Debug Frame ===
        self.debug_frame = DebugFrame(
            self.root,
            self.try_all_baud_rates,
            self.send_enq,
            self.show_port_settings,
            self.output_format
        )
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        # === Output Frame ===
        self.output_frame = OutputFrame(
            self.root,
            self.output_format
        )
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # === Continuous Reading Frame ===
        self.continuous_frame = ttk.LabelFrame(
            self.root,
            text="Continuous Reading"
        )
        self.continuous_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Checkbutton(
            self.continuous_frame,
            text="View Continuous Reading",
            variable=self.continuous_var,
            command=self.toggle_continuous_reading
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            self.continuous_frame,
            text="Update Interval (ms):"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Entry(
            self.continuous_frame,
            textvariable=self.update_interval,
            width=6
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.continuous_frame,
            text="Update",
            command=self._update_interval_value
        ).pack(side=tk.LEFT, padx=5)

        # Adds a data_tx_mode toggle if needed
        self.toggle_datatx_button = ttk.Button(
            self.continuous_frame,
            text="Toggle DataTxMode",
            command=self._toggle_data_tx_mode
        )
        self.toggle_datatx_button.pack(side=tk.LEFT, padx=5)

        # Periodically checks queue
        self.update_gui()

    def _toggle_turbo_window(self):
        """
        Called when the user toggles the "Turbo" checkbutton.
        If toggled ON => creates a Toplevel with TurboFrame.
        If toggled OFF => destroys it if present.
        Positions the new window near the center-right of main window.
        """
        if self.turbo_var.get():
            if not self.turbo_window:
                self._create_turbo_window()
        else:
            if self.turbo_window:
                self.turbo_window.destroy()
                self.turbo_window = None

    def _create_turbo_window(self):
        """
           Creates or shows the Turbo Controller window in a separate Toplevel.
           This function ensures the Toplevel is titled "Turbo Controller"
           and contains a TurboFrame that auto-resizes itself so nothing is cut off.
           If already open, you can decide whether to bring it to front or do nothing.
           """
        if self.turbo_window:
            self.turbo_window.lift()
            return

        self.turbo_window = tk.Toplevel(self.root)
        self.turbo_window.title("Turbo Controller")

        from GUI.turbo_frame import TurboFrame
        turbo_frame = TurboFrame(self.turbo_window, self)

        def on_turbo_close():
            self.turbo_window.destroy()
            self.turbo_window = None

        self.turbo_window.protocol("WM_DELETE_WINDOW", on_turbo_close)

    def update_gui(self):
        """
        Periodically checks the response_queue for new GaugeResponses,
        updates the OutputFrame, reschedules itself in 50ms.
        """
        while not self.response_queue.empty():
            try:
                resp = self.response_queue.get_nowait()
                if resp.success:
                    self.output_frame.append_log(f"\n{resp.formatted_data}")
                else:
                    self.output_frame.append_log(f"\nError: {resp.error_message}")
            except queue.Empty:
                pass

        self.root.after(50, self.update_gui)

    def _on_gauge_change(self, *args):
        gauge_type = self.selected_gauge.get()
        if gauge_type in GAUGE_PARAMETERS:
            params = GAUGE_PARAMETERS[gauge_type]
            self.serial_frame.baud_var.set(str(params["baudrate"]))

            rs485_supported = "rs_modes" in params and "RS485" in params["rs_modes"]
            rs485_address = params.get("address", 254) if rs485_supported else 254

            self.serial_frame.set_rs485_mode(rs485_supported, rs485_address)
            self.output_format.set(GAUGE_OUTPUT_FORMATS.get(gauge_type))

            if not self.communicator:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

            self.apply_serial_settings({
                'baudrate': params["baudrate"],
                'bytesize': params.get("bytesize", 8),
                'parity': params.get("parity", 'N'),
                'stopbits': params.get("stopbits", 1.0),
                'rs485_mode': rs485_supported,
                'rs485_address': rs485_address
            })

    def toggle_continuous_reading(self):
        if not self.communicator:
            self.continuous_var.set(False)
            return

        if self.continuous_var.get():
            self.start_continuous_reading()
        else:
            self.stop_continuous_reading()

    def start_continuous_reading(self):
        if self.continuous_thread and self.continuous_thread.is_alive():
            return
        self.communicator.set_continuous_reading(True)
        self.continuous_thread = threading.Thread(target=self.continuous_reading_thread, daemon=True)
        self.continuous_thread.start()

    def stop_continuous_reading(self):
        if self.communicator:
            self.communicator.stop_continuous_reading()
        if self.continuous_thread:
            self.continuous_thread.join(timeout=1.0)
            self.continuous_thread = None

    def continuous_reading_thread(self):
        try:
            interval_sec = int(self.update_interval.get()) / 1000.0
            self.communicator.read_continuous(lambda r: self.response_queue.put(r), interval_sec)
        except Exception as e:
            self.response_queue.put(GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=f"Thread error: {str(e)}"
            ))

    def _update_interval_value(self):
        try:
            val = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {val} ms")
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value.")

    def _toggle_data_tx_mode(self):
        if not self.communicator:
            self.log_message("No active connection. Unable to toggle DataTxMode.")
            return

        try:
            if not hasattr(self, 'datatx_mode'):
                self.datatx_mode = 0

            new_val = 1 if self.datatx_mode == 0 else 0
            cmd = GaugeCommand(
                name="data_tx_mode",
                command_type="!",
                parameters={"value": new_val}
            )
            resp = self.communicator.send_command(cmd)
            if resp.success:
                self.datatx_mode = new_val
                self.log_message(f"DataTxMode set to {new_val}")
            else:
                self.log_message(f"Failed to toggle DataTxMode: {resp.error_message}")
        except Exception as e:
            self.log_message(f"Error toggling DataTxMode: {str(e)}")

    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(label=port, command=lambda p=port: self.selected_port.set(p))
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    def connect_disconnect(self):
        if self.communicator is None:
            try:
                self.communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )
                if self.communicator.connect():
                    self.connect_button.config(text="Disconnect")
                    self.log_message("Connection established.")
                    self.cmd_frame.communicator = self.communicator
                    self.cmd_frame.set_enabled(True)
                    self.debug_frame.set_enabled(True)
                    self.update_continuous_visibility()
                else:
                    self.log_message("Failed to connect.")
                    self.communicator = None
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.communicator = None
        else:
            try:
                self.stop_continuous_reading()
                self.communicator.disconnect()
                self.communicator = None
                self.connect_button.config(text="Connect")
                self.log_message("Disconnected.")
                self.cmd_frame.set_enabled(False)
                self.debug_frame.set_enabled(False)
                self.continuous_var.set(False)
                self.continuous_frame.pack_forget()
            except Exception as e:
                self.log_message(f"Disconnection error: {e}")

    def _on_output_format_change(self, *args):
        new_fmt = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_fmt)
        self.log_message(f"Output format changed to: {new_fmt}")

    def apply_serial_settings(self, settings: dict):
        try:
            self.current_serial_settings.update(settings)
            if self.communicator and self.communicator.ser and self.communicator.ser.is_open:
                self.communicator.ser.baudrate = settings['baudrate']
                self.communicator.ser.bytesize = settings['bytesize']
                self.communicator.ser.parity = settings['parity']
                self.communicator.ser.stopbits = settings['stopbits']

                if settings.get('rs485_mode', False):
                    self.communicator.set_rs_mode("RS485")
                    if isinstance(self.communicator.protocol, PPGProtocol):
                        self.communicator.protocol.address = settings.get('rs485_address', 254)
                else:
                    self.communicator.set_rs_mode("RS232")

                self.log_message(f"Serial settings updated: {settings}")
                if settings.get('rs485_mode', False):
                    self.log_message(f"RS485 Address: {settings.get('rs485_address', 254)}")
        except Exception as e:
            self.log_message(f"Failed to update serial settings: {str(e)}")

    def send_command(self, command: str, response: Optional[GaugeResponse] = None):
        if response:
            if response.success:
                self.log_message(f">: {command}")
                self.log_message(f"<: {response.formatted_data}")
            else:
                self.log_message(f"Command failed: {response.error_message}")
        else:
            self.log_message(f"\nUnable to send command: {command}")

    def send_manual_command(self, command: str):
        if not hasattr(self, 'cmd_frame') or not self.cmd_frame:
            self.log_message("CommandFrame is not available.")
            return
        self.cmd_frame.process_command(command)

    def try_all_baud_rates(self):
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()

        try:
            temp_communicator = GaugeCommunicator(
                port=port,
                gauge_type=self.selected_gauge.get(),
                logger=self
            )
            temp_communicator.set_output_format(self.output_format.get())
            tester = GaugeTester(temp_communicator, self)
            success = tester.try_all_baud_rates(port)
            if success:
                succ_baud = temp_communicator.baudrate
                self.serial_frame.baud_var.set(str(succ_baud))
                self.apply_serial_settings({
                    'baudrate': succ_baud,
                    'bytesize': 8,
                    'parity': 'N',
                    'stopbits': 1.0
                })

                test_results = tester.run_all_tests()
                for c_name, rdict in test_results.get("commands_tested", {}).items():
                    if rdict.get("success"):
                        self.log_message(f"Test {c_name}: {rdict.get('response', 'OK')}")
                    else:
                        self.log_message(f"Test {c_name} failed: {rdict.get('error', 'Unknown error')}")
                temp_communicator.disconnect()
                return True
            else:
                if temp_communicator.ser and temp_communicator.ser.is_open:
                    temp_communicator.disconnect()
                return False
        except Exception as e:
            import traceback
            self.log_message(f"Baud rate testing error: {str(e)}")
            self.log_message(f"Traceback: {traceback.format_exc()}")
            return False

    def update_continuous_visibility(self):
        if hasattr(self, 'continuous_frame'):
            if self.communicator and self.communicator.continuous_output:
                self.continuous_frame.pack(fill="x", padx=5, pady=5)
            else:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

    def send_enq(self):
        if not self.communicator or not self.communicator.ser or not self.communicator.ser.is_open:
            self.log_message("Not connected")
            return
        try:
            self.communicator.set_output_format(self.output_format.get())
            tester = GaugeTester(self.communicator, self)
            if tester.send_enq():
                self.log_message("> ENQ test successful")
            else:
                self.log_message("> ENQ test failed")
        except Exception as e:
            self.log_message(f"ENQ test error: {str(e)}")

    def show_port_settings(self):
        if self.communicator and self.communicator.ser:
            ser = self.communicator.ser
            s = f"""
=== Port Settings ===
Port: {ser.port}
Baudrate: {ser.baudrate}
Bytesize: {ser.bytesize}
Parity: {ser.parity}
Stopbits: {ser.stopbits}
Timeout: {ser.timeout}
XonXoff: {ser.xonxoff}
RtsCts: {ser.rtscts}
DsrDtr: {ser.dsrdtr}
"""
            self.log_message(s)
        else:
            self.log_message("Not connected - showing saved settings:")
            s = f"""
=== Saved Settings ===
Baudrate: {self.current_serial_settings['baudrate']}
Bytesize: {self.current_serial_settings['bytesize']}
Parity: {self.current_serial_settings['parity']}
Stopbits: {self.current_serial_settings['stopbits']}
RS485 Mode: {self.current_serial_settings.get('rs485_mode', False)}
RS485 Address: {self.current_serial_settings.get('rs485_address', 254)}
"""
            self.log_message(s)

    def log_message(self, message: str):
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_frame.append_log(f"[{now}] {message}")

    def debug(self, message: str):
        if self.logger.isEnabledFor(logging.DEBUG):
            self.log_message(f"DEBUG: {message}")

    def set_show_debug(self, enabled: bool):
        if enabled:
            self.logger.setLevel(logging.DEBUG)
            self.log_message("Show Debug: ON")
        else:
            self.logger.setLevel(logging.INFO)
            self.log_message("Show Debug: OFF")

    def on_closing(self):
        if self.turbo_window:
            self.turbo_window.destroy()
            self.turbo_window = None

        self.stop_continuous_reading()
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()
