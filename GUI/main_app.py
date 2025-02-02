#!/usr/bin/env python3
"""
GUI/main_app.py

Main entry point for the Vacuum Gauge Communication Program.
This module initializes the GUI, manages device connections, and now supports a hardware simulator mode.
When Simulator Mode is enabled, real device connections are replaced with a simulated communicator.

Frames created:
  - Connection Frame: Port selection, gauge dropdown, Connect/Disconnect button, and a Turbo toggle.
  - SerialSettingsFrame: For configuring serial parameters.
  - CommandFrame: For sending manual/quick commands.
  - DebugFrame: Contains debug controls and now a Simulator Mode toggle and Simulation Options button.
  - OutputFrame: Displays log messages and command responses.
  - Continuous Reading Frame: For periodic data updates.

Simulator integration:
  - When Simulator Mode is enabled (via a checkbox in the DebugFrame), the application creates a simulated communicator.
  - The simulator is maintained until the user clicks the Disconnect button.
  - Simulation Options can be configured at runtime via a dedicated dialog.
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

# Import configuration, communicator, tester, and data models
from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS, setup_logging
from serial_communication.models import GaugeCommand, GaugeResponse

# Real communicator (for gauges)
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.gauge_tester import GaugeTester

# Import protocol factory if needed (for real connection)
from serial_communication.communicator.protocol_factory import PPGProtocol

# Import GUI frames
from GUI.serial_settings_frame import SerialSettingsFrame
from GUI.command_frame import CommandFrame
from GUI.debug_frame import DebugFrame
from GUI.output_frame import OutputFrame
from GUI.turbo_frame import TurboFrame


class GaugeApplication:
    """
    Main application class for the Vacuum Gauge Communication Interface.
    Manages the GUI layout, serial communications, and simulator mode.
    """

    def __init__(self, root: tk.Tk):
        """
        Initializes the GaugeApplication.

        Args:
            root: The main Tkinter window.
        """
        self.root = root
        self.root.title("Vacuum Gauge Communication Interface")
        self.root.geometry("800x650")

        # Variables for port, gauge, and output format
        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="PPG550")
        self.output_format = tk.StringVar(value="ASCII")

        # Variables for continuous reading
        self.continuous_var = tk.BooleanVar(value=False)
        self.update_interval = tk.StringVar(value="1000")
        self.response_queue = queue.Queue()

        # Serial settings (default values)
        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        # Communicator object (real or simulated)
        self.communicator: Optional[object] = None

        # Flags for turbo and simulator modes
        self.turbo_window: Optional[tk.Toplevel] = None
        self.turbo_var = tk.BooleanVar(value=False)
        self.simulator_enabled = False  # This flag is controlled by the Simulator Mode toggle

        # Logger for the application
        self.logger = setup_logging("GaugeApplication")

        # Build all GUI frames
        self._create_gui()

        # Trace changes in gauge and output format variables
        self.output_format.trace('w', self._on_output_format_change)
        self.selected_gauge.trace('w', self._on_gauge_change)

        # Populate port list initially
        self.refresh_ports()

    def _create_gui(self) -> None:
        """
        Constructs and packs all the GUI frames.
        """
        # --- Connection Frame ---
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)

        # Build gauge dropdown (excluding turbo-only devices)
        gauge_dict = {
            "Capacitive": ["CDG025D", "CDG045D"],
            "Pirani/Capacitive": ["PCG550", "PSG550"],
            "MEMS Pirani": ["PPG550", "PPG570"],
            "Cold Cathode": ["MAG500", "MPG500"],
            "Hot Cathode": ["BPG40x", "BPG552"],
            "Combination": ["BCG450", "BCG552"]
        }
        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)
        gauge_list = [g for sub in gauge_dict.values() for g in sub]
        self.gauge_combo = ttk.Combobox(conn_frame, textvariable=self.selected_gauge,
                                        values=gauge_list, state="readonly", width=20)
        self.gauge_combo.pack(side=tk.LEFT, padx=5)
        if gauge_list:
            self.selected_gauge.set(gauge_list[0])

        # Connect/Disconnect button uses text to toggle state.
        self.connect_button = ttk.Button(conn_frame, text="Connect", command=self.connect_disconnect)
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # Turbo toggle (remains unchanged)
        self.turbo_check = ttk.Checkbutton(conn_frame, text="Turbo", variable=self.turbo_var,
                                           command=self._toggle_turbo_window)
        self.turbo_check.pack(side=tk.LEFT, padx=5)

        # --- Serial Settings Frame ---
        self.serial_frame = SerialSettingsFrame(self.root, self.apply_serial_settings, self.send_manual_command)
        self.serial_frame.set_parent(self)
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # --- Command Frame ---
        self.cmd_frame = CommandFrame(self.root, self.selected_gauge, self.send_command)
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # --- Debug Frame ---
        self.debug_frame = DebugFrame(
            self.root,
            baud_callback=self.try_all_baud_rates,
            enq_callback=self.send_enq,
            settings_callback=self.show_port_settings,
            output_format=self.output_format,
            simulator_callback=self.set_simulator_mode,
            simulation_options_callback=self.open_simulation_options
        )
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        # --- Output Frame ---
        self.output_frame = OutputFrame(self.root, self.output_format)
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Continuous Reading Frame ---
        self.continuous_frame = ttk.LabelFrame(self.root, text="Continuous Reading")
        self.continuous_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Checkbutton(self.continuous_frame, text="View Continuous Reading",
                        variable=self.continuous_var, command=self.toggle_continuous_reading).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.continuous_frame, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(self.continuous_frame, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.continuous_frame, text="Update", command=self._update_interval_value).pack(side=tk.LEFT, padx=5)
        self.toggle_datatx_button = ttk.Button(self.continuous_frame, text="Toggle DataTxMode",
                                               command=self._toggle_data_tx_mode)
        self.toggle_datatx_button.pack(side=tk.LEFT, padx=5)

        # Start the periodic GUI update loop.
        self.update_gui()

    def _toggle_turbo_window(self) -> None:
        """
        Toggles the Turbo window on or off.
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
        from GUI.turbo_frame import TurboFrame
        TurboFrame(self.turbo_window, self)

        def on_turbo_close():
            self.turbo_window.destroy()
            self.turbo_window = None

        self.turbo_window.protocol("WM_DELETE_WINDOW", on_turbo_close)

    def update_gui(self) -> None:
        """
        Periodically checks the response queue and updates the OutputFrame.
        """
        while not self.response_queue.empty():
            try:
                resp = self.response_queue.get_nowait()
                if resp.success:
                    self.output_frame.append_log(f"\n{resp.formatted_data}")
                else:
                    self.output_frame.append_log(f"\nError: {resp.error_message}")
            except Exception:
                pass
        self.root.after(50, self.update_gui)

    def _on_gauge_change(self, *args) -> None:
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

    def toggle_continuous_reading(self) -> None:
        """
        Toggles continuous reading on or off.
        """
        if not self.communicator:
            self.continuous_var.set(False)
            return
        if self.continuous_var.get():
            self.start_continuous_reading()
        else:
            self.stop_continuous_reading()

    def start_continuous_reading(self) -> None:
        if hasattr(self, 'continuous_thread') and self.continuous_thread and self.continuous_thread.is_alive():
            return
        self.communicator.set_continuous_reading(True)
        self.continuous_thread = threading.Thread(target=self.continuous_reading_thread, daemon=True)
        self.continuous_thread.start()

    def stop_continuous_reading(self) -> None:
        if self.communicator:
            self.communicator.stop_continuous_reading()
        if hasattr(self, 'continuous_thread') and self.continuous_thread:
            self.continuous_thread.join(timeout=1.0)
            self.continuous_thread = None

    def continuous_reading_thread(self) -> None:
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
        try:
            val = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {val} ms")
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value.")

    def _toggle_data_tx_mode(self) -> None:
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
        Connects or disconnects based on the button text.
        When the button reads "Connect", a new communicator is created.
        If Simulator Mode is enabled, a simulated communicator is created.
        When the button reads "Disconnect", the current communicator is disconnected.
        """
        if self.connect_button["text"] == "Connect":
            try:
                if self.simulator_enabled:
                    from serial_communication.device_simulator import DeviceSimulator
                    self.communicator = DeviceSimulator(device_type="gauge", config=None, logger=self.logger)
                else:
                    from serial_communication.communicator.gauge_communicator import GaugeCommunicator
                    self.communicator = GaugeCommunicator(
                        port=self.selected_port.get(),
                        gauge_type=self.selected_gauge.get(),
                        logger=self
                    )
                if self.communicator.connect():
                    self.connect_button.config(text="Disconnect")
                    self.log_message("Connection established.")
                    self.cmd_frame.communicator = self.communicator
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
        new_fmt = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_fmt)
        self.log_message(f"Output format changed to: {new_fmt}")

    def apply_serial_settings(self, settings: dict) -> None:
        try:
            self.current_serial_settings.update(settings)
            if self.communicator and hasattr(self.communicator,
                                             'ser') and self.communicator.ser and self.communicator.ser.is_open:
                self.communicator.ser.baudrate = settings['baudrate']
                self.communicator.ser.bytesize = settings['bytesize']
                self.communicator.ser.parity = settings['parity']
                self.communicator.ser.stopbits = settings['stopbits']
                if settings.get('rs485_mode', False):
                    self.communicator.set_rs_mode("RS485")
                    if hasattr(self.communicator.protocol, 'address'):
                        self.communicator.protocol.address = settings.get('rs485_address', 254)
                else:
                    self.communicator.set_rs_mode("RS232")
                self.log_message(f"Serial settings updated: {settings}")
                if settings.get('rs485_mode', False):
                    self.log_message(f"RS485 Address: {settings.get('rs485_address', 254)}")
            else:
                self.log_message("Serial settings applied locally; will take effect on connection.")
        except Exception as e:
            self.log_message(f"Failed to update serial settings: {str(e)}")

    def send_command(self, command: str, response: Optional[GaugeResponse] = None) -> None:
        if response:
            if response.success:
                self.log_message(f">: {command}")
                self.log_message(f"<: {response.formatted_data}")
            else:
                self.log_message(f"Command failed: {response.error_message}")
        else:
            self.log_message(f"\nUnable to send command: {command}")

    def send_manual_command(self, command: str) -> None:
        if not hasattr(self, 'cmd_frame') or not self.cmd_frame:
            self.log_message("CommandFrame is not available.")
            return
        self.cmd_frame.process_command(command)

    def try_all_baud_rates(self) -> bool:
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None
        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()
        try:
            from serial_communication.communicator.gauge_communicator import GaugeCommunicator
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

    def update_continuous_visibility(self) -> None:
        if hasattr(self, 'continuous_frame'):
            if self.communicator and hasattr(self.communicator,
                                             "continuous_output") and self.communicator.continuous_output:
                self.continuous_frame.pack(fill="x", padx=5, pady=5)
            else:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

    def send_enq(self) -> None:
        if not self.communicator or not hasattr(self.communicator,
                                                'ser') or not self.communicator.ser or not self.communicator.ser.is_open:
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
        if self.communicator and hasattr(self.communicator, 'ser') and self.communicator.ser:
            ser = self.communicator.ser
            s = (
                f"=== Port Settings ===\n"
                f"Port: {ser.port}\n"
                f"Baudrate: {ser.baudrate}\n"
                f"Bytesize: {ser.bytesize}\n"
                f"Parity: {ser.parity}\n"
                f"Stopbits: {ser.stopbits}\n"
                f"Timeout: {ser.timeout}\n"
                f"XonXoff: {ser.xonxoff}\n"
                f"RtsCts: {ser.rtscts}\n"
                f"DsrDtr: {ser.dsrdtr}\n"
            )
            self.log_message(s)
        else:
            self.log_message("Not connected - showing saved settings:")
            s = (
                f"=== Saved Settings ===\n"
                f"Baudrate: {self.current_serial_settings['baudrate']}\n"
                f"Bytesize: {self.current_serial_settings['bytesize']}\n"
                f"Parity: {self.current_serial_settings['parity']}\n"
                f"Stopbits: {self.current_serial_settings['stopbits']}\n"
                f"RS485 Mode: {self.current_serial_settings.get('rs485_mode', False)}\n"
                f"RS485 Address: {self.current_serial_settings.get('rs485_address', 254)}\n"
            )
            self.log_message(s)

    def log_message(self, message: str, level: str = "INFO") -> None:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if level.upper() == "ERROR":
            self.logger.error(message)
        elif level.upper() == "DEBUG":
            self.logger.debug(message)
        else:
            self.logger.info(message)
        self.output_frame.append_log(f"[{now}] [{level.upper()}] {message}")

    def error(self, msg: str) -> None:
        self.logger.error(msg)
        self.log_message(msg, level="ERROR")

    def debug(self, message: str) -> None:
        if self.logger.isEnabledFor(logging.DEBUG):
            self.log_message(f"DEBUG: {message}")

    def set_show_debug(self, enabled: bool) -> None:
        if enabled:
            self.logger.setLevel(logging.DEBUG)
            self.log_message("Show Debug: ON")
        else:
            self.logger.setLevel(logging.INFO)
            self.log_message("Show Debug: OFF")

    def on_closing(self) -> None:
        if self.turbo_window:
            self.turbo_window.destroy()
            self.turbo_window = None
        self.stop_continuous_reading()
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()

    # --- Simulator Integration Methods ---

    def set_simulator_mode(self, simulator_enabled: bool) -> None:
        """
        Enables or disables simulator mode. When enabled, the real communicator is replaced
        with a simulated communicator. The connection is maintained until the user clicks Disconnect.

        Args:
            simulator_enabled (bool): True to enable simulation; False to disable.
        """
        self.simulator_enabled = simulator_enabled
        if simulator_enabled:
            # Warn user if a physical port is selected.
            if self.selected_port.get():
                self.log_message("Simulator Mode enabled: Physical devices will be ignored.", level="INFO")
            from serial_communication.device_simulator import DeviceSimulator
            self.communicator = DeviceSimulator(device_type="gauge", config=None, logger=self.logger)
            self.communicator.connect()
            if self.cmd_frame:
                self.cmd_frame.communicator = self.communicator
            if self.debug_frame:
                self.debug_frame.baud_button.config(state="disabled")
            self.log_message("Simulator Mode is now active.", level="INFO")
        else:
            if self.communicator and hasattr(self.communicator, "disconnect"):
                self.communicator.disconnect()
            self.communicator = None
            if self.debug_frame:
                self.debug_frame.baud_button.config(state="normal")
            self.log_message("Simulator Mode disabled. Please connect a physical device.", level="INFO")

    def set_simulation_config(self, config: dict) -> None:
        """
        Updates simulation configuration parameters in the active DeviceSimulator.

        Args:
            config (dict): Simulation configuration options.
        """
        if self.communicator and hasattr(self.communicator, "config"):
            self.communicator.config.update(config)
            self.log_message(f"Simulation configuration updated: {config}", level="INFO")
        else:
            self.log_message("No simulator active; configuration not applied.", level="ERROR")

    def open_simulation_options(self) -> None:
        """
        Opens a simulation options dialog to adjust simulation parameters.
        """
        options_window = tk.Toplevel(self.root)
        options_window.title("Simulation Options")
        tk.Label(options_window, text="Response Delay (s):").grid(row=0, column=0, padx=5, pady=5)
        delay_var = tk.StringVar(
            value=str(self.communicator.config.get("response_delay", 0.1)) if self.communicator else "0.1")
        tk.Entry(options_window, textvariable=delay_var).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(options_window, text="Noise Level (fraction):").grid(row=1, column=0, padx=5, pady=5)
        noise_var = tk.StringVar(
            value=str(self.communicator.config.get("noise_level", 0.05)) if self.communicator else "0.05")
        tk.Entry(options_window, textvariable=noise_var).grid(row=1, column=1, padx=5, pady=5)

        def apply_options():
            try:
                new_config = {
                    "response_delay": float(delay_var.get()),
                    "noise_level": float(noise_var.get())
                }
                self.set_simulation_config(new_config)
                options_window.destroy()
            except ValueError:
                self.log_message("Invalid simulation parameters entered.", level="ERROR")

        tk.Button(options_window, text="Apply", command=apply_options).grid(row=2, column=0, columnspan=2, padx=5,
                                                                            pady=10)


def setup_exception_handling(root, logger) -> None:
    def show_error(msg):
        messagebox.showerror("Error", f"An error occurred: {msg}\n\nCheck the log for details.")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            root.quit()
            return
        logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        root.after(100, lambda: show_error(str(exc_value)))

    sys.excepthook = handle_exception


def create_app_directories() -> tuple:
    app_dir = Path.home() / ".gauge_communicator"
    log_dir = app_dir / "logs"
    config_dir = app_dir / "config"
    for directory in [app_dir, log_dir, config_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    return app_dir, log_dir, config_dir


def on_closing(root, app) -> None:
    try:
        app.on_closing()
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)
    finally:
        root.destroy()


def main() -> None:
    app_dir, log_dir, config_dir = create_app_directories()
    logger = setup_logging("GaugeCommunicator")
    logger.info("Starting Gauge Communication Program")
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app))
    setup_exception_handling(root, logger)
    try:
        app = GaugeApplication(root)
        logger.info("Application initialized successfully")
        window_width = 800
        window_height = 650
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        root.mainloop()
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        messagebox.showerror("Startup Error",
                             f"Failed to start application: {str(e)}\n\nCheck the log for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
