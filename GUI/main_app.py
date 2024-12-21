"""
GaugeApplication: Main application class that manages the overall GUI and orchestrates its frames.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk
import serial.tools.list_ports
from typing import Optional

from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.gauge_tester import GaugeTester
from serial_communication.models import GaugeResponse
from serial_communication.communicator.protocol_factory import PPGProtocol  # or from your new "gauges" folder if changed

# Import your new frames from the same folder
from .serial_settings_frame import SerialSettingsFrame
from .command_frame import CommandFrame
from .debug_frame import DebugFrame
from .output_frame import OutputFrame


class GaugeApplication:
    """
    Main application class for the vacuum gauge communication interface.
    Manages the overall GUI, serial communication, and user interactions.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Vacuum Gauge Communication Interface")
        self.root.geometry("800x650")

        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="PPG550")
        self.output_format = tk.StringVar(value="ASCII")

        self.continuous_var = tk.BooleanVar(value=False)
        self.continuous_thread = None
        self.response_queue = queue.Queue()
        self.update_interval = tk.StringVar(value="1000")

        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        self.communicator: Optional[GaugeCommunicator] = None

        self._create_gui()

        self.output_format.trace('w', self._on_output_format_change)
        self.selected_gauge.trace('w', self._on_gauge_change)

        self.refresh_ports()

    def _create_gui(self):
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)

        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)
        self.gauge_menu = ttk.OptionMenu(
            conn_frame,
            self.selected_gauge,
            "PCG550",
            *GAUGE_PARAMETERS.keys()
        )
        self.gauge_menu.pack(side=tk.LEFT, padx=5)

        self.connect_button = ttk.Button(conn_frame, text="Connect", command=self.connect_disconnect)
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # Create frames
        self.serial_frame = SerialSettingsFrame(self.root, self.apply_serial_settings, self.send_manual_command)
        self.serial_frame.set_logger(self)
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        self.cmd_frame = CommandFrame(self.root, self.selected_gauge, self.send_command)
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        self.debug_frame = DebugFrame(self.root, self.try_all_baud_rates, self.send_enq, self.show_port_settings, self.output_format)
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        self.output_frame = OutputFrame(self.root, self.output_format)
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.continuous_frame = ttk.LabelFrame(self.root, text="Continuous Reading")

        ttk.Checkbutton(
            self.continuous_frame,
            text="View Continuous Reading",
            variable=self.continuous_var,
            command=self.toggle_continuous_reading
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(self.continuous_frame, text="Update Interval (ms):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(self.continuous_frame, textvariable=self.update_interval, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Button(self.continuous_frame, text="Update", command=self._update_interval_value).pack(side=tk.LEFT, padx=5)

        self.update_gui()  # Start GUI update loop

    def update_gui(self):
        while not self.response_queue.empty():
            try:
                response = self.response_queue.get_nowait()
                if response.success:
                    self.output_frame.append_log(f"\n{response.formatted_data}")
                else:
                    self.output_frame.append_log(f"\nError: {response.error_message}")
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
            interval = int(self.update_interval.get()) / 1000.0
            self.communicator.read_continuous(
                lambda response: self.response_queue.put(response),
                interval
            )
        except Exception as e:
            self.response_queue.put(GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=f"Thread error: {str(e)}"
            ))

    def _update_interval_value(self):
        try:
            interval = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {interval} ms")
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value.")

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
        if self.communicator is None:  # Connect
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
        else:  # Disconnect
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
        new_format = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_format)
        self.log_message(f"Output format changed to: {new_format}")

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
                successful_baud = temp_communicator.baudrate
                self.serial_frame.baud_var.set(str(successful_baud))
                self.apply_serial_settings({
                    'baudrate': successful_baud,
                    'bytesize': 8,
                    'parity': 'N',
                    'stopbits': 1.0
                })

                test_results = tester.run_all_tests()
                for cmd_name, result in test_results.get("commands_tested", {}).items():
                    if result.get("success"):
                        self.log_message(f"Test {cmd_name}: {result.get('response', 'OK')}")
                    else:
                        self.log_message(f"Test {cmd_name} failed: {result.get('error', 'Unknown error')}")

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
            if temp_communicator and temp_communicator.ser and temp_communicator.ser.is_open:
                temp_communicator.disconnect()
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
            settings = f"""
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
            self.log_message(settings)
        else:
            self.log_message("Not connected - showing saved settings:")
            settings = f"""
=== Saved Settings ===
Baudrate: {self.current_serial_settings['baudrate']}
Bytesize: {self.current_serial_settings['bytesize']}
Parity: {self.current_serial_settings['parity']}
Stopbits: {self.current_serial_settings['stopbits']}
RS485 Mode: {self.current_serial_settings.get('rs485_mode', False)}
RS485 Address: {self.current_serial_settings.get('rs485_address', 254)}
"""
            self.log_message(settings)

    def log_message(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_frame.append_log(f"[{timestamp}] {message}")

    def debug(self, message: str):
        self.log_message(f"DEBUG: {message}")

    def info(self, message: str):
        self.log_message(message)

    def warning(self, message: str):
        self.log_message(f"WARNING: {message}")

    def error(self, message: str):
        self.log_message(f"ERROR: {message}")

    def on_closing(self):
        self.stop_continuous_reading()
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()
