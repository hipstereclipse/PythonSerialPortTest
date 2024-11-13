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
    if gauge_type in ["PPG550", "PPG570"]:
        return PPGProtocol(
            address=params.get("address", 254),
            gauge_type=gauge_type
        )
    elif gauge_type in ["PCG550", "PSG550"]:
        return PCGProtocol(device_id=params.get("device_id", 0x02))
    elif gauge_type == "MAG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x14))
    elif gauge_type == "MPG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x04))
    elif gauge_type == "CDG045D":
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
        """Send manual command and format according to specified format"""
        try:
            # Detect input format and convert to bytes
            input_format, normalized = IntelligentCommandSender.detect_format(input_string)
            command_bytes = IntelligentCommandSender.convert_to_bytes(input_format, normalized)

            result = {
                "input_format_detected": input_format,
                "success": False,
                "error": None,
                "response_formatted": None,
                "response_raw": None,
                "rs_mode": communicator.rs_mode
            }

            if communicator.ser and communicator.ser.is_open:
                communicator.ser.reset_input_buffer()
                communicator.ser.reset_output_buffer()

                # Handle RS485 mode
                if communicator.rs_mode == "RS485":
                    if hasattr(communicator.ser, 'rs485_mode'):
                        communicator.ser.rs485_mode = communicator.rs485_config
                    communicator.ser.setRTS(communicator.rts_level_for_tx)
                    time.sleep(communicator.rts_delay_before_tx)

                communicator.ser.write(command_bytes)
                communicator.ser.flush()

                if communicator.rs_mode == "RS485":
                    communicator.ser.setRTS(communicator.rts_level_for_rx)
                    time.sleep(communicator.rts_delay_before_rx)

                time.sleep(communicator.rts_delay)
                response = communicator.read_response()

                if response:
                    # Format response according to specified format
                    suggested_format = force_format or communicator.output_format
                    communicator.set_output_format(suggested_format)

                    result.update({
                        "success": True,
                        "response_raw": response.hex(),
                        "response_formatted": communicator.format_response(response)
                    })
                else:
                    result.update({
                        "error": "No response received"
                    })
            else:
                result.update({
                    "error": "Port not open"
                })

            return result

        except Exception as e:
            communicator.logger.error(f"Manual command failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response_formatted": None,
                "response_raw": None
            }

class ResponseHandler:
    """Handles formatting and processing of all gauge responses"""

    def __init__(self, output_format: str = "ASCII"):
        self.output_format = output_format

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

    def suggest_format(self, raw_response: bytes) -> str:
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

    def set_output_format(self, format_type: str):
        """Update the output format"""
        self.output_format = format_type

    def process_cdg_frame(self, response: bytes) -> dict:
        """Process CDG gauge specific 9-byte frame format"""
        if len(response) != 9:
            return {"error": "Invalid frame length"}

        try:
            return {
                "start_byte": response[0],
                "page_no": response[1],
                "status": {
                    "unit": (response[2] >> 4) & 0x03,
                    "heating": bool(response[2] & 0x80),
                    "temp_ok": bool(response[2] & 0x40),
                    "emission": bool(response[2] & 0x20)
                },
                "error": response[3],
                "pressure": self._calculate_cdg_pressure(response[4], response[5]),
                "read_value": response[6],
                "sensor_type": response[7],
                "checksum": response[8],
                "checksum_valid": self._verify_cdg_checksum(response)
            }
        except Exception as e:
            return {"error": f"Frame processing error: {str(e)}"}

    def _calculate_cdg_pressure(self, high_byte: int, low_byte: int) -> float:
        """Calculate pressure value from CDG gauge bytes"""
        pressure_value = (high_byte << 8) | low_byte
        if pressure_value & 0x8000:  # Handle negative values
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        return pressure_value / 16384.0  # Scale factor for CDG

    def _verify_cdg_checksum(self, frame: bytes) -> bool:
        """Verify CDG frame checksum"""
        if len(frame) != 9:
            return False
        calc_checksum = sum(frame[1:8]) & 0xFF
        return calc_checksum == frame[8]

    def parse_ppg_response(self, response: bytes) -> dict:
        """Parse PPG gauge ASCII response format"""
        try:
            decoded = response.decode('ascii').strip()
            if not decoded.startswith('@') or not decoded.endswith(';FF'):
                return {"error": "Invalid response format"}

            # Remove framing
            if decoded.startswith('@ACK'):
                data = decoded[4:-3]  # Remove @ACK and ;FF
            elif decoded.startswith('@NAK'):
                return {"error": f"Command failed: {decoded[4:-3]}"}
            else:
                data = decoded[1:-3]  # Remove @ and ;FF

            return {
                "data": data,
                "values": data.split(',') if ',' in data else [data]
            }
        except Exception as e:
            return {"error": f"Parse error: {str(e)}"}

    def create_gauge_response(self, raw_data: bytes, formatted_data: str = "",
                              success: bool = True, error_message: str = None) -> GaugeResponse:
        """Create a standardized GaugeResponse object"""
        return GaugeResponse(
            raw_data=raw_data,
            formatted_data=formatted_data or self.format_response(raw_data),
            success=success,
            error_message=error_message
        )

class GaugeCommunicator:
    """Main communicator class using IntelligentCommandSender for all communications and ResponseHandler for all responses"""

    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        # Basic setup
        self.port = port
        self.gauge_type = gauge_type
        self.logger = logger or logging.getLogger(__name__)
        self.ser: Optional[serial.Serial] = None

        # Get gauge config and initialize protocol
        self.params = GAUGE_PARAMETERS[gauge_type]
        self.protocol = get_protocol(gauge_type, self.params)

        # Initialize handlers and format
        initial_format = GAUGE_OUTPUT_FORMATS.get(gauge_type, "ASCII")
        self.output_format = initial_format
        self.manual_sender = IntelligentCommandSender()
        self.response_handler = ResponseHandler(initial_format)

        # Serial settings
        self._init_serial_settings()

        # Setup communication modes
        self._init_communication_modes()

        self.logger.debug(f"Initialized {gauge_type} communicator with {initial_format} format")

    def _init_serial_settings(self):
        """Initialize serial port settings from gauge parameters"""
        self.baudrate = self.params["baudrate"]
        self.bytesize = self.params.get("bytesize", serial.EIGHTBITS)
        self.parity = self.params.get("parity", serial.PARITY_NONE)
        self.stopbits = self.params.get("stopbits", serial.STOPBITS_ONE)
        self.timeout = self.params.get("timeout", 2)
        self.write_timeout = self.params.get("write_timeout", 2)

    def _init_communication_modes(self):
        """Initialize communication mode settings"""
        self.rs_mode = "RS232"
        self.rs_modes = self.params.get("rs_modes", ["RS232"])
        self.continuous_output = self.gauge_type == "CDG045D"
        self.continuous_reading = False
        self._stop_continuous = False

        # RS485 timing parameters
        self.rts_level_for_tx = True
        self.rts_level_for_rx = False
        self.rts_delay_before_tx = 0.002
        self.rts_delay_before_rx = 0.002
        self.rts_delay = 0.002

    def connect(self) -> bool:
        """Establish serial connection and test it"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=self.write_timeout
            )

            self.set_rs_mode(self.rs_mode)
            return self.test_connection()

        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            self.disconnect()
            return False

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        """Send command using protocol handler"""
        try:
            # Create command bytes
            cmd_bytes = self.protocol.create_command(command)
            formatted_cmd = self.format_response(cmd_bytes)
            self.logger.debug(f"Sending command: {formatted_cmd}")

            # Send command using IntelligentCommandSender
            result = self.manual_sender.send_manual_command(self, cmd_bytes.hex(' '), self.output_format)

            if not result['success']:
                return GaugeResponse(
                    raw_data=b"",
                    success=False,
                    error_message=result['error'],
                    formatted_data=""
                )

            # Handle response
            if result['response_raw']:
                response_bytes = bytes.fromhex(result['response_raw'])
                return self.protocol.parse_response(response_bytes)

            return GaugeResponse(
                raw_data=b"",
                success=False,
                error_message="No response received",
                formatted_data=""
            )

        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            return GaugeResponse(
                raw_data=b"",
                success=False,
                error_message=str(e),
                formatted_data=""
            )

    def read_response(self) -> Optional[bytes]:
        """Read response based on gauge type"""
        if not self.ser:
            return None

        try:
            if self.continuous_output:
                response = self._read_with_frame_sync(0x07, 9)
            elif isinstance(self.protocol, PPGProtocol):
                response = self._read_until_terminator(b'\\')
            else:
                response = self._read_available()

            if response:
                formatted_resp = self.format_response(response)
                self.logger.debug(f"Received response: {formatted_resp}")
            return response

        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None

    def _read_with_frame_sync(self, sync_byte: int, frame_size: int) -> Optional[bytes]:
        """Read fixed-size frame with sync byte"""
        start_time = time.time()
        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting >= 1:
                byte = self.ser.read(1)
                if byte[0] == sync_byte:
                    remaining = self.ser.read(frame_size - 1)
                    if len(remaining) == frame_size - 1:
                        return byte + remaining
            time.sleep(0.001)
        return None

    def _read_until_terminator(self, terminator: bytes) -> Optional[bytes]:
        """Read until terminator is found"""
        response = bytearray()
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting:
                byte = self.ser.read(1)
                response += byte
                if response.endswith(terminator):
                    return bytes(response)

                # For PPG gauges, also check for NAK response
                if response.startswith(b'@NAK'):
                    # Read until backslash
                    while not response.endswith(b'\\'):
                        if self.ser.in_waiting:
                            response += self.ser.read(1)
                    return bytes(response)
            else:
                if response:  # Return what we have if no more data is coming
                    return bytes(response)
                time.sleep(0.01)

        return bytes(response) if response else None

    def _read_available(self) -> Optional[bytes]:
        """Read all available data"""
        response = bytearray()
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting:
                response += self.ser.read(1)
            else:
                if response:
                    return bytes(response)
                time.sleep(0.01)

        return bytes(response) if response else None

    def read_continuous(self, callback, update_interval) -> None:
        """Handle continuous reading"""
        self._stop_continuous = False

        while not self._stop_continuous and self.ser and self.ser.is_open:
            try:
                response = self.read_response()
                if response:
                    gauge_response = self.protocol.parse_response(response)
                    callback(gauge_response)
                time.sleep(update_interval)
            except Exception as e:
                self.logger.error(f"Continuous reading error: {str(e)}")
                callback(self.response_handler.create_gauge_response(
                    raw_data=b"",
                    success=False,
                    error_message=f"Reading error: {str(e)}"
                ))

    def format_response(self, response: bytes) -> str:
        """Delegate response formatting to ResponseHandler"""
        return self.response_handler.format_response(response)

    def set_output_format(self, format_type: str):
        """Set output format for both communicator and response handler"""
        if format_type not in OUTPUT_FORMATS:
            self.logger.error(f"Invalid output format: {format_type}")
            return

        self.output_format = format_type
        self.response_handler.set_output_format(format_type)
        self.logger.debug(f"Output format set to: {format_type}")

    def format_response(self, response: bytes) -> str:
        """Format response according to current output format"""
        return self.response_handler.format_response(response)

    def apply_serial_settings(self, settings: dict):
        """Apply new serial port settings"""
        try:
            if self.ser and self.ser.is_open:
                self.ser.baudrate = settings['baudrate']
                self.ser.bytesize = settings['bytesize']
                self.ser.parity = settings['parity']
                self.ser.stopbits = settings['stopbits']

                # Handle RS485 mode settings
                if settings.get('rs485_mode', False):
                    self.set_rs_mode("RS485")
                    if isinstance(self.protocol, PPGProtocol):  # Changed from PPG550Protocol
                        self.protocol.address = settings.get('rs485_address', 254)
                else:
                    self.set_rs_mode("RS232")

                self.logger.debug(f"Serial settings updated: {settings}")
                if settings.get('rs485_mode', False):
                    self.logger.debug(f"RS485 Address: {settings.get('rs485_address', 254)}")

        except Exception as e:
            self.logger.error(f"Failed to update serial settings: {str(e)}")
            raise

    def set_rs_mode(self, mode: str) -> bool:
        if mode not in self.rs_modes:
            return False
        self.rs_mode = mode
        if self.ser and self.ser.is_open:
            if mode == "RS485":
                self.ser.setDTR(True)
                self.ser.setRTS(False)
            else:
                self.ser.setDTR(True)
                self.ser.setRTS(True)
        return True

    def set_continuous_reading(self, enabled: bool):
        """Enable/disable continuous reading mode"""
        self.continuous_reading = enabled
        self._stop_continuous = not enabled
        self.logger.debug(f"Continuous reading {'enabled' if enabled else 'disabled'}")

    def stop_continuous_reading(self):
        """Stop continuous reading mode"""
        self._stop_continuous = True
        self.logger.debug("Stopping continuous reading")

    def test_connection(self) -> bool:
        """Test connection using protocol's test commands"""
        if not self.ser or not self.ser.is_open:
            return False

        try:
            for cmd_bytes in self.protocol.test_commands():
                self.logger.debug(f"Testing connection with command: {cmd_bytes.hex(' ')}")
                result = self.manual_sender.send_manual_command(
                    self,
                    cmd_bytes.hex(' '),
                    None
                )
                if result['success'] and result['response_raw']:
                    self.logger.debug(f"Test response: {result['response_formatted']}")
                    return True
                else:
                    self.logger.debug("Test command failed or no response")

            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error disconnecting: {str(e)}")
            return False


class GaugeTester:
    """Handles all gauge testing functionality including baud rate testing, connection testing, and ENQ tests"""

    def __init__(self, communicator, logger):
        """Initialize with reference to communicator and logger"""
        self.communicator = communicator
        self.logger = logger
        self.gauge_type = communicator.gauge_type
        self.params = GAUGE_PARAMETERS[self.gauge_type]
        self.protocol = communicator.protocol
        self.test_commands = self._get_test_commands()

    def send_command_formatted(self, command_bytes: bytes) -> Optional[str]:
        """Send command and return formatted response based on current output format"""
        if not self.communicator or not self.communicator.ser:
            return None

        try:
            # Clear buffers
            self.communicator.ser.reset_input_buffer()
            self.communicator.ser.reset_output_buffer()

            # Format command for logging using current output format
            formatted_cmd = self.communicator.format_response(command_bytes)
            self.logger.debug(f"Sending command: {formatted_cmd}")

            # Send command
            self.communicator.ser.write(command_bytes)
            self.communicator.ser.flush()

            # Read response
            response = self.communicator.read_response()
            if response:
                formatted_resp = self.communicator.format_response(response)
                self.logger.debug(f"Received response: {formatted_resp}")
                return formatted_resp
            return None

        except Exception as e:
            self.logger.error(f"Command send error: {str(e)}")
            return None

    def _get_test_commands(self) -> dict:
        """Get test commands specific to the gauge type"""
        commands = {}
        if self.gauge_type in ["PCG550", "PSG550", "MAG500", "MPG500"]:
            commands.update({
                "product_name": {"pid": 208, "cmd": 1, "desc": "Read product name"},
                "software_version": {"pid": 218, "cmd": 1, "desc": "Read software version"},
                "serial_number": {"pid": 207, "cmd": 1, "desc": "Read serial number"}
            })
        elif self.gauge_type == "PPG550":
            commands.update({
                "product_name": {"cmd": "PRD", "type": "read"},
                "software_version": {"cmd": "SWV", "type": "read"},
                "serial_number": {"cmd": "SER", "type": "read"}
            })
        elif self.gauge_type == "CDG045D":
            commands.update({
                "software_version": {"cmd": "read", "name": "software_version"},
                "unit": {"cmd": "read", "name": "unit"},
                "gauge_type": {"cmd": "read", "name": "cdg_type"}
            })
        return commands

    def test_connection(self) -> bool:
        """Test connection using protocol's test commands"""
        if not self.communicator.ser or not self.communicator.ser.is_open:
            return False

        try:
            for cmd_bytes in self.communicator.protocol.test_commands():
                formatted_cmd = self.communicator.format_response(cmd_bytes)
                self.logger.debug(f"Testing connection with command: {formatted_cmd}")

                result = IntelligentCommandSender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )

                if result['success']:
                    if 'response_formatted' in result:
                        self.logger.debug(f"Test response: {result['response_formatted']}")
                        return True
                    else:
                        self.logger.debug("Test response missing formatted data")
                else:
                    self.logger.debug(f"Test command failed: {result.get('error', 'Unknown error')}")

            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False
    def try_all_baud_rates(self, port: str) -> bool:
        """Test connection with different baud rates"""
        # Factory default rates first, then others
        baud_rates = [
            self.params.get("baudrate", 9600),  # Try factory default first
            57600, 38400, 19200, 9600
        ]
        # Remove duplicates while preserving order
        baud_rates = list(dict.fromkeys(baud_rates))

        self.logger.info("\n=== Testing Baud Rates ===")

        for baud in baud_rates:
            self.logger.info(f"\nTrying baud rate: {baud}")
            try:
                # Create temporary communicator for this baud rate
                temp_communicator = GaugeCommunicator(
                    port=port,
                    gauge_type=self.gauge_type,
                    logger=self.logger
                )
                temp_communicator.baudrate = baud

                if temp_communicator.connect():
                    # Test connection with commands
                    if self.test_connection():
                        self.logger.info(f"Successfully connected at {baud} baud!")
                        temp_communicator.disconnect()
                        return True
                    else:
                        self.logger.debug(f"Connection test failed at {baud} baud")

                if temp_communicator.ser and temp_communicator.ser.is_open:
                    temp_communicator.disconnect()

            except Exception as e:
                self.logger.error(f"Failed at {baud} baud: {str(e)}")

            time.sleep(0.5)  # Wait between attempts

        self.logger.info("\nFailed to connect at any baud rate")
        return False

    def send_enq(self) -> bool:
        """Send ENQ character and check response"""
        if not self.communicator.ser or not self.communicator.ser.is_open:
            self.logger.error("Not connected")
            return False

        try:
            # Clear buffers
            self.communicator.ser.reset_input_buffer()
            self.communicator.ser.reset_output_buffer()

            self.logger.debug("> Sending ENQ (0x05)")

            # Use IntelligentCommandSender to send ENQ
            result = IntelligentCommandSender.send_manual_command(
                self.communicator,
                "05",  # ENQ in hex
                self.communicator.output_format
            )

            if result['success'] and 'response_formatted' in result:
                self.logger.debug(f"< ENQ Response: {result['response_formatted']}")
                return True
            else:
                self.logger.debug("< No response to ENQ")
                return False

        except Exception as e:
            self.logger.error(f"ENQ test error: {str(e)}")
            return False


    def get_supported_test_commands(self) -> dict:
        """Return dictionary of supported test commands for this gauge type"""
        return self.test_commands

    def run_all_tests(self) -> dict:
        """Run all available tests and return results"""
        results = {
            "connection": False,
            "enq": False,
            "commands_tested": {}
        }

        if not self.communicator.ser or not self.communicator.ser.is_open:
            return results

        # Test basic connection
        results["connection"] = True

        # Test ENQ
        results["enq"] = self.send_enq()

        # Test each command
        for cmd_name, cmd_info in self.test_commands.items():
            try:
                if self.gauge_type in ["PCG550", "PSG550", "MAG500", "MPG500"]:
                    command = GaugeCommand(
                        name=cmd_name,
                        command_type="?",
                        parameters={"pid": cmd_info["pid"], "cmd": cmd_info["cmd"]}
                    )
                elif self.gauge_type == "PPG550":
                    command = GaugeCommand(
                        name=cmd_info["cmd"],
                        command_type="?"
                    )
                else:  # CDG045D
                    command = GaugeCommand(
                        name=cmd_info["name"],
                        command_type=cmd_info["cmd"]
                    )

                cmd_bytes = self.protocol.create_command(command)
                result = self.communicator.manual_sender.send_manual_command(
                    self.communicator,
                    cmd_bytes.hex(' '),
                    self.communicator.output_format
                )

                results["commands_tested"][cmd_name] = {
                    "success": result['success'],
                    "response": result.get('response_formatted', '')
                }

            except Exception as e:
                results["commands_tested"][cmd_name] = {
                    "success": False,
                    "error": str(e)
                }

        return results
