import tkinter as tk
from tkinter import ttk
import serial
import serial.tools.list_ports
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import time

from ..config import GAUGE_PARAMETERS, OUTPUT_FORMATS, setup_logging
from ..models import GaugeCommand
from ..communicator import GaugeCommunicator
from .widgets import (
    CommandFrame,
    DebugFrame,
    OutputFrame,
    SerialSettingsFrame
)
from serial_gauge.protocols import *

class GaugeApp:
    def __init__(self, root: tk.Tk):
        # Initialize main window settings
        self.root = root
        self.root.title("Gauge Communication Interface")
        self.root.geometry("800x600")

        # Initialize variables
        self.selected_port = tk.StringVar()
        self.selected_gauge = tk.StringVar(value="PCG550")
        self.output_format = tk.StringVar(value="ASCII")

        # Initialize default serial settings
        self.current_serial_settings = {
            'baudrate': 9600,
            'bytesize': 8,
            'parity': 'N',
            'stopbits': 1.0
        }

        # Initialize communicator as None
        self.communicator: Optional[GaugeCommunicator] = None

        # Create GUI elements
        self.create_gui()

        # Set up traces after GUI elements exist
        self.output_format.trace('w', self.on_output_format_change)

        # Refresh ports initially
        self.refresh_ports()

        self.selected_gauge.trace('w', self.on_gauge_change)

    def on_gauge_change(self, *args):
        """Handle gauge type change"""
        gauge_type = self.selected_gauge.get()

        if gauge_type in GAUGE_PARAMETERS:
            # Get default settings for selected gauge
            params = GAUGE_PARAMETERS[gauge_type]

            # Update serial settings in UI
            self.serial_frame.baud_var.set(str(params["baudrate"]))

            # Apply the new settings
            self.apply_serial_settings({
                'baudrate': params["baudrate"],
                'bytesize': 8,
                'parity': 'N',
                'stopbits': 1.0
            })

            # Update GUI and log the change
            self.log_message(f"\nChanged to {gauge_type}")
            self.log_message("Updated serial settings to match gauge defaults:")
            self.log_message(f"Baudrate: {params['baudrate']}")

            # Log the appropriate identifier based on gauge type
            if gauge_type == "PPG550":
                # Use 'address' for PPG550 instead of 'device_id'
                self.log_message(f"Address: {params.get('address', 'N/A')}")
            elif gauge_type in ["PCG550", "MAG500", "MPG500"]:
                # Use 'device_id' for other gauges
                self.log_message(f"Device ID: {params.get('device_id', 'N/A'):#x}")
            else:
                self.log_message("Unknown gauge type selected.")

            # Show updated settings in the UI
            self.show_port_settings()
        else:
            self.log_message("Selected gauge type not found in GAUGE_PARAMETERS.")
    def create_gui(self):
        """Create all GUI elements."""
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        # Port selection
        ttk.Label(conn_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_menu = ttk.OptionMenu(conn_frame, self.selected_port, "")
        self.port_menu.pack(side=tk.LEFT, padx=5)

        # Refresh ports button
        ttk.Button(
            conn_frame,
            text="Refresh",
            command=self.refresh_ports
        ).pack(side=tk.LEFT, padx=5)

        # Gauge selection
        ttk.Label(conn_frame, text="Gauge:").pack(side=tk.LEFT, padx=5)
        self.gauge_menu = ttk.OptionMenu(  # Now assigned to self.gauge_menu
            conn_frame,
            self.selected_gauge,
            "PCG550",
            *GAUGE_PARAMETERS.keys()
        )
        self.gauge_menu.pack(side=tk.LEFT, padx=5)

        # Connect button
        self.connect_button = ttk.Button(
            conn_frame,
            text="Connect",
            command=self.connect_disconnect
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)

        # Add Serial Settings Frame
        self.serial_frame = SerialSettingsFrame(
            self.root,
            self.apply_serial_settings,
            self.send_manual_command
        )
        self.serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # Command interface
        self.cmd_frame = CommandFrame(
            parent=self.root,
            gauge_var=self.selected_gauge,
            command_callback=self.send_command
        )
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)

        # Debug frame
        self.debug_frame = DebugFrame(
            self.root,
            self.try_all_baud_rates,
            self.send_enq,
            self.show_port_settings
        )
        self.debug_frame.pack(fill=tk.X, padx=5, pady=5)

        # Output frame - must be created last
        self.output_frame = OutputFrame(
            self.root,
            self.output_format
        )
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh_ports(self):
        """Refresh available COM ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        for port in ports:
            menu.add_command(label=port,
                             command=lambda p=port: self.selected_port.set(p))
        if ports:
            self.selected_port.set(ports[0])
        else:
            self.selected_port.set("")

    def connect_disconnect(self):
        """Handle connect/disconnect button."""
        if self.communicator is None:
            try:
                self.communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )

                # Apply current settings before connecting
                if self.communicator.ser:
                    self.communicator.ser.baudrate = self.current_serial_settings['baudrate']
                    self.communicator.ser.bytesize = self.current_serial_settings['bytesize']
                    self.communicator.ser.parity = self.current_serial_settings['parity']
                    self.communicator.ser.stopbits = self.current_serial_settings['stopbits']

                if self.communicator.connect():
                    self.connect_button.config(text="Disconnect")
                    self.log_message("Connected successfully")
                    self.cmd_frame.set_enabled(True)
                    self.debug_frame.set_enabled(True)

                    # Disable gauge and COM port selection after successful connection
                    self.gauge_menu.configure(state="disabled")
                    self.port_menu.configure(state="disabled")
                else:
                    self.communicator = None
                    self.log_message("Connection failed")
            except Exception as e:
                self.log_message(f"Connection error: {str(e)}")
                self.communicator = None
        else:
            try:
                self.communicator.disconnect()
                self.communicator = None
                self.connect_button.config(text="Connect")
                self.log_message("Disconnected")
                self.cmd_frame.set_enabled(False)
                self.debug_frame.set_enabled(False)

                # Re-enable gauge and COM port selection on disconnect
                self.gauge_menu.configure(state="normal")
                self.port_menu.configure(state="normal")
            except Exception as e:
                self.log_message(f"Disconnection error: {str(e)}")

    def on_output_format_change(self, *args):
        """Handle output format changes"""
        new_format = self.output_format.get()
        if self.communicator:
            self.communicator.set_output_format(new_format)
        self.log_message(f"Output format changed to: {new_format}")

    def apply_serial_settings(self, settings: dict):
        """Apply new serial port settings by reinitializing the communicator."""
        # Save the new settings
        self.current_serial_settings.update(settings)

        if self.communicator:
            try:
                # Disconnect and delete the old communicator instance
                if self.communicator.ser and self.communicator.ser.is_open:
                    self.communicator.ser.close()

                # Create a new communicator instance with updated settings
                self.communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )

                # Apply current settings directly to the new communicator
                if self.communicator.ser:
                    self.communicator.ser.baudrate = self.current_serial_settings['baudrate']
                    self.communicator.ser.bytesize = self.current_serial_settings['bytesize']
                    self.communicator.ser.parity = self.current_serial_settings['parity']
                    self.communicator.ser.stopbits = self.current_serial_settings['stopbits']

                # Reopen the connection
                if self.communicator.connect():
                    self.log_message(f"Serial settings updated and connection reestablished: {settings}")
                else:
                    self.log_message("Failed to reconnect with new settings")

            except Exception as e:
                self.log_message(f"Failed to update serial settings: {str(e)}")
        else:
            # Save settings for future connections
            self.log_message(f"Settings saved for the next connection: {settings}")

    def send_manual_command(self, command: str):
        """Send a manual command to the device."""
        # If not connected, attempt to open a temporary connection
        if not self.communicator or not self.communicator.ser.is_open:
            try:
                temp_ser = serial.Serial(
                    port=self.selected_port.get(),
                    baudrate=self.current_serial_settings['baudrate'],
                    bytesize=self.current_serial_settings['bytesize'],
                    parity=self.current_serial_settings['parity'],
                    stopbits=self.current_serial_settings['stopbits'],
                    timeout=1
                )
                # Create temporary communicator for formatting
                temp_communicator = GaugeCommunicator(
                    port=self.selected_port.get(),
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )
                temp_communicator.ser = temp_ser
                temp_communicator.set_output_format(self.output_format.get())
            except Exception as e:
                self.log_message(f"Could not open port: {str(e)}")
                return
        else:
            temp_ser = self.communicator.ser
            temp_communicator = self.communicator

        try:
            # Strip whitespace and remove any 'b' prefix if present
            command = command.strip()
            if command.startswith("b'") or command.startswith('b"'):
                command = command[2:-1]

            # Convert input to bytes based on simple hex check
            if command.startswith('0x') or all(c in '0123456789ABCDEFabcdef ' for c in command):
                cmd_bytes = bytes.fromhex(command.replace('0x', '').replace(' ', ''))
            else:
                cmd_bytes = command.encode('ascii')

            # Log formatted command using existing formatter
            formatted_cmd = temp_communicator.format_command(cmd_bytes)
            self.log_message(f"> {formatted_cmd}")

            # Send command
            temp_ser.write(cmd_bytes)
            temp_ser.flush()

            # Read response with a short delay
            time.sleep(0.1)
            response = temp_ser.read(temp_ser.in_waiting or 64)

            if response:
                # Format response using existing formatter
                formatted_response = temp_communicator.format_response(response)
                self.log_message(f"< {formatted_response}")
            else:
                self.log_message("No response received")

        except Exception as e:
            self.log_message(f"Command error: {str(e)}")

        finally:
            # Close temp connection if it was created
            if temp_ser and (not self.communicator or temp_ser != self.communicator.ser):
                temp_ser.close()
                self.log_message("Temporary connection closed.")
    def send_command(self, command_name: str, command_type: str, parameters: Optional[Dict[str, Any]] = None):
        """Send command through communicator"""
        if not self.communicator:
            self.log_message("Not connected")
            return

        try:
            command = GaugeCommand(
                name=command_name,
                command_type=command_type,
                parameters=parameters
            )

            # Create and log command first
            if isinstance(self.communicator.protocol, PPG550Protocol):
                cmd_str = self.communicator.protocol.create_command(command).decode('ascii', errors='replace')
                self.log_message(f"> {cmd_str}")
            else:
                cmd_bytes = self.communicator.protocol.create_command(command)
                self.log_message(f"> {' '.join(f'{b:02x}' for b in cmd_bytes)}")

            # Send command and get response
            response = self.communicator.send_command(command)

            # Log response
            if isinstance(response, str):
                self.log_message(f"< ({self.output_format.get()}): {response}")
            else:
                # Handle GaugeResponse objects
                if response.success:
                    self.log_message(f"< ({self.output_format.get()}): {response.formatted_data}")
                else:
                    self.log_message(f"Command failed: {response.error_message}")

        except Exception as e:
            self.log_message(f"Command error: {str(e)}")

    def try_all_baud_rates(self):
        """Test connection with different baud rates"""
        if self.communicator:
            self.communicator.disconnect()
            self.communicator = None

        self.log_message("\n=== Testing Baud Rates ===")
        port = self.selected_port.get()

        for baud in [57600, 38400, 19200, 9600]:  # Try factory default first
            self.log_message(f"\nTrying baud rate: {baud}")
            try:
                # Create temporary communicator for this baud rate
                temp_communicator = GaugeCommunicator(
                    port=port,
                    gauge_type=self.selected_gauge.get(),
                    logger=self
                )

                # Override the default baud rate
                temp_communicator.baudrate = baud

                # Try to connect and read product name
                if temp_communicator.connect():
                    # Try to read something simple like the product name
                    cmd = GaugeCommand(
                        name="product_name",
                        command_type="?",
                        parameters={"pid": 208, "cmd": 1}
                    )

                    response = temp_communicator.send_command(cmd)
                    if response.success:
                        self.log_message(f"Successfully connected at {baud} baud!")
                        self.log_message(f"Product name: {response.formatted_data}")

                        # Update the UI settings
                        self.serial_frame.baud_var.set(str(baud))
                        self.apply_serial_settings({
                            'baudrate': baud,
                            'bytesize': 8,
                            'parity': 'N',
                            'stopbits': 1.0
                        })

                        temp_communicator.disconnect()
                        return True

                if temp_communicator:
                    temp_communicator.disconnect()

            except Exception as e:
                self.log_message(f"Failed at {baud} baud: {str(e)}")

            time.sleep(0.5)  # Wait between attempts

        self.log_message("\nFailed to connect at any baud rate")
        return False
    def send_enq(self):
        """Send ENQ character for testing"""
        port = self.selected_port.get()
        if not port:
            self.log_message("No port selected")
            return

        try:
            ser = None
            if self.communicator and self.communicator.ser and self.communicator.ser.is_open:
                ser = self.communicator.ser
            else:
                self.log_message("Creating temporary connection for ENQ test")
                ser = serial.Serial(
                    port=port,
                    baudrate=int(self.serial_frame.baud_var.get()),
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                    write_timeout=1
                )

            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            self.log_message("> Sending ENQ (0x05)")
            ser.write(b'\x05')
            ser.flush()
            time.sleep(0.1)

            if ser.in_waiting:
                response = ser.read(ser.in_waiting)
                self.log_message(f"< ENQ Response: {' '.join(f'{b:02x}' for b in response)}")
                if response:
                    try:
                        ascii_resp = response.decode('ascii', errors='replace')
                        self.log_message(f"< ASCII: {ascii_resp}")
                    except:
                        pass
            else:
                self.log_message("< No response to ENQ")

            # Close temporary connection if we created one
            if ser and (not self.communicator or ser != self.communicator.ser):
                ser.close()

        except Exception as e:
            self.log_message(f"ENQ test error: {str(e)}")

    def show_port_settings(self):
        """Display current serial port settings."""
        port = self.selected_port.get()
        if not port:
            self.log_message("No port selected")
            return

        try:
            # If we have an active communicator, use its settings
            if self.communicator and self.communicator.ser:
                ser = self.communicator.ser
            else:
                # Create temporary connection with current saved settings
                ser = serial.Serial(
                    port=port,
                    baudrate=self.current_serial_settings['baudrate'],
                    bytesize=self.current_serial_settings['bytesize'],
                    parity=self.current_serial_settings['parity'],
                    stopbits=self.current_serial_settings['stopbits']
                )

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

            # Only close if it's our temporary connection
            if not (self.communicator and self.communicator.ser):
                ser.close()

        except Exception as e:
            self.log_message(f"Error getting port settings: {str(e)}")

    def log_message(self, message: str):
        """Add message to output log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.output_frame.append_log(f"[{timestamp}] {message}")

    # Make GaugeApp compatible with Python's logging system
    def debug(self, message: str):
        """Handle debug messages from logger"""
        self.log_message(f"DEBUG: {message}")

    def info(self, message: str):
        """Handle info messages from logger"""
        self.log_message(message)

    def warning(self, message: str):
        """Handle warning messages from logger"""
        self.log_message(f"WARNING: {message}")

    def error(self, message: str):
        """Handle error messages from logger"""
        self.log_message(f"ERROR: {message}")

    def on_closing(self):
        """Handle application shutdown"""
        if self.communicator:
            self.communicator.disconnect()
        self.root.destroy()