#!/usr/bin/env python3
"""
GUI/main_app.py

This module contains the GaugeApplication class that initializes the main GUI,
manages serial connections, continuous reading, and the Turbo (advanced) window.
It also defines the main() function to launch the application.
"""

import sys
import tkinter as tk
from tkinter import messagebox, ttk
import logging
from pathlib import Path
import queue
import threading
from typing import Optional

import serial.tools.list_ports

from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS, setup_logging
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.gauge_tester import GaugeTester
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.communicator.protocol_factory import get_protocol

from GUI.serial_settings_frame import SerialSettingsFrame
from GUI.command_frame import CommandFrame
from GUI.debug_frame import DebugFrame
from GUI.output_frame import OutputFrame
from GUI.turbo_frame import TurboFrame


def setup_exception_handling(root: tk.Tk, logger: logging.Logger) -> None:
    """
    Configures a global exception handler to log errors and show a user-friendly dialog.
    """

    def show_error(msg: str) -> None:
        messagebox.showerror("Error", f"An error occurred: {msg}\n\nCheck the log for details.")

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            root.quit()
            return
        logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        root.after(100, lambda: show_error(str(exc_value)))

    sys.excepthook = handle_exception


def create_app_directories() -> tuple[Path, Path, Path]:
    """
    Creates and returns the application directories (app_dir, log_dir, config_dir).
    """
    app_dir = Path.home() / ".gauge_communicator"
    log_dir = app_dir / "logs"
    config_dir = app_dir / "config"

    for directory in [app_dir, log_dir, config_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return app_dir, log_dir, config_dir


class GaugeApplication:
    """
    The main application class for the Vacuum Gauge Communication Interface.
    Manages connection settings, continuous reading, debug logging, and Turbo window.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Vacuum Gauge Communication Interface")
        self.root.geometry("800x650")

        # Variables for port, gauge, and output format
        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="PPG550")
        self.output_format = tk.StringVar(value="ASCII")

        self.continuous_var = tk.BooleanVar(value=False)
        self.continuous_thread: Optional[threading.Thread] = None
        self.response_queue = queue.Queue()
        self.update_interval = tk.StringVar(value="1000")

        self.current_serial_settings: Dict[str, Any] = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        self.communicator: Optional[GaugeCommunicator] = None
        self.show_debug = True
        self.turbo_window: Optional[tk.Toplevel] = None
        self.turbo_var = tk.BooleanVar(value=False)
        self.logger = setup_logging("GaugeApplication")

        self._create_gui()
        self.output_format.trace("w", self._on_output_format_change)
        self.selected_gauge.trace("w", self._on_gauge_change)

        self.refresh_ports()

    def _create_gui(self) -> None:
        """
        Builds and packs all GUI frames: Connection, Serial Settings, Commands, Debug, Output,
        and Continuous Reading. Also creates a Turbo checkbutton.
        """
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)

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
        for arr in gauge_dict.values():
            gauge_list.extend(arr)
        self.gauge_combo = ttk.Combobox(conn_frame, textvariable=self.selected_gauge,
                                        values=gauge_list, state="readonly", width=20)
        self.gauge_combo.pack(side=tk.LEFT, padx=5)
        if gauge_list:
            self.selected_gauge.set(gauge_list[0])

        self.connect_button = ttk.Button(conn_frame, text="Connect", command=self.connect_disconnect)
        self.connect_button.pack(side=tk.LEFT, padx=5)

        self.turbo_check = ttk.Checkbutton(conn_frame, text="Turbo", variable=self.turbo_var,
                                           command=self._toggle_turbo_window)
        self.turbo_check.pack(side=tk.LEFT, padx=5)

        self.serial_frame = SerialSettingsFrame(self.root, self.apply_serial_settings, self.send_manual_command)
        self.serial_frame.set_parent(self)
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        self.cmd_frame = CommandFrame(self.root, self.selected_gauge, self.send_command)
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        self.debug_frame = DebugFrame(self.root, self.try_all_baud_rates, self.send_enq,
                                      self.show_port_settings, self.output_format)
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        self.output_frame = OutputFrame(self.root, self.output_format)
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.continuous_frame = ttk.LabelFrame(self.root, text="Continuous Reading")
        self.continuous_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Checkbutton(self.continuous_frame, text="View Continuous Reading", variable=self.continuous_var,
                        command=self.toggle_continuous_reading).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.continuous_frame, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(self.continuous_frame, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.continuous_frame, text="Update", command=self._update_interval_value).pack(side=tk.LEFT, padx=5)
        self.toggle_datatx_button = ttk.Button(self.continuous_frame, text="Toggle DataTxMode",
                                               command=self._toggle_data_tx_mode)
        self.toggle_datatx_button.pack(side=tk.LEFT, padx=5)

        self.root.after(50, self.update_gui)

    def _toggle_turbo_window(self) -> None:
        """
        Toggles the Turbo window. If checked, creates a Toplevel with TurboFrame.
        """
        if self.turbo_var.get():
            if not self.turbo_window:
                self._create_turbo_window()
        else:
            if self.turbo_window:
                self.turbo_window.destroy()
                self.turbo_window = None

    def _create_turbo_window(self) -> None:
        """
        Creates a new Toplevel window containing the TurboFrame.
        """
        if self.turbo_window:
            self.turbo_window.lift()
            return

        self.turbo_window = tk.Toplevel(self.root)
        self.turbo_window.title("Turbo Controller")
        turbo_frame = TurboFrame(self.turbo_window, self)
        self.turbo_window.protocol("WM_DELETE_WINDOW", lambda: self._on_turbo_close())

    def _on_turbo_close(self) -> None:
        """
        Called when the Turbo window is closed.
        """
        if self.turbo_window:
            self.turbo_window.destroy()
            self.turbo_window = None

    def update_gui(self) -> None:
        """
        Periodically checks the response queue and updates the output frame.
        """
        while not self.response_queue.empty():
            try:
                resp = self.response_queue.get_nowait()
                if resp.success:
                    self.output_frame.append_log(f"\n{resp.formatted_data}")
                else:
                    self.output_frame.append_log(f"\nError: {resp.error_message}")
            except Exception:
                break
        self.root.after(50, self.update_gui)

    def _on_gauge_change(self, *args) -> None:
        """
        Called when the gauge selection changes.
        Updates serial settings and output format based on gauge parameters.
        """
        gauge_type = self.selected_gauge.get()
        if gauge_type in GAUGE_PARAMETERS:
            params = GAUGE_PARAMETERS[gauge_type]
            self.serial_frame.baud_var.set(str(params["baudrate"]))
            rs485_supported = "rs_modes" in params and "RS485" in params["rs_modes"]
            rs485_address = params.get("address", 254) if rs485_supported else 254
            self.serial_frame.set_rs485_mode(rs485_supported, rs485_address)
            self.output_format.set(GAUGE_OUTPUT_FORMATS.get(gauge_type, "ASCII"))
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

    def toggle_continuous_reading(self) -> None:
        """
        Starts or stops continuous reading based on the toggle state.
        """
        if not self.communicator:
            self.continuous_var.set(False)
            return

        if self.continuous_var.get():
            self.start_continuous_reading()
        else:
            self.stop_continuous_reading()

    def start_continuous_reading(self) -> None:
        """
        Starts a background thread for continuous reading.
        """
        if self.continuous_thread and self.continuous_thread.is_alive():
            return
        self.communicator.set_continuous_reading(True)
        self.continuous_thread = threading.Thread(target=self.continuous_reading_thread, daemon=True)
        self.continuous_thread.start()

    def stop_continuous_reading(self) -> None:
        """
        Stops the continuous reading thread and resets its reference.
        """
        if self.communicator:
            self.communicator.stop_continuous_reading()
        if self.continuous_thread:
            self.continuous_thread.join(timeout=1.0)
            self.continuous_thread = None

    def continuous_reading_thread(self) -> None:
        """
        Background thread function to perform continuous reading.
        """
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

    def _update_interval_value(self) -> None:
        """
        Updates the continuous reading interval.
        """
        try:
            val = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {val} ms")
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value.")

    def _toggle_data_tx_mode(self) -> None:
        """
        Toggles the data transmission mode by sending a GaugeCommand.
        """
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

    def refresh_ports(self) -> None:
        """
        Refreshes the list of available serial ports and updates the port menu.
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

    def connect_disconnect(self) -> None:
        """
        Connects to the gauge if not connected; otherwise disconnects.
        """
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

    def _on_output_format_change(self, *args) -> None:
        """
        Updates the communicator output format when the user changes the output format.
        """
        new_fmt = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_fmt)
        self.log_message(f"Output format changed to: {new_fmt}")

    def apply_serial_settings(self, settings: dict) -> None:
        """
        Applies updated serial settings to the communicator if connected.
        """
        try:
            self.current_serial_settings.update(settings)
            if self.communicator and self.communicator.ser and self.communicator.ser.is_open:
                self.communicator.ser.baudrate = settings["baudrate"]
                self.communicator.ser.bytesize = settings["bytesize"]
                self.communicator.ser.parity = settings["parity"]
                self.communicator.ser.stopbits = settings["stopbits"]

                if settings.get("rs485_mode", False):
                    self.communicator.set_rs_mode("RS485")
                    from serial_communication.communicator.protocol_factory import get_protocol
                    if hasattr(self.communicator.protocol, "address"):
                        self.communicator.protocol.address = settings.get("rs485_address", 254)
                else:
                    self.communicator.set_rs_mode("RS232")

                self.log_message(f"Serial settings updated: {settings}")
                if settings.get("rs485_mode", False):
                    self.log_message(f"RS485 Address: {settings.get('rs485_address', 254)}")
        except Exception as e:
            self.log_message(f"Failed to update serial settings: {str(e)}")

    def send_command(self, command: str, response: Optional[GaugeResponse] = None) -> None:
        """
        Logs the command and response.
        """
        if response:
            if response.success:
                self.log_message(f">: {command}")
                self.log_message(f"<: {response.formatted_data}")
            else:
                self.log_message(f"Command failed: {response.error_message}")
        else:
            self.log_message(f"\nUnable to send command: {command}")

    def send_manual_command(self, command: str) -> None:
        """
        Delegates manual command processing to the CommandFrame.
        """
        if not hasattr(self, "cmd_frame") or not self.cmd_frame:
            self.log_message("CommandFrame is not available.")
            return
        self.cmd_frame.send_manual_command()

    def try_all_baud_rates(self) -> bool:
        """
        Uses GaugeTester to try a list of baud rates.
        """
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()

        try:
            temp_comm = GaugeCommunicator(
                port=port,
                gauge_type=self.selected_gauge.get(),
                logger=self
            )
            temp_comm.set_output_format(self.output_format.get())
            tester = GaugeTester(temp_comm, self)
            success = tester.try_all_baud_rates(port)
            if success:
                succ_baud = temp_comm.baudrate
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
                temp_comm.disconnect()
                return True
            else:
                if temp_comm.ser and temp_comm.ser.is_open:
                    temp_comm.disconnect()
                return False
        except Exception as e:
            import traceback
            self.log_message(f"Baud rate testing error: {str(e)}")
            self.log_message(f"Traceback: {traceback.format_exc()}")
            return False

    def update_continuous_visibility(self) -> None:
        """
        Shows or hides the continuous reading frame based on connection and gauge support.
        """
        if hasattr(self, "continuous_frame"):
            if self.communicator and self.communicator.continuous_output:
                self.continuous_frame.pack(fill="x", padx=5, pady=5)
            else:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

    def send_enq(self) -> None:
        """
        Sends an ENQ command to the gauge to test connectivity.
        """
        if not (self.communicator and self.communicator.ser and self.communicator.ser.is_open):
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

    def show_port_settings(self) -> None:
        """
        Logs the current serial port settings.
        """
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

    def log_message(self, message: str, level: str = "INFO") -> None:
        """
        Logs a message using the app logger and appends it to the output frame.
        """
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if level.upper() == "ERROR":
            self.logger.error(message)
        elif level.upper() == "DEBUG":
            self.logger.debug(message)
        else:
            self.logger.info(message)
        self.output_frame.append_log(f"[{now}] [{level}] {message}")

    def error(self, msg: str) -> None:
        """
        Called when errors occur. Logs and shows the error message.
        """
        self.logger.error(msg)
        self.log_message(msg, level="ERROR")

    def debug(self, message: str) -> None:
        """
        Logs a debug message if debug level is enabled.
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.log_message(f"DEBUG: {message}")

    def set_show_debug(self, enabled: bool) -> None:
        """
        Adjusts the logger level based on the debug checkbox.
        """
        if enabled:
            self.logger.setLevel(logging.DEBUG)
            self.log_message("Show Debug: ON")
        else:
            self.logger.setLevel(logging.INFO)
            self.log_message("Show Debug: OFF")

    def on_closing(self) -> None:
        """
        Performs cleanup on application exit.
        """
        if self.turbo_window:
            self.turbo_window.destroy()
            self.turbo_window = None
        self.stop_continuous_reading()
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()


def on_closing(root: tk.Tk, app: GaugeApplication) -> None:
    """
    Handles shutdown by calling the app's on_closing method and destroying the root.
    """
    try:
        app.on_closing()
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)
    finally:
        root.destroy()
