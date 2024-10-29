import serial
import serial.tools.list_ports
from typing import Optional, List, Tuple
import time
import logging
from serial_gauge.protocols import *
from serial_gauge.models import *
from serial_gauge.config import *
import binascii

def get_protocol(gauge_type: str, params: dict) -> GaugeProtocol:
    """Factory function to get the appropriate protocol handler based on gauge type."""
    if gauge_type == "PPG550":
        return PPG550Protocol(address=params.get("address", 254))  # Use address for PPG550
    elif gauge_type in ["PCG550", "PSG550"]:
        return PCG550Protocol(device_id=params.get("device_id", 0x02))  # Use device_id for PCG550/PSG550
    elif gauge_type == "MAG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x14))  # Use specific device_id for MAG500
    elif gauge_type == "MPG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x04))  # Use specific device_id for MPG500
    else:
        raise ValueError(f"Unsupported gauge type: {gauge_type}")  # Raise error if gauge type is unsupported

class GaugeCommunicator:
    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        self.port = port  # Port for serial communication
        self.gauge_type = gauge_type  # Type of gauge
        self.logger = logger or logging.getLogger(__name__)  # Initialize logger
        self.ser: Optional[serial.Serial] = None  # Serial connection instance

        params = GAUGE_PARAMETERS[gauge_type]  # Fetch gauge-specific parameters
        self.protocol = get_protocol(gauge_type, params)  # Set protocol based on gauge type and parameters

        self.baudrate = params["baudrate"]  # Baud rate for serial communication
        self.commands = params["commands"]  # Commands dictionary specific to the gauge type
        self.output_format = "ASCII"  # Default format for encoding/decoding

        # RS mode configuration
        self.rs_modes = params.get("rs_modes", ["RS232"])
        self.rs_mode = "RS232"  # Default to RS232
        self.rs485_mode = False
        self.rs485_address = params.get("address", 254)  # Default to global address

        # Serial port configuration defaults
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        self.timeout = 2  # Response timeout in seconds
        self.write_timeout = 2  # Write timeout in seconds

    def set_rs_mode(self, mode: str):
        """Set RS232 or RS485 mode"""
        if mode not in self.rs_modes:
            self.logger.error(f"Invalid RS mode: {mode}. Must be one of {self.rs_modes}")
            return
        self.rs_mode = mode
        self.logger.debug(f"RS mode set to: {mode}")

    def set_rs485_mode(self, enabled: bool, address: int = 254):
        """Configure RS485 mode settings"""
        self.rs485_mode = enabled
        self.rs485_address = address
        if hasattr(self.protocol, 'address'):
            self.protocol.address = address
        self.logger.debug(f"RS485 mode: {'enabled' if enabled else 'disabled'}, Address: {address}")

    def apply_serial_settings(self, settings: dict):
        """Apply new serial port settings."""
        if 'rs485_enabled' in settings:
            self.set_rs485_mode(settings['rs485_enabled'], settings.get('rs485_address', 254))

    def set_output_format(self, format_type: str):
        """Set the output format type and update protocol if needed"""
        self.output_format = format_type
        self.logger.debug(f"Output format set to: {format_type}")

    def format_command(self, command_bytes: bytes) -> str:
        """Format command according to selected output format"""
        if not command_bytes:
            return "No command"

        try:
            if self.output_format == "Hex":
                return ' '.join(f'{byte:02x}' for byte in command_bytes)
            elif self.output_format == "Binary":
                return ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in command_bytes)
            elif self.output_format == "ASCII":
                return command_bytes.decode('ascii', errors='replace')
            elif self.output_format == "UTF-8":
                return command_bytes.decode('utf-8', errors='replace')
            elif self.output_format == "Decimal":
                return ' '.join(str(byte) for byte in command_bytes)
            else:  # Raw Bytes
                return str(command_bytes)
        except Exception as e:
            return f"Error formatting command: {str(e)}"

    def format_response(self, response: bytes) -> str:
        """Format response according to selected output format"""
        if not response:
            return "No response"

        try:
            if self.output_format == "Hex":
                return ' '.join(f'{byte:02x}' for byte in response)
            elif self.output_format == "Binary":
                return ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in response)
            elif self.output_format == "ASCII":
                return response.decode('ascii', errors='replace')
            elif self.output_format == "UTF-8":
                return response.decode('utf-8', errors='replace')
            elif self.output_format == "Decimal":
                return ' '.join(str(byte) for byte in response)
            else:  # Raw Bytes
                return str(response)
        except Exception as e:
            return f"Error formatting response: {str(e)}"

    def connect(self) -> bool:
        """Establish connection to the gauge."""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=self.write_timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )

            # Configure port based on RS485 mode
            self.ser.setDTR(True)
            if not self.rs485_mode:
                self.ser.setRTS(True)  # Keep RTS high for RS232
            else:
                self.ser.setRTS(False)  # Start with RTS low for RS485
                self.logger.debug(f"RS485 mode enabled with address: {self.rs485_address}")

            time.sleep(0.2)  # Allow port settings to settle

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            test_commands = self.protocol.test_commands()
            for cmd_bytes in test_commands:
                try:
                    if self.gauge_type == "PPG550":
                        self.logger.debug(f"Testing connection with: {cmd_bytes.decode('ascii')}")
                    else:
                        self.logger.debug(f"Testing connection with: {' '.join(f'{b:02x}' for b in cmd_bytes)}")

                    # For PPG550, add carriage return and line feed if not present
                    if self.gauge_type == "PPG550" and not cmd_bytes.endswith(b'\r\n'):
                        cmd_bytes += b'\r\n'

                    # Handle RS485 transmission
                    if self.rs485_mode:
                        self.ser.setRTS(True)  # Enable transmitter
                        time.sleep(0.002)  # 2ms delay before transmission

                    self.ser.write(cmd_bytes)
                    self.ser.flush()

                    if self.rs485_mode:
                        time.sleep(0.002)  # 2ms delay after transmission
                        self.ser.setRTS(False)  # Switch to receive mode

                    time.sleep(0.1)  # Wait for response

                    if self.ser.in_waiting:
                        response = self.read_response()
                        if response:
                            if self.gauge_type == "PPG550":
                                try:
                                    printable_response = bytes(b for b in response if b >= 32 or b in [10, 13])
                                    self.logger.debug(
                                        f"Got response: {printable_response.decode('ascii', errors='ignore')}")
                                except Exception as e:
                                    self.logger.debug(f"Got raw response: {' '.join(f'{b:02x}' for b in response)}")
                            else:
                                self.logger.debug(f"Got response: {' '.join(f'{b:02x}' for b in response)}")
                            return True

                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    time.sleep(0.2)

                except Exception as e:
                    self.logger.error(f"Command failed: {str(e)}")
                    continue

            self.logger.debug("No response to test commands")
            return False

        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            if self.ser and self.ser.is_open:
                self.ser.close()
            return False

    def send_quick_command(self, command_name: str, command_type: str,
                           parameters: Optional[Dict[str, Any]] = None) -> str:
        """Send a predefined quick command"""
        try:
            command = GaugeCommand(
                name=command_name,
                command_type=command_type,
                parameters=parameters
            )

            response = self.send_command(command)
            return response

        except Exception as e:
            self.logger.error(f"Quick command failed: {str(e)}")
            return f"Error: {str(e)}"

    def send_command(self, command: GaugeCommand) -> str:
        """Send command and return formatted response"""
        if not self.ser or not self.ser.is_open:
            return GaugeResponse(
                raw_data=None,
                formatted_data="Not connected",
                success=False,
                error_message="Not connected"
            )

        try:
            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Create command
            cmd_bytes = self.protocol.create_command(command)

            # Handle RS485 transmission
            if self.rs485_mode:
                self.ser.setRTS(True)  # Enable transmitter
                time.sleep(0.002)  # 2ms delay before transmission

            # Send command
            self.logger.debug(f"> {cmd_bytes.decode('ascii', errors='replace')}")
            self.ser.write(cmd_bytes)
            self.ser.flush()

            if self.rs485_mode:
                time.sleep(0.002)  # 2ms delay after transmission
                self.ser.setRTS(False)  # Switch to receive mode

            # Wait for response
            time.sleep(0.1)
            response_bytes = self.read_response()

            if response_bytes:
                # Parse response using protocol handler
                response = self.protocol.parse_response(response_bytes)
                if response.success:
                    self.logger.debug(f"< {response.formatted_data}")
                else:
                    self.logger.error(f"Response error: {response.error_message}")
                return response.formatted_data
            else:
                return "No response"

        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            return f"Error: {str(e)}"


    def read_response(self) -> Optional[bytes]:
        """Read response from serial port with proper timeout handling."""
        if not self.ser:
            return None

        try:
            response = b''
            start_time = time.time()

            # Wait for initial data
            while (time.time() - start_time) < self.timeout:
                if self.ser.in_waiting:
                    break
                time.sleep(0.01)

            if not self.ser.in_waiting:
                return None

            # For PPG550, read until terminator or timeout
            if self.gauge_type == "PPG550":
                while (time.time() - start_time) < self.timeout:
                    if self.ser.in_waiting:
                        chunk = self.ser.read(self.ser.in_waiting)
                        response += chunk

                        # Check for termination sequences
                        if b';FF' in response:
                            break

                    elif response:  # If we have data but nothing more is coming
                        break

                    time.sleep(0.01)

                return response

            else:
                # Original header-based reading for other gauges
                header = self.ser.read(4)
                if len(header) < 4:
                    return None

                msg_length = header[3]
                remaining_length = msg_length + 2  # Add 2 for CRC
                remaining = self.ser.read(remaining_length)

                return header + remaining

        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None
    def disconnect(self):
        """Safely disconnect from the gauge."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.logger.info("Disconnected from gauge")
                return True
        except Exception as e:
            self.logger.error(f"Error disconnecting: {str(e)}")
            return False

