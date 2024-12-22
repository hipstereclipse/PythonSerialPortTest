"""
GaugeApplication: Main application class that manages the overall GUI and orchestrates its frames.
"""

import queue                            # Imports queue to handle thread-safe communication between threads
import threading                        # Imports threading to run continuous reads in the background
import tkinter as tk                    # Imports tkinter for GUI building
from tkinter import ttk                 # Imports themed tkinter widgets
import serial.tools.list_ports          # Imports pySerial tools for listing serial ports
from typing import Optional             # Imports Optional for type hinting

# Imports all necessary modules for gauge communication
from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS
from serial_communication.communicator.gauge_communicator import GaugeCommunicator
from serial_communication.communicator.gauge_tester import GaugeTester
from serial_communication.models import GaugeResponse
from serial_communication.communicator.protocol_factory import PPGProtocol

# Imports custom frames to keep the GUI modular
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
        # Stores the reference to the root window
        self.root = root
        # Sets the window title
        self.root.title("Vacuum Gauge Communication Interface")
        # Sets initial window size
        self.root.geometry("800x650")

        # Holds the currently selected serial port
        self.selected_port = tk.StringVar()
        # Holds the user’s gauge selection (defaults to "PPG550" as an example)
        self.selected_gauge = tk.StringVar(value="PPG550")
        # Holds the user’s selected output format (defaults to "ASCII")
        self.output_format = tk.StringVar(value="ASCII")

        # Controls whether the continuous reading is enabled
        self.continuous_var = tk.BooleanVar(value=False)
        # Reference to the continuous reading thread
        self.continuous_thread = None
        # Queue to hold gauge responses from the background thread
        self.response_queue = queue.Queue()
        # How frequently to poll in continuous reading (in milliseconds)
        self.update_interval = tk.StringVar(value="1000")

        # A dict to store the current serial settings
        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        # Reference to the GaugeCommunicator that handles the serial
        self.communicator: Optional[GaugeCommunicator] = None

        # Calls a helper method to create all GUI elements
        self._create_gui()

        # Watches for changes in output_format and selected_gauge
        self.output_format.trace('w', self._on_output_format_change)
        self.selected_gauge.trace('w', self._on_gauge_change)

        # Populates the port selection dropdown
        self.refresh_ports()

    def _create_gui(self):
        """
        Creates and lays out the main GUI frames and widgets:
         - Connection frame (port/gauge selection, connect button)
         - SerialSettingsFrame for serial configuration
         - CommandFrame for sending commands
         - DebugFrame for debug & testing features
         - OutputFrame for logging and display
         - Continuous reading frame for enabling background data reads
        """

        # Creates a labeled frame for connection settings
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adds a label for the port dropdown
        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        # Creates an OptionMenu to list serial ports
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        # Adds a button to refresh the list of serial ports
        ttk.Button(conn_frame, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)

        # Groups known gauge types for better organization
        gauge_groups = {
            "Capacitive": ["CDG025D", "CDG045D"],
            "Pirani/Capacitive": ["PCG550", "PSG550"],
            "MEMS Pirani": ["PPG550", "PPG570"],
            "Cold Cathode": ["MAG500", "MPG500"],
            "Hot Cathode": ["BPG40x", "BPG552"],
            "Combination": ["BCG450", "BCG552"],
            "Turbo Controller": ["TC600"]
        }

        # Adds label for gauge selection
        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)

        # Prepares a list of all available gauges by group
        gauge_list = []
        for group, gauges in gauge_groups.items():
            gauge_list.extend(gauges)

        # Creates a ComboBox to select a gauge
        self.gauge_combo = ttk.Combobox(
            conn_frame,
            textvariable=self.selected_gauge,
            values=gauge_list,
            state="readonly",
            width=20
        )
        self.gauge_combo.pack(side=tk.LEFT, padx=5)

        # Sets a default gauge (the first in the gauge_list, if present)
        if gauge_list:
            self.selected_gauge.set(gauge_list[0])

        # Adds a button to connect or disconnect from the gauge
        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self.connect_disconnect
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # Creates a frame for adjusting serial settings
        self.serial_frame = SerialSettingsFrame(
            self.root,
            self.apply_serial_settings,
            self.send_manual_command
        )
        # Passes self as a logger object for optional log messages
        self.serial_frame.set_logger(self)
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # Creates a frame for sending commands quickly or manually
        self.cmd_frame = CommandFrame(
            self.root,
            self.selected_gauge,
            self.send_command
        )
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Creates a debug frame for advanced testing like trying all baud rates
        self.debug_frame = DebugFrame(
            self.root,
            self.try_all_baud_rates,
            self.send_enq,
            self.show_port_settings,
            self.output_format
        )
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        # Creates the output frame to display logs and gauge responses
        self.output_frame = OutputFrame(
            self.root,
            self.output_format
        )
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Creates a labeled frame to handle continuous reading
        self.continuous_frame = ttk.LabelFrame(
            self.root,
            text="Continuous Reading"
        )

        # Adds a checkbox to toggle continuous reading of gauge data
        ttk.Checkbutton(
            self.continuous_frame,
            text="View Continuous Reading",
            variable=self.continuous_var,
            command=self.toggle_continuous_reading
        ).pack(side=tk.LEFT, padx=5)

        # Asks user how often to update in ms
        ttk.Label(
            self.continuous_frame,
            text="Update Interval (ms):"
        ).pack(side=tk.LEFT, padx=5)

        # Lets user enter the desired polling interval
        ttk.Entry(
            self.continuous_frame,
            textvariable=self.update_interval,
            width=6
        ).pack(side=tk.LEFT, padx=5)

        # Adds a button to apply a new update interval
        ttk.Button(
            self.continuous_frame,
            text="Update",
            command=self._update_interval_value
        ).pack(side=tk.LEFT, padx=5)

        # Updates the GUI dynamically after creation
        self.update_gui()

    def update_gui(self):
        """
        Periodically fetches any new responses from the queue, updates the OutputFrame,
        and schedules itself to run again in 50ms.
        """
        # Checks if there are any new messages in the response_queue
        while not self.response_queue.empty():
            try:
                # Gets the oldest response without blocking
                response = self.response_queue.get_nowait()
                # Checks if the response indicated success or an error
                if response.success:
                    self.output_frame.append_log(f"\n{response.formatted_data}")
                else:
                    self.output_frame.append_log(f"\nError: {response.error_message}")
            except queue.Empty:
                # If the queue is empty, do nothing
                pass

        # Schedules the next call of this method in 50ms
        self.root.after(50, self.update_gui)

    def _on_gauge_change(self, *args):
        """
        Called when the user selects a different gauge type.
        Updates serial settings and output format to match gauge defaults.
        """
        gauge_type = self.selected_gauge.get()

        # Looks up gauge parameters for the new gauge
        if gauge_type in GAUGE_PARAMETERS:
            params = GAUGE_PARAMETERS[gauge_type]
            # Sets the baud rate in the GUI to the gauge's recommended default
            self.serial_frame.baud_var.set(str(params["baudrate"]))

            # Checks if RS485 is supported by the gauge
            rs485_supported = "rs_modes" in params and "RS485" in params["rs_modes"]
            # If RS485 is supported, gets an address from params or defaults to 254
            rs485_address = params.get("address", 254) if rs485_supported else 254

            # Applies the new RS485 mode in the SerialSettingsFrame
            self.serial_frame.set_rs485_mode(rs485_supported, rs485_address)

            # Updates the output format if specified for this gauge
            self.output_format.set(GAUGE_OUTPUT_FORMATS.get(gauge_type))

            # If not connected, hides the continuous reading frame
            if not self.communicator:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

            # Also updates the internal serial settings
            self.apply_serial_settings({
                'baudrate': params["baudrate"],
                'bytesize': params.get("bytesize", 8),
                'parity': params.get("parity", 'N'),
                'stopbits': params.get("stopbits", 1.0),
                'rs485_mode': rs485_supported,
                'rs485_address': rs485_address
            })

    def toggle_continuous_reading(self):
        """
        Called when the user toggles the "View Continuous Reading" checkbox.
        Starts or stops a continuous reading thread accordingly.
        """
        if not self.communicator:
            # Disables the checkbox if there's no active communicator
            self.continuous_var.set(False)
            return

        if self.continuous_var.get():
            self.start_continuous_reading()
        else:
            self.stop_continuous_reading()

    def start_continuous_reading(self):
        """
        Launches a background thread that polls the gauge at fixed intervals.
        """
        # Prevents multiple threads from starting simultaneously
        if self.continuous_thread and self.continuous_thread.is_alive():
            return

        # Tells the communicator we want to read continuously
        self.communicator.set_continuous_reading(True)
        # Creates a daemon thread to read data without blocking the GUI
        self.continuous_thread = threading.Thread(target=self.continuous_reading_thread, daemon=True)
        self.continuous_thread.start()

    def stop_continuous_reading(self):
        """
        Instructs the communicator to stop sending continuous data
        and waits for the thread to finish.
        """
        if self.communicator:
            self.communicator.stop_continuous_reading()

        if self.continuous_thread:
            self.continuous_thread.join(timeout=1.0)
            self.continuous_thread = None

    def continuous_reading_thread(self):
        """
        The worker function that repeatedly calls communicator.read_continuous().
        Runs on a separate thread to avoid blocking the GUI.
        """
        try:
            # Converts milliseconds to seconds
            interval = int(self.update_interval.get()) / 1000.0
            # Calls a helper in communicator to repeatedly poll
            self.communicator.read_continuous(
                lambda response: self.response_queue.put(response),
                interval
            )
        except Exception as e:
            # If an error occurs, puts an error response in the queue
            self.response_queue.put(GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=f"Thread error: {str(e)}"
            ))

    def _update_interval_value(self):
        """
        Called when the user clicks 'Update' to apply a new update interval
        for continuous reading.
        """
        try:
            interval = int(self.update_interval.get())
            self.log_message(f"Update interval set to: {interval} ms")
            # Restarts continuous reading if it's currently enabled
            if self.continuous_var.get():
                self.stop_continuous_reading()
                self.start_continuous_reading()
        except ValueError:
            self.log_message("Invalid interval value.")

    def refresh_ports(self):
        """
        Refreshes the list of available serial ports
        and updates the port OptionMenu.
        """
        # Gets the list of available serial ports via pySerial
        ports = [p.device for p in serial.tools.list_ports.comports()]
        # Clears the existing menu items
        menu = self.port_menu["menu"]
        menu.delete(0, "end")

        # Populates new items
        for port in ports:
            menu.add_command(label=port, command=lambda p=port: self.selected_port.set(p))

        # Selects the first port by default, if any
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    def connect_disconnect(self):
        """
        Toggles between connecting and disconnecting from the selected gauge.
        """
        # If no communicator is present, it means we are not connected yet
        if self.communicator is None:
            try:
                # Creates a new GaugeCommunicator with the selected port and gauge
                self.communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )
                # Tries to open the serial connection
                if self.communicator.connect():
                    # Updates the connect button to read "Disconnect"
                    self.connect_button.config(text="Disconnect")
                    self.log_message("Connection established.")
                    # Passes the communicator to the CommandFrame
                    self.cmd_frame.communicator = self.communicator
                    # Enables the CommandFrame and DebugFrame
                    self.cmd_frame.set_enabled(True)
                    self.debug_frame.set_enabled(True)
                    # Updates the continuous reading UI
                    self.update_continuous_visibility()
                else:
                    self.log_message("Failed to connect.")
                    self.communicator = None
            except Exception as e:
                self.log_message(f"Connection error: {e}")
                self.communicator = None
        else:
            # Currently connected, so handle a disconnection
            try:
                # Stops continuous reading if it’s running
                self.stop_continuous_reading()
                # Closes the serial port
                self.communicator.disconnect()
                self.communicator = None
                # Resets the connect button text
                self.connect_button.config(text="Connect")
                self.log_message("Disconnected.")
                # Disables frames that require a connected communicator
                self.cmd_frame.set_enabled(False)
                self.debug_frame.set_enabled(False)
                self.continuous_var.set(False)
                self.continuous_frame.pack_forget()
            except Exception as e:
                self.log_message(f"Disconnection error: {e}")

    def _on_output_format_change(self, *args):
        """
        Called whenever output_format changes.
        Updates the communicator's output format if connected,
        and logs a message.
        """
        new_format = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_format)
        self.log_message(f"Output format changed to: {new_format}")

    def apply_serial_settings(self, settings: dict):
        """
        Applies new serial settings to the current communicator, if it exists.
        Also updates the internal dictionary self.current_serial_settings.
        """
        try:
            # Updates the local dict first
            self.current_serial_settings.update(settings)

            # If currently connected, applies them directly to the open port
            if self.communicator and self.communicator.ser and self.communicator.ser.is_open:
                self.communicator.ser.baudrate = settings['baudrate']
                self.communicator.ser.bytesize = settings['bytesize']
                self.communicator.ser.parity = settings['parity']
                self.communicator.ser.stopbits = settings['stopbits']

                # Sets RS485 or RS232 mode
                if settings.get('rs485_mode', False):
                    self.communicator.set_rs_mode("RS485")
                    if isinstance(self.communicator.protocol, PPGProtocol):
                        # For PPG gauges, sets the RS485 address in the protocol
                        self.communicator.protocol.address = settings.get('rs485_address', 254)
                else:
                    self.communicator.set_rs_mode("RS232")

                self.log_message(f"Serial settings updated: {settings}")
                if settings.get('rs485_mode', False):
                    self.log_message(f"RS485 Address: {settings.get('rs485_address', 254)}")

        except Exception as e:
            # Logs any error that occurs while updating settings
            self.log_message(f"Failed to update serial settings: {str(e)}")

    def send_command(self, command: str, response: Optional[GaugeResponse] = None):
        """
        Called by CommandFrame after a command is processed.
        Logs the command and response to the OutputFrame.
        """
        if response:
            if response.success:
                self.log_message(f">: {command}")
                self.log_message(f"<: {response.formatted_data}")
            else:
                self.log_message(f"Command failed: {response.error_message}")
        else:
            self.log_message(f"\nUnable to send command: {command}")

    def send_manual_command(self, command: str):
        """
        Allows the SerialSettingsFrame or any other part of the GUI
        to submit a manual command string for execution.
        """
        if not hasattr(self, 'cmd_frame') or not self.cmd_frame:
            self.log_message("CommandFrame is not available.")
            return
        # Delegates to cmd_frame to parse and execute the command
        self.cmd_frame.process_command(command)

    def try_all_baud_rates(self):
        """
        Called from the DebugFrame.
        Attempts all known valid baud rates until a connection test passes.
        """
        # Disconnect if currently connected
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()

        try:
            # Creates a temporary communicator for testing
            temp_communicator = GaugeCommunicator(
                port=port,
                gauge_type=self.selected_gauge.get(),
                logger=self
            )
            # Matches the user's chosen output format
            temp_communicator.set_output_format(self.output_format.get())
            tester = GaugeTester(temp_communicator, self)
            # Attempts connecting with known baud rates
            success = tester.try_all_baud_rates(port)

            if success:
                # If success, retrieves the successful baud rate
                successful_baud = temp_communicator.baudrate
                # Updates the GUI to reflect it
                self.serial_frame.baud_var.set(str(successful_baud))
                # Applies the settings to the actual communicator
                self.apply_serial_settings({
                    'baudrate': successful_baud,
                    'bytesize': 8,
                    'parity': 'N',
                    'stopbits': 1.0
                })

                # Runs a set of built-in commands as final validation
                test_results = tester.run_all_tests()
                for cmd_name, result in test_results.get("commands_tested", {}).items():
                    if result.get("success"):
                        self.log_message(f"Test {cmd_name}: {result.get('response', 'OK')}")
                    else:
                        self.log_message(f"Test {cmd_name} failed: {result.get('error', 'Unknown error')}")

                temp_communicator.disconnect()
                return True
            else:
                # If we never find a successful baud rate, closes the port
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
        """
        Shows or hides the continuous reading frame based on the gauge's capability.
        For instance, some gauges may not have continuous output.
        """
        if hasattr(self, 'continuous_frame'):
            if self.communicator and self.communicator.continuous_output:
                self.continuous_frame.pack(fill="x", padx=5, pady=5)
            else:
                self.continuous_frame.pack_forget()
                self.continuous_var.set(False)

    def send_enq(self):
        """
        Attempts sending an ENQ (0x05) to the gauge to see if it responds.
        Used mainly for debugging certain protocols.
        """
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
        """
        Logs either the current open port’s settings or the saved settings if not connected.
        """
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
        """
        A convenience method to timestamp and display a message in the output frame.
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_frame.append_log(f"[{timestamp}] {message}")

    def debug(self, message: str):
        """
        Logs a debug message with a "DEBUG:" prefix.
        """
        self.log_message(f"DEBUG: {message}")

    def info(self, message: str):
        """
        Logs an info-level message.
        """
        self.log_message(message)

    def warning(self, message: str):
        """
        Logs a warning message.
        """
        self.log_message(f"WARNING: {message}")

    def error(self, message: str):
        """
        Logs an error message.
        """
        self.log_message(f"ERROR: {message}")

    def on_closing(self):
        """
        Called right before the application window closes.
        Ensures background threads are stopped and the serial port is disconnected.
        """
        self.stop_continuous_reading()
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()
