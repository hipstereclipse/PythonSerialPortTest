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
        return PPG550Protocol(address=params.get("address", 254))
    elif gauge_type in ["PCG550", "PSG550"]:
        return PCG550Protocol(device_id=params.get("device_id", 0x02))
    elif gauge_type == "MAG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x14))
    elif gauge_type == "MPG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x04))
    elif gauge_type == "CDG045D":  # Add this condition
        return CDGProtocol()
    else:
        raise ValueError(f"Unsupported gauge type: {gauge_type}")

class IntelligentCommandSender:
    @staticmethod
    def detect_format(input_string: str) -> tuple[str, str]:
        """
        Detect the format of the input string and normalize it
        Returns: (format_type, normalized_string)
        """
        # Remove leading/trailing whitespace
        input_string = input_string.strip()

        # Binary format (e.g., "1010 0011")
        if all(c in '01 ' for c in input_string):
            return "binary", input_string.replace(" ", "")

        # Hex with '0x' prefix (e.g., "0x03 0x00 0x02")
        if input_string.lower().startswith('0x') or ' 0x' in input_string.lower():
            return "hex_prefixed", input_string.lower().replace("0x", "").replace(" ", "")

        # Hex with '\x' prefix (e.g., "\x03\x00\x02")
        if input_string.startswith('\\x') or '\\x' in input_string:
            return "hex_escaped", input_string.replace("\\x", "").replace(" ", "")

        # Space-separated decimal (e.g., "3 0 2")
        if all(part.isdigit() for part in input_string.split()):
            return "decimal", input_string

        # Comma-separated decimal (e.g., "3,0,2")
        if ',' in input_string and all(part.strip().isdigit() for part in input_string.split(',')):
            return "decimal_csv", input_string

        # Standard hex (e.g., "03 00 02")
        if all(c in '0123456789ABCDEFabcdef ' for c in input_string):
            return "hex", input_string.replace(" ", "")

        # ASCII string (e.g., "ABC")
        return "ascii", input_string

    @staticmethod
    def convert_to_bytes(format_type: str, input_string: str) -> bytes:
        """Convert the normalized string to bytes based on detected format"""
        try:
            if format_type == "binary":
                # Convert binary string to bytes
                # Pad with zeros if needed
                while len(input_string) % 8 != 0:
                    input_string = input_string + '0'
                return bytes(int(input_string[i:i + 8], 2) for i in range(0, len(input_string), 8))

            elif format_type in ["hex", "hex_prefixed", "hex_escaped"]:
                # Convert hex string to bytes
                return bytes.fromhex(input_string)

            elif format_type in ["decimal", "decimal_csv"]:
                # Convert decimal numbers to bytes
                if ',' in input_string:
                    numbers = [int(x.strip()) for x in input_string.split(',')]
                else:
                    numbers = [int(x) for x in input_string.split()]
                return bytes(numbers)

            elif format_type == "ascii":
                # Convert ASCII string to bytes
                return input_string.encode('ascii')

            else:
                raise ValueError(f"Unsupported format: {format_type}")

        except Exception as e:
            raise ValueError(f"Conversion error: {str(e)}")

    @staticmethod
    def format_output_suggestion(raw_response: bytes) -> str:
        """Suggest the best output format based on the response content"""
        if not raw_response:
            return "Hex"  # Default to Hex if no response

        # Check if response looks like ASCII text
        try:
            decoded = raw_response.decode('ascii')
            if all(32 <= ord(c) <= 126 or c in '\r\n' for c in decoded):
                return "ASCII"
        except:
            pass

        # Check if response might be binary data
        if any(b > 127 for b in raw_response):
            return "Hex"

        # If small numbers, might be better as decimal
        if all(b < 100 for b in raw_response):
            return "Decimal"

        # Default to Hex for other cases
        return "Hex"

    @staticmethod
    def send_manual_command(communicator, input_string: str, force_format: str = None) -> dict:
        """
        Intelligently send a manual command and format the response

        Args:
            communicator: GaugeCommunicator instance
            input_string: Command string in any supported format
            force_format: Optional format to force for output

        Returns:
            Dictionary containing command info and response
        """
        try:
            # Detect input format
            input_format, normalized = IntelligentCommandSender.detect_format(input_string)

            # Convert to bytes
            command_bytes = IntelligentCommandSender.convert_to_bytes(input_format, normalized)

            # Prepare result dictionary
            result = {
                "input_format_detected": input_format,
                "command_bytes": command_bytes.hex(' '),
                "command_binary": ' '.join(f'{b:08b}' for b in command_bytes),
                "command_decimal": ' '.join(str(b) for b in command_bytes),
                "rs_mode": communicator.rs_mode
            }

            # Send command if communicator is ready
            if communicator.ser and communicator.ser.is_open:
                # Clear buffers
                communicator.ser.reset_input_buffer()
                communicator.ser.reset_output_buffer()

                # Handle RS485 mode if enabled
                if communicator.rs_mode == "RS485":
                    # Configure RS485 settings if needed
                    if hasattr(communicator.ser, 'rs485_mode'):
                        communicator.ser.rs485_mode = communicator.rs485_config

                    # Set RTS high for transmit
                    communicator.ser.setRTS(communicator.rts_level_for_tx)
                    time.sleep(communicator.rts_delay_before_tx)

                    # Log RS485 state
                    communicator.logger.debug("RS485: Switched to transmit mode")

                # Send command
                communicator.logger.debug(f"Sending command: {command_bytes.hex(' ')}")
                communicator.ser.write(command_bytes)
                communicator.ser.flush()

                # Switch back to receive for RS485
                if communicator.rs_mode == "RS485":
                    # Set RTS low for receive
                    communicator.ser.setRTS(communicator.rts_level_for_rx)
                    time.sleep(communicator.rts_delay_before_rx)
                    communicator.logger.debug("RS485: Switched to receive mode")

                # Read response with proper timing
                time.sleep(communicator.rts_delay)  # Wait for line to settle
                response = communicator.read_response()

                if response:
                    # Determine best output format if not forced
                    suggested_format = force_format or IntelligentCommandSender.format_output_suggestion(response)

                    # Set communicator output format
                    communicator.set_output_format(suggested_format)

                    # Format response
                    formatted_response = communicator.format_response(response)

                    # Add response info to result
                    result.update({
                        "response_format": suggested_format,
                        "response_raw": response.hex(' '),
                        "response_formatted": formatted_response,
                        "success": True,
                        "rs485_timing": {
                            "pre_delay": communicator.rts_delay_before_tx,
                            "post_delay": communicator.rts_delay_before_rx
                        } if communicator.rs_mode == "RS485" else None
                    })
                else:
                    result.update({
                        "success": False,
                        "error": "No response received"
                    })
            else:
                result.update({
                    "success": False,
                    "error": "Port not open"
                })

            return result

        except Exception as e:
            communicator.logger.error(f"Manual command failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


class GaugeCommunicator:
    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        # ... [Keep existing initialization code] ...
        self.manual_sender = IntelligentCommandSender()

    # ... [Keep all existing methods] ...

    def send_manual_command(self, command_string: str, force_format: str = None) -> Dict[str, Any]:
        """
        Send a manual command string to the gauge.

        Args:
            command_string: Command in any supported format (hex, binary, decimal, ASCII)
            force_format: Optional format to force for the response

        Returns:
            Dictionary containing command details and response
        """
        return self.manual_sender.send_manual_command(self, command_string, force_format)

    def get_supported_formats(self) -> Dict[str, str]:
        """
        Get information about supported command formats
        """
        return {
            "hex": "Space-separated hex (e.g., '03 00 02')",
            "hex_prefixed": "Hex with 0x prefix (e.g., '0x03 0x00')",
            "hex_escaped": "Hex with \\x escape (e.g., '\\x03\\x00')",
            "decimal": "Space-separated decimal (e.g., '3 0 2')",
            "decimal_csv": "Comma-separated decimal (e.g., '3,0,2')",
            "binary": "Binary string (e.g., '0000 0011')",
            "ascii": "ASCII text (e.g., 'ABC')"
        }

class GaugeCommunicator:
    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        self.port = port
        self.gauge_type = gauge_type
        self.logger = logger or logging.getLogger(__name__)
        self.ser: Optional[serial.Serial] = None

        # Get gauge parameters and protocol
        params = GAUGE_PARAMETERS[gauge_type]
        self.protocol = get_protocol(gauge_type, params)
        self.baudrate = params["baudrate"]
        self.commands = params["commands"]
        self.output_format = "ASCII"

        # RS232/RS485 configuration
        self.rs_modes = params.get("rs_modes", ["RS232"])
        self.rs_mode = "RS232"  # Default to RS232
        self.rs485_mode = False  # For direct RTS control
        self.rts_delay = 0.002  # RTS switching delay

        # Serial settings
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        self.timeout = 2
        self.write_timeout = 2
        self.xonxoff = False
        self.rtscts = False
        self.dsrdtr = False

        # For RS485 mode
        self.rts_level_for_tx = True
        self.rts_level_for_rx = False
        self.rts_delay_before_tx = 0.002
        self.rts_delay_before_rx = 0.002

        self.manual_sender = IntelligentCommandSender()
        self.continuous_output = gauge_type == "CDG045D"  # Gauge has continuous output
        self.continuous_reading = False  # User setting for continuous reading
        self._stop_continuous = False  # Flag to stop continuous reading

    def configure_rs485(self):
        """Configure RS485 settings"""
        if self.rs_mode == "RS485":
            self.rs485_config = serial.rs485.RS485Settings(
                rts_level_for_tx=self.rts_level_for_tx,
                rts_level_for_rx=self.rts_level_for_rx,
                delay_before_tx=self.rts_delay_before_tx,
                delay_before_rx=self.rts_delay_before_rx,
                loopback=False
            )
            if self.ser:
                self.ser.rs485_mode = self.rs485_config
                # Set RTS state based on initial mode
                self.ser.setRTS(self.rts_level_for_rx)

    def set_continuous_reading(self, enabled: bool):
        """Enable or disable continuous reading mode"""
        self.continuous_reading = enabled
        self._stop_continuous = not enabled
        self.logger.debug(f"Continuous reading {'enabled' if enabled else 'disabled'}")

    def stop_continuous_reading(self):
        """Signal to stop continuous reading"""
        self._stop_continuous = True

    def read_continuous(self, callback) -> None:
        """
        Continuously read gauge responses and pass them to callback function.

        Args:
            callback: Function that takes a GaugeResponse object as parameter
        """
        self._stop_continuous = False
        self.logger.info("Starting continuous reading")

        try:
            while not self._stop_continuous and self.ser and self.ser.is_open:
                response = self.read_response()
                if response:
                    gauge_response = self.protocol.parse_response(response)
                    if gauge_response.success:
                        callback(gauge_response)
                time.sleep(0.020)  # Match CDG output rate

        except Exception as e:
            self.logger.error(f"Continuous reading error: {str(e)}")
            callback(GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=f"Continuous reading error: {str(e)}"
            ))

        self.logger.info("Stopped continuous reading")

    def set_rs_mode(self, mode: str):
        """Set RS232 or RS485 mode with validation"""
        if mode not in self.rs_modes:
            self.logger.error(f"Invalid RS mode: {mode}. Must be one of {self.rs_modes}")
            return False

        try:
            self.rs_mode = mode
            self.rs485_mode = (mode == "RS485")

            if self.ser and self.ser.is_open:
                if mode == "RS485":
                    self.ser.setDTR(True)
                    self.ser.setRTS(False)  # Start in receive mode
                else:
                    # Reset to RS232 mode
                    self.ser.setDTR(True)
                    self.ser.setRTS(True)

            self.logger.debug(f"RS mode set to: {mode}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to set RS mode: {str(e)}")
            return False

    def set_rs485_timing(self, pre_delay: float = 0.002, post_delay: float = 0.002):
        """Set RS485 timing parameters"""
        self.rts_delay_before_tx = pre_delay
        self.rts_delay_before_rx = post_delay
        if self.rs_mode == "RS485":
            self.configure_rs485()

    def set_rs485_mode(self, enabled: bool):
        """Enable or disable RS485 mode"""
        self.rs485_mode = enabled
        if self.ser and self.ser.is_open:
            if enabled:
                self.ser.setRTS(False)  # Start in receive mode
            else:
                self.ser.setRTS(True)  # Normal RTS for RS232
        self.logger.debug(f"RS485 mode: {'enabled' if enabled else 'disabled'}")

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
        """Establish connection with proper RS232/RS485 handling"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=self.write_timeout,
                xonxoff=self.xonxoff,
                rtscts=self.rtscts,
                dsrdtr=self.dsrdtr
            )

            # Configure port based on mode
            if self.rs485_mode:
                self.ser.setDTR(True)
                self.ser.setRTS(False)  # Start in receive mode
            else:
                self.ser.setDTR(True)
                self.ser.setRTS(True)  # Normal RS232 mode

            time.sleep(0.2)  # Wait for port to stabilize

            # Test connection
            success = self.test_connection()
            if not success:
                self.disconnect()

            return success

        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            if self.ser and self.ser.is_open:
                self.ser.close()
            return False

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        """Send command with proper RS232/RS485 handling"""
        if not self.ser or not self.ser.is_open:
            return GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message="Not connected"
            )

        try:
            # Create command
            cmd_bytes = self.protocol.create_command(command)

            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Handle RS485 if enabled
            if self.rs485_mode:
                self.ser.setRTS(True)  # Switch to transmit
                time.sleep(self.rts_delay)

            # Send command
            formatted_cmd = self.format_command(cmd_bytes)
            self.logger.debug(f"Sending command: {formatted_cmd}")
            self.ser.write(cmd_bytes)
            self.ser.flush()

            # Switch back to receive for RS485
            if self.rs485_mode:
                self.ser.setRTS(False)
                time.sleep(self.rts_delay)

            # Read response
            time.sleep(0.1)  # Short delay for response
            response = self.read_response()

            if response:
                return self.protocol.parse_response(response)
            else:
                return GaugeResponse(
                    raw_data=b"",
                    formatted_data="",
                    success=False,
                    error_message="No response"
                )

        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            return GaugeResponse(
                raw_data=b"",
                formatted_data="",
                success=False,
                error_message=str(e)
            )

    def test_connection(self) -> bool:
        """Test connection with proper protocol handling"""
        if not self.ser or not self.ser.is_open:
            return False

        test_commands = self.protocol.test_commands()
        for cmd_bytes in test_commands:
            try:
                formatted_cmd = self.format_command(cmd_bytes)
                self.logger.debug(f"Testing connection with: {formatted_cmd}")

                if self.rs485_mode:
                    # Switch to transmit mode
                    self.ser.setRTS(True)
                    time.sleep(self.rs485_rts_delay)

                self.ser.write(cmd_bytes)
                self.ser.flush()

                if self.rs485_mode:
                    # Switch to receive mode
                    self.ser.setRTS(False)
                    time.sleep(self.rs485_rts_delay)

                # Wait for response
                time.sleep(0.2)
                if self.ser.in_waiting:
                    response = self.read_response()
                    if response:
                        formatted_response = self.format_response(response)
                        self.logger.debug(f"Got response: {formatted_response}")
                        return True

                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Test command failed: {str(e)}")
                continue

        self.logger.debug("No response to test commands")
        return False

    def get_port_info(self) -> Dict[str, Any]:
        """Get current port configuration"""
        if not self.ser:
            return {}

        return {
            'port': self.ser.port,
            'baudrate': self.ser.baudrate,
            'bytesize': self.ser.bytesize,
            'parity': self.ser.parity,
            'stopbits': self.ser.stopbits,
            'timeout': self.ser.timeout,
            'write_timeout': self.ser.write_timeout,
            'rs_mode': self.rs_mode,
            'xonxoff': self.ser.xonxoff,
            'rtscts': self.ser.rtscts,
            'dsrdtr': self.ser.dsrdtr,
            'rts_level': self.ser.rts if self.ser.is_open else None,
            'dtr_level': self.ser.dtr if self.ser.is_open else None
        }

    def read_response(self) -> Optional[bytes]:
        """Read response from serial port with proper timeout and gauge-specific handling."""
        if not self.ser:
            return None

        try:
            if self.continuous_output:  # Special handling for CDG gauges
                # CDG sends 9-byte frames continuously
                response = bytearray()
                start_time = time.time()

                # Look for frame start (0x07)
                while (time.time() - start_time) < self.timeout:
                    if self.ser.in_waiting >= 1:
                        byte = self.ser.read(1)
                        if byte[0] == 0x07:  # Start of frame found
                            response.extend(byte)
                            # Read remaining 8 bytes of the frame
                            remaining = self.ser.read(8)
                            if len(remaining) == 8:
                                response.extend(remaining)
                                self.logger.debug(f"CDG frame received: {' '.join(f'{b:02x}' for b in response)}")
                                return bytes(response)
                    time.sleep(0.001)  # Short sleep to prevent CPU overload

                self.logger.debug("Timeout waiting for CDG frame start")
                return None

            # For PPG550, read until terminator
            elif isinstance(self.protocol, PPG550Protocol):
                while (time.time() - start_time) < self.timeout:
                    if self.ser.in_waiting:
                        byte = self.ser.read(1)
                        if byte[0] >= 32 or byte[0] in [10, 13]:  # Printable or newline
                            response += byte
                        if response.endswith(b';FF'):
                            return response
                    else:
                        if response:  # Have data but no more coming
                            return response
                        time.sleep(0.01)

            else:
                start_time = time.time()
                response = b''

                while (time.time() - start_time) < self.timeout:
                    if self.ser.in_waiting:
                        byte = self.ser.read(1)
                        response += byte
                    else:
                        if response:  # Have data but no more coming
                            return response
                        time.sleep(0.01)

            return response if response else None

        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None

    def apply_settings(self, settings: dict):
        """Apply new settings without breaking existing mode"""
        # Update RS mode first
        if settings.get('rs485_mode', False):
            self.set_rs_mode("RS485")
        else:
            self.set_rs_mode("RS232")

        # Update protocol address if needed
        if isinstance(self.protocol, PPG550Protocol):
            self.protocol.address = settings.get('rs485_address', 254)

        # Update other serial settings
        if self.ser and self.ser.is_open:
            self.ser.baudrate = settings.get('baudrate', self.baudrate)
            self.ser.bytesize = settings.get('bytesize', self.bytesize)
            self.ser.parity = settings.get('parity', self.parity)
            self.ser.stopbits = settings.get('stopbits', self.stopbits)

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

