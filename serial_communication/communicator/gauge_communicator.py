"""
gauge_communicator.py
Implements the GaugeCommunicator class that handles core serial operations and protocol interactions.
"""


import time
import logging
from typing import Optional

import serial
import serial.tools.list_ports

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.gauges.protocols.ppg_protocol import PPGProtocol  # Add this import
from serial_communication.communicator.intelligent_command_sender import IntelligentCommandSender
from serial_communication.communicator.response_handler import ResponseHandler
from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS, OUTPUT_FORMATS
from serial_communication.models import GaugeCommand, GaugeResponse

# Import the protocol factory function directly
from .protocol_factory import get_protocol
class GaugeCommunicator:
    """
    Main communicator class that manages serial connections, sending commands,
    reading responses, and controlling continuous reading.
    """

    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        self.port = port
        self.gauge_type = gauge_type
        self.logger = logger or logging.getLogger(__name__)
        self.ser: Optional[serial.Serial] = None

        # Acquire gauge parameters and create protocol handler
        self.params = GAUGE_PARAMETERS[gauge_type]
        self.protocol = get_protocol(gauge_type, self.params)

        # Decide on initial output format
        initial_format = GAUGE_OUTPUT_FORMATS.get(gauge_type, "ASCII")
        self.output_format = initial_format

        # Initialize command sender and response handler
        self.manual_sender = IntelligentCommandSender()
        self.response_handler = ResponseHandler(initial_format)

        # Setup default serial config
        self._init_serial_settings()
        # Setup default communication modes
        self._init_communication_modes()

        self.logger.debug(f"Initialized {gauge_type} communicator with {initial_format} format")

    def _init_serial_settings(self):
        """Load serial port settings from config."""
        self.baudrate = self.params["baudrate"]
        self.bytesize = self.params.get("bytesize", serial.EIGHTBITS)
        self.parity = self.params.get("parity", serial.PARITY_NONE)
        self.stopbits = self.params.get("stopbits", serial.STOPBITS_ONE)
        self.timeout = self.params.get("timeout", 2)
        self.write_timeout = self.params.get("write_timeout", 2)

    def _init_communication_modes(self):
        """Set up communication mode defaults."""
        self.rs_mode = "RS232"
        self.rs_modes = self.params.get("rs_modes", ["RS232"])
        self.continuous_output = (self.gauge_type == "CDG045D")
        self.continuous_reading = False
        self._stop_continuous = False

        # RS485 timing
        self.rts_level_for_tx = True
        self.rts_level_for_rx = False
        self.rts_delay_before_tx = 0.002
        self.rts_delay_before_rx = 0.002
        self.rts_delay = 0.002

    def connect(self) -> bool:
        """Open the serial port and test the connection."""
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

    def disconnect(self) -> bool:
        """Close the serial connection, if open."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error disconnecting: {str(e)}")
            return False

    def test_connection(self) -> bool:
        """
        Test connection using the protocol's test commands,
        returning True if at least one test command yields a valid response.
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("Not connected")
            return False

        try:
            current_format = self.output_format
            self.logger.debug(f"Testing connection using {current_format} format")

            for cmd_bytes in self.protocol.test_commands():
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()

                if current_format == "Hex":
                    formatted_cmd = ' '.join(f'{b:02X}' for b in cmd_bytes)
                elif current_format == "ASCII":
                    formatted_cmd = self._format_protocol_message(cmd_bytes)
                elif current_format == "Decimal":
                    formatted_cmd = ' '.join(str(b) for b in cmd_bytes)
                elif current_format == "Binary":
                    formatted_cmd = ' '.join(f'{b:08b}' for b in cmd_bytes)
                elif current_format == "UTF-8":
                    formatted_cmd = cmd_bytes.decode('utf-8', errors='replace')
                else:
                    formatted_cmd = str(cmd_bytes)

                self.logger.debug(f"Testing command: {formatted_cmd}")
                self.ser.write(cmd_bytes)
                self.ser.flush()
                response = self.read_response()

                if response:
                    if current_format == "Hex":
                        formatted_resp = ' '.join(f'{b:02X}' for b in response)
                    elif current_format == "ASCII":
                        formatted_resp = self._format_protocol_message(response)
                    elif current_format == "Decimal":
                        formatted_resp = ' '.join(str(b) for b in response)
                    elif current_format == "Binary":
                        formatted_resp = ' '.join(f'{b:08b}' for b in response)
                    elif current_format == "UTF-8":
                        formatted_resp = response.decode('utf-8', errors='replace')
                    else:
                        formatted_resp = str(response)

                    self.logger.debug(f"Received response: {formatted_resp}")
                    return True
                else:
                    self.logger.debug("No response received")

            return False

        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def send_command(self, command: 'GaugeCommand') -> 'GaugeResponse':
        """Creates and sends a command via the protocol, then returns the parsed response."""
        try:
            cmd_bytes = self.protocol.create_command(command)
            formatted_cmd = self.format_response(cmd_bytes)
            self.logger.debug(f"Sending command: {formatted_cmd}")

            result = self.manual_sender.send_manual_command(self, cmd_bytes.hex(' '), self.output_format)
            if not result['success']:
                return GaugeResponse(raw_data=b"", success=False, error_message=result['error'], formatted_data="")

            if result['response_raw']:
                response_bytes = bytes.fromhex(result['response_raw'])
                return self.protocol.parse_response(response_bytes)

            return GaugeResponse(raw_data=b"", success=False, error_message="No response received", formatted_data="")

        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            return GaugeResponse(raw_data=b"", success=False, error_message=str(e), formatted_data="")

    def read_response(self) -> Optional[bytes]:
        """Reads a response from the gauge based on gauge type or continuous modes."""
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
                self.logger.debug(f"Received response: {self.format_response(response)}")
            return response
        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None

    def _read_with_frame_sync(self, sync_byte: int, frame_size: int) -> Optional[bytes]:
        """Read a fixed-size frame that starts with a specific sync byte."""
        import time
        start_time = time.time()
        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting >= 1:
                byte = self.ser.read(1)
                if byte and byte[0] == sync_byte:
                    remaining = self.ser.read(frame_size - 1)
                    if len(remaining) == frame_size - 1:
                        return byte + remaining
            time.sleep(0.001)
        return None

    def _read_until_terminator(self, terminator: bytes) -> Optional[bytes]:
        """Reads until a certain terminator is encountered."""
        import time
        response = bytearray()
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting:
                byte = self.ser.read(1)
                response += byte
                if response.endswith(terminator):
                    return bytes(response)

                # Also handle @NAK for PPG
                if response.startswith(b'@NAK'):
                    while not response.endswith(b'\\'):
                        if self.ser.in_waiting:
                            response += self.ser.read(1)
                    return bytes(response)
            else:
                if response:
                    return bytes(response)
                time.sleep(0.01)

        return bytes(response) if response else None

    def _read_available(self) -> Optional[bytes]:
        """Reads all available data."""
        import time
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

    def format_response(self, response: bytes) -> str:
        """Use the ResponseHandler to format the response."""
        return self.response_handler.format_response(response)

    def set_output_format(self, format_type: str):
        """Set a new output format for the communicator and its response handler."""
        if format_type not in OUTPUT_FORMATS:
            self.logger.error(f"Invalid output format: {format_type}")
            return
        self.output_format = format_type
        self.response_handler.set_output_format(format_type)
        self.logger.debug(f"Output format set to: {format_type}")

    def apply_serial_settings(self, settings: dict):
        """Applies updated serial settings if the port is open."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.baudrate = settings['baudrate']
                self.ser.bytesize = settings['bytesize']
                self.ser.parity = settings['parity']
                self.ser.stopbits = settings['stopbits']

                if settings.get('rs485_mode', False):
                    self.set_rs_mode("RS485")
                    if isinstance(self.protocol, PPGProtocol):
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
        """Switch between RS232 and RS485 modes if supported."""
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
        """Enable or disable continuous reading mode."""
        self.continuous_reading = enabled
        self._stop_continuous = not enabled
        self.logger.debug(f"Continuous reading {'enabled' if enabled else 'disabled'}")

    def stop_continuous_reading(self):
        """Stop continuous reading."""
        self._stop_continuous = True
        self.logger.debug("Stopping continuous reading")

    def read_continuous(self, callback, update_interval: float):
        """Loop to read continuously at specified intervals, calling a callback with the response."""
        import time

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

