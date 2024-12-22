#!/usr/bin/env python3
"""
main_app.py

This module implements the core GaugeApplication class that coordinates all aspects of the
vacuum gauge communication program including:
- GUI layout and window management
- Connection handling and port settings
- Command processing and responses
- Continuous reading functionality
- Debug logging and display
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk
import serial.tools.list_ports
import logging
from typing import Optional

# Imports configuration constants
from serial_communication.config import (
    GAUGE_PARAMETERS,
    GAUGE_OUTPUT_FORMATS,
    setup_logging
)

# Imports core communication classes
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.gauge_tester import GaugeTester
from serial_communication.gauges.protocols.ppg_protocol import PPGProtocol

# Imports data model classes
from serial_communication.models import GaugeCommand, GaugeResponse

# Imports the GUI frames
from .serial_settings_frame import SerialSettingsFrame
from .command_frame import CommandFrame
from .debug_frame import DebugFrame
from .output_frame import OutputFrame


class GaugeApplication:
    """
    Main application class that unifies the GUI and communication functionality.
    Handles window layout, event binding, and coordination between components.
    """

    def __init__(self, root: tk.Tk):
        """
        Initializes the application window and all major components.
        Args:
            root: The main Tkinter root window
        """
        # Stores reference to root window and configures it
        self.root = root
        self.root.title("Vacuum Gauge Communication Interface")
        self.root.geometry("800x650")

        # Creates StringVars to track selected port, gauge type and output format
        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="CDG045D")  # Sets default gauge
        self.output_format = tk.StringVar(value="ASCII")  # Sets default format

        # Creates variables to manage continuous reading state
        self.continuous_var = tk.BooleanVar(value=False)  # Tracks if continuous reading enabled
        self.continuous_thread = None  # Background thread for reading
        self.response_queue = queue.Queue()  # Queue for passing responses back to GUI
        self.update_interval = tk.StringVar(value="1000")  # Milliseconds between reads
        self.data_tx_mode = tk.BooleanVar(value=False)  # Tracks gauge transmission mode

        # Stores current serial port configuration
        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        # Communicator starts as None until connection established
        self.communicator: Optional[GaugeCommunicator] = None

        # Sets up logging for the application
        self.logger = setup_logging("GaugeApplication")
        self.show_debug = True  # Controls visibility of debug messages

        # Creates and arranges GUI elements
        self._create_gui()

        # Binds variables to update handlers
        self.output_format.trace('w', self._on_output_format_change)  # Updates when format changes
        self.selected_gauge.trace('w', self._on_gauge_change)  # Updates when gauge changes

        # Performs initial port scan
        self.refresh_ports()

        # Starts periodic check for queued responses
        self.update_gui()

    def _create_gui(self):
        """Creates and arranges all GUI frames and elements."""

        # Creates connection frame with port and gauge selection
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds port selection dropdown
        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        # Adds refresh button to rescan ports
        ttk.Button(
            conn_frame,
            text="Refresh",
            command=self.refresh_ports
        ).pack(side=tk.LEFT, padx=5)

        # Organizes gauges by type for dropdown
        gauge_dict = {
            "Capacitive": ["CDG025D", "CDG045D"],
            "Pirani/Capacitive": ["PCG550", "PSG550"],
            "MEMS Pirani": ["PPG550", "PPG570"],
            "Cold Cathode": ["MAG500", "MPG500"],
            "Hot Cathode": ["BPG40x", "BPG552"],
            "Combination": ["BCG450", "BCG552"],
            "Turbo Controller": ["TC600"]
        }

        # Flattens gauge list for dropdown
        gauge_list = []
        for cat, arr in gauge_dict.items():
            gauge_list.extend(arr)

        # Adds gauge selection dropdown
        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)
        self.gauge_combo = ttk.Combobox(
            conn_frame,
            textvariable=self.selected_gauge,
            values=gauge_list,
            state="readonly",
            width=20
        )
        self.gauge_combo.pack(side=tk.LEFT, padx=5)

        # Selects first gauge as default if list not empty
        if gauge_list:
            self.selected_gauge.set(gauge_list[0])

        # Adds connect/disconnect button
        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self.connect_disconnect
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # Creates frame for serial port settings
        self.serial_frame = SerialSettingsFrame(
            self.root,
            self.apply_serial_settings,
            self.send_manual_command
        )
        self.serial_frame.set_logger(self)
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # Creates frame for sending commands
        self.cmd_frame = CommandFrame(
            self.root,
            self.selected_gauge,
            self.send_command
        )
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Creates frame for debug controls
        self.debug_frame = DebugFrame(
            self.root,
            self.try_all_baud_rates,
            self.send_enq,
            self.show_port_settings,
            self.output_format
        )
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        # Creates frame for log output
        self.output_frame = OutputFrame(
            self.root,
            self.output_format
        )
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Creates frame for continuous reading controls
        self.continuous_frame = ttk.LabelFrame(self.root, text="Continuous Reading")
        self.continuous_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds checkbox to enable/disable continuous reading
        self.continuous_checkbox = ttk.Checkbutton(
            self.continuous_frame,
            text="View Continuous Reading",
            variable=self.continuous_var,
            command=self.toggle_continuous_reading
        )
        self.continuous_checkbox.pack(side=tk.LEFT, padx=5)

        # Adds interval entry field
        ttk.Label(
            self.continuous_frame,
            text="Update Interval (ms):"
        ).pack(side=tk.LEFT, padx=5)

        self.interval_entry = ttk.Entry(
            self.continuous_frame,
            textvariable=self.update_interval,
            width=6
        )
        self.interval_entry.pack(side=tk.LEFT, padx=5)

        # Adds button to apply interval changes
        ttk.Button(
            self.continuous_frame,
            text="Update",
            command=self._update_interval_value
        ).pack(side=tk.LEFT, padx=5)

        # Adds button to toggle transmission mode
        self.toggle_datatx_button = ttk.Button(
            self.continuous_frame,
            text="Start Continuous",
            command=self._toggle_data_tx_mode
        )
        self.toggle_datatx_button.pack(side=tk.LEFT, padx=5)

    def update_gui(self):
        """
        Processes any queued responses and updates the display.
        Reschedules itself to run again after 50ms.
        """
        # Processes all queued responses
        while not self.response_queue.empty():
            try:
                resp = self.response_queue.get_nowait()
                if resp.success:
                    # Formats successful response data
                    self.output_frame.append_log(f"\n{resp.formatted_data}")
                else:
                    # Shows error message for failed response
                    self.output_frame.append_log(f"\nError: {resp.error_message}")
            except queue.Empty:
                pass

        # Reschedules check in 50ms
        self.root.after(50, self.update_gui)

    def check_data_tx_mode(self):
        """
        Queries the gauge's current data transmission mode.
        Returns True if gauge is in continuous mode, False otherwise.
        """
        if not self.communicator:
            return False

        try:
            # Sends query command for transmission mode
            cmd = GaugeCommand(
                name="data_tx_mode",
                command_type="?"
            )

            resp = self.communicator.send_command(cmd)
            if resp.success:
                # Extracts mode from response (bit 0)
                mode = resp.raw_data[2] & 0x01
                self.data_tx_mode.set(bool(mode))

                # Updates button text to match mode
                self.toggle_datatx_button.config(
                    text="Stop Continuous" if mode else "Start Continuous"
                )
                return bool(mode)

            return False

        except Exception as e:
            self.logger.error(f"Error checking data_tx_mode: {str(e)}")
            return False

    def _toggle_data_tx_mode(self):
        """
        Toggles the gauge between continuous and polled transmission modes.
        Updates UI elements to reflect the change.
        """
        if not self.communicator:
            self.log_message("No active connection")
            return

        try:
            # Gets current mode and calculates new state
            current = self.data_tx_mode.get()
            new_mode = 0 if current else 1

            # Creates command to change mode
            cmd = GaugeCommand(
                name="data_tx_mode",
                command_type="!",
                parameters={"value": new_mode}
            )

            # Sends command and handles response
            resp = self.communicator.send_command(cmd)
            if resp.success:
                # Updates state tracking and button text
                self.data_tx_mode.set(not current)
                self.toggle_datatx_button.config(
                    text="Stop Continuous" if new_mode else "Start Continuous"
                )
                self.log_message(
                    f"Data transmission mode set to {'continuous' if new_mode else 'polled'}"
                )
            else:
                self.log_message(f"Failed to change mode: {resp.error_message}")

        except Exception as e:
            self.log_message(f"Error toggling mode: {str(e)}")

    def connect_disconnect(self):
        """
        Handles connection and disconnection from the gauge.
        Updates UI elements to reflect connection state.
        """
        if self.communicator is None:
            try:
                # Creates new communicator
                self.communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self.logger
                )

                # Attempts connection
                if self.communicator.connect():
                    # Updates UI for connected state
                    self.connect_button.config(text="Disconnect")
                    self.log_message("Connection established.")

                    # Enables command frame and debug controls
                    self.cmd_frame.communicator = self.communicator
                    self.cmd_frame.set_enabled(True)
                    self.debug_frame.set_enabled(True)

                    # Checks initial transmission mode
                    if self.check_data_tx_mode():
                        # Starts continuous reading if gauge is in continuous mode
                        self.continuous_var.set(True)
                        self.start_continuous_reading()

                    # Shows/hides continuous frame based on gauge support
                    self.update_continuous_visibility()
                else:
                    self.log_message("Failed to connect.")
                    self.communicator = None

            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.communicator = None
        else:
            try:
                # Stops continuous reading if active
                self.stop_continuous_reading()

                # Disconnects from gauge
                self.communicator.disconnect()
                self.communicator = None

                # Resets UI elements
                self.connect_button.config(text="Connect")
                self.log_message("Disconnected.")
                self.cmd_frame.set_enabled(False)
                self.debug_frame.set_enabled(False)
                self.continuous_var.set(False)
                self.continuous_frame.pack_forget()

            except Exception as e:
                self.log_message(f"Disconnection error: {e}")

    def apply_serial_settings(self, settings: dict):
        """
        Updates serial port configuration for active connection.
        Handles both basic serial parameters and RS485 specific settings.

        Args:
            settings: Dictionary containing serial parameters like baudrate, bytesize,
                     parity, stopbits, and optional RS485 configuration
        """
        try:
            # Updates stored settings
            self.current_serial_settings.update(settings)

            # Applies settings if port is open
            if self.communicator and self.communicator.ser and self.communicator.ser.is_open:
                # Updates basic serial parameters
                self.communicator.ser.baudrate = settings['baudrate']
                self.communicator.ser.bytesize = settings['bytesize']
                self.communicator.ser.parity = settings['parity']
                self.communicator.ser.stopbits = settings['stopbits']

                # Handles RS485 mode settings if present
                if settings.get('rs485_mode', False):
                    self.communicator.set_rs_mode("RS485")
                    if isinstance(self.communicator.protocol, PPGProtocol):
                        self.communicator.protocol.address = settings.get('rs485_address', 254)
                else:
                    self.communicator.set_rs_mode("RS232")

                # Logs applied settings
                self.log_message(f"Serial settings updated: {settings}")
                if settings.get('rs485_mode', False):
                    self.log_message(f"RS485 Address: {settings.get('rs485_address', 254)}")
        except Exception as e:
            self.log_message(f"Failed to update serial settings: {str(e)}")
            raise

    def refresh_ports(self):
        """
        Rescans available COM ports and updates port selection dropdown.
        """
        # Gets list of available ports
        ports = [p.device for p in serial.tools.list_ports.comports()]

        # Updates dropdown menu
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(
                label=port,
                command=lambda p=port: self.selected_port.set(p)
            )

        # Selects first port if available
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    def toggle_continuous_reading(self):
        """
        Enables or disables continuous reading based on checkbox state.
        """
        if not self.communicator:
            self.continuous_var.set(False)
            return

        if self.continuous_var.get():
            self.start_continuous_reading()
        else:
            self.stop_continuous_reading()

    def start_continuous_reading(self):
        """
        Starts background thread for continuous reading if not already running.
        """
        # Verifies no existing thread is running
        if self.continuous_thread and self.continuous_thread.is_alive():
            return

        # Notifies communicator to enable continuous mode
        self.communicator.set_continuous_reading(True)

        # Creates and starts background thread
        self.continuous_thread = threading.Thread(
            target=self.continuous_reading_thread,
            daemon=True  # Thread will terminate when main program exits
        )
        self.continuous_thread.start()

    def stop_continuous_reading(self):
        """
        Stops continuous reading by signaling thread to exit and waiting for completion.
        """
        # Signals communicator to stop continuous mode
        if self.communicator:
            self.communicator.stop_continuous_reading()

        # Waits for thread to finish (timeout prevents hanging)
        if self.continuous_thread:
            self.continuous_thread.join(timeout=1.0)
            self.continuous_thread = None

    def continuous_reading_thread(self):
        """
        Worker function that repeatedly reads from gauge at specified intervals.
        Runs in background thread to prevent GUI freezing.
        """
        try:
            # Converts milliseconds to seconds for interval
            interval_sec = int(self.update_interval.get()) / 1000.0

            # Starts continuous reading loop
            self.communicator.read_continuous(
                lambda r: self.response_queue.put(r),  # Callback to queue responses
                interval_sec
            )
        except Exception as e:
            # Reports errors through queue
            self.response_queue.put(GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=f"Thread error: {str(e)}"
            ))

    def _update_interval_value(self):
        """
        Updates the continuous reading interval when user clicks 'Update'.
        Restarts continuous reading if active.
        """
        try:
            # Validates and applies new interval
            val = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {val} ms")

            # Restarts continuous reading if active
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value.")

    def set_show_debug(self, enabled: bool):
        """
        Controls visibility of debug messages in output.
        Updates both logger level and existing message display.
        """
        self.show_debug = enabled
        if enabled:
            # Shows all messages by setting DEBUG level
            self.logger.setLevel(logging.DEBUG)
            self.log_message("Debug messages enabled")
        else:
            # Hides debug messages by setting INFO level
            self.logger.setLevel(logging.INFO)
            self.log_message("Debug messages disabled")

        # Updates output frame to filter existing messages
        if hasattr(self, 'output_frame'):
            self.output_frame.filter_debug_messages(enabled)

    def log_message(self, msg: str):
        """
        Writes a timestamped message to the output frame.
        Args:
            msg: The message text to display
        """
        from datetime import datetime
        # Formats current timestamp
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Adds message to output
        self.output_frame.append_log(f"[{now}] {msg}")

    def try_all_baud_rates(self):
        """
        Systematically tests different baud rates to find a working connection.
        Creates a temporary communicator for each test to avoid disrupting the main connection.
        Returns True if a working baud rate is found, False otherwise.
        """
        # Disconnects existing connection if any
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        # Starts testing sequence
        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()

        try:
            # Creates temporary communicator for testing
            temp = GaugeCommunicator(
                port=port,
                gauge_type=self.selected_gauge.get(),
                logger=self.logger
            )

            # Sets output format for consistent display
            temp.set_output_format(self.output_format.get())

            # Creates tester instance
            tester = GaugeTester(temp, self)

            # Runs baud rate tests
            success = tester.try_all_baud_rates(port)
            if success:
                # If successful, updates settings with working baud rate
                succ_baud = temp.baudrate
                self.serial_frame.baud_var.set(str(succ_baud))
                self.apply_serial_settings({
                    'baudrate': succ_baud,
                    'bytesize': 8,
                    'parity': 'N',
                    'stopbits': 1.0
                })

                # Runs additional gauge tests
                results = tester.run_all_tests()
                for c_name, rdict in results.get("commands_tested", {}).items():
                    if rdict.get("success"):
                        self.log_message(f"Test {c_name}: {rdict.get('response', 'OK')}")
                    else:
                        self.log_message(f"Test {c_name} failed: {rdict.get('error', 'Unknown error')}")

                # Cleans up temporary communicator
                temp.disconnect()
                return True
            else:
                if temp.ser and temp.ser.is_open:
                    temp.disconnect()
                return False

        except Exception as e:
            import traceback
            self.log_message(f"Baud rate testing error: {str(e)}")
            self.log_message(f"Traceback: {traceback.format_exc()}")
            return False

    def _on_output_format_change(self, *args):
        """
        Handles changes to the output format selection.
        Updates both the communicator and any active displays.

        The format change affects how data is displayed in logs and responses.
        Valid formats include: Hex, ASCII, Binary, Decimal, etc.
        """
        # Gets the newly selected format
        new_fmt = self.output_format.get()

        # Updates communicator format if connected
        if self.communicator:
            self.communicator.set_output_format(new_fmt)

        # Logs the format change
        self.log_message(f"Output format changed to: {new_fmt}")

    def _on_gauge_change(self, *args):
        """
        Handles selection of a different gauge type.
        Updates serial settings, interface modes, and display formats.

        Each gauge type may have specific:
        - Default baud rates and serial settings
        - RS485 support and addressing
        - Output format preferences
        - Continuous reading capabilities
        """
        # Gets selected gauge type
        gauge_type = self.selected_gauge.get()

        # Loads parameters for this gauge type
        if gauge_type in GAUGE_PARAMETERS:
            params = GAUGE_PARAMETERS[gauge_type]

            # Updates baud rate display
            self.serial_frame.baud_var.set(str(params["baudrate"]))

            # Determines RS485 support
            rs485_supported = "rs_modes" in params and "RS485" in params["rs_modes"]
            rs485_address = params.get("address", 254) if rs485_supported else 254

            # Updates RS485 mode settings
            self.serial_frame.set_rs485_mode(rs485_supported, rs485_address)

            # Sets preferred output format for this gauge
            self.output_format.set(GAUGE_OUTPUT_FORMATS.get(gauge_type))

            # Hides continuous frame if not connected
            if not self.communicator:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

            # Applies default serial settings for this gauge
            self.apply_serial_settings({
                'baudrate': params["baudrate"],
                'bytesize': params.get("bytesize", 8),
                'parity': params.get("parity", 'N'),
                'stopbits': params.get("stopbits", 1.0),
                'rs485_mode': rs485_supported,
                'rs485_address': rs485_address
            })

    def send_enq(self):
        """
        Sends an ENQ (Enquiry) character to test gauge responsiveness.
        Some gauges respond with ACK or version info, while others might ignore it.
        """
        if not self.communicator or not self.communicator.ser or not self.communicator.ser.is_open:
            self.log_message("Not connected")
            return

        try:
            # Sets output format for test
            self.communicator.set_output_format(self.output_format.get())

            # Creates tester instance
            tester = GaugeTester(self.communicator, self)

            # Sends ENQ and checks response
            if tester.send_enq():
                self.log_message("> ENQ test successful")
            else:
                self.log_message("> ENQ test failed")

        except Exception as e:
            self.log_message(f"ENQ test error: {str(e)}")

    def show_port_settings(self):
        """
        Displays current serial port configuration.
        Shows active settings if connected, or stored settings if disconnected.
        """
        if self.communicator and self.communicator.ser:
            # Gets settings from active connection
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
            # Shows stored settings if not connected
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

    def send_manual_command(self, command: str):
        """
        Passes manual commands from the SerialSettingsFrame to the CommandFrame.

        Args:
            command: Raw command string entered by user
        """
        if not hasattr(self, 'cmd_frame'):
            self.log_message("CommandFrame is not available.")
            return

        # Forwards command to CommandFrame for processing
        self.cmd_frame.send_manual_command(command)

    def send_command(self, command: str, response: Optional[GaugeResponse] = None):
        """
        Called by CommandFrame after command processing to log results.
        Args:
            command: The command that was sent
            response: Optional response received from gauge
        """
        if response:
            if response.success:
                # Logs successful command and response
                self.log_message(f">: {command}")
                self.log_message(f"<: {response.formatted_data}")
            else:
                # Logs command failure
                self.log_message(f"Command failed: {response.error_message}")
        else:
            self.log_message(f"\nUnable to send command: {command}")

    def update_continuous_visibility(self):
        """
        Shows or hides continuous reading frame based on gauge support.
        """
        if hasattr(self, 'continuous_frame'):
            if self.communicator and self.communicator.continuous_output:
                # Shows frame if gauge supports continuous mode
                self.continuous_frame.pack(fill="x", padx=5, pady=5)
            else:
                # Hides frame and disables continuous mode
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

    def on_closing(self):
        """
        Handles application shutdown.
        Stops background tasks and closes connections.
        """
        # Stops continuous reading if active
        self.stop_continuous_reading()

        # Disconnects from gauge if connected
        if self.communicator:
            self.communicator.disconnect()

        # Destroys main window
        self.root.destroy()