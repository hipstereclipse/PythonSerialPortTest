"""
gauge_communicator.py

Implements the GaugeCommunicator class that manages serial communication,
command creation, response parsing, and continuous reading for vacuum gauges.
"""

import time
import logging
from typing import Optional
import serial

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.gauges.protocols.ppg_protocol import PPGProtocol
from serial_communication.communicator.intelligent_command_sender import IntelligentCommandSender
from serial_communication.communicator.response_handler import ResponseHandler
from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS, OUTPUT_FORMATS
from serial_communication.models import GaugeCommand, GaugeResponse
from serial_communication.communicator.protocol_factory import get_protocol


class GaugeCommunicator:
    """
    Manages serial communication with a vacuum gauge and handles command/response interactions.
    """

    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        """
        Initializes the GaugeCommunicator.

        Args:
            port: The serial port (e.g., "COM3" or "/dev/ttyUSB0").
            gauge_type: The gauge model/type (e.g., "PPG550", "CDG045D").
            logger: Optional logger for debugging.
        """
        self.port = port
        self.gauge_type = gauge_type
        self.logger = logger or logging.getLogger(__name__)
        self.ser: Optional[serial.Serial] = None
        self.params = GAUGE_PARAMETERS[gauge_type]
        self.protocol: GaugeProtocol = get_protocol(gauge_type, self.params)
        initial_format = GAUGE_OUTPUT_FORMATS.get(gauge_type, "ASCII")
        self.output_format = initial_format
        self.manual_sender = IntelligentCommandSender()
        self.response_handler = ResponseHandler(initial_format)
        self._init_serial_settings()
        self._init_communication_modes()
        self.logger.debug(f"Initialized {gauge_type} communicator with output format: {initial_format}")

    def _init_serial_settings(self) -> None:
        self.baudrate = self.params["baudrate"]
        self.bytesize = self.params.get("bytesize", serial.EIGHTBITS)
        self.parity = self.params.get("parity", serial.PARITY_NONE)
        self.stopbits = self.params.get("stopbits", serial.STOPBITS_ONE)
        self.timeout = self.params.get("timeout", 2)
        self.write_timeout = self.params.get("write_timeout", 2)

    def _init_communication_modes(self) -> None:
        self.rs_mode = "RS232"
        self.rs_modes = self.params.get("rs_modes", ["RS232"])
        self.continuous_output = (self.gauge_type == "CDG045D")
        self.continuous_reading = False
        self._stop_continuous = False
        self.rts_level_for_tx = True
        self.rts_level_for_rx = False
        self.rts_delay_before_tx = 0.002
        self.rts_delay_before_rx = 0.002
        self.rts_delay = 0.002

    def connect(self) -> bool:
        """
        Opens the serial port using the configured settings and tests the connection.

        Returns:
            True if the connection test is successful, False otherwise.
        """
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
            self.disable_validation()
            connection_result = self.test_connection()
            if connection_result:
                self.enable_validation()
            return connection_result
        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            self.disconnect()
            return False

    def detect_gauge(self) -> Optional[str]:
        """
        If the gauge type is generic ("CDGxxxD"), attempts to detect the exact model.

        Returns:
            The detected gauge type (e.g., "CDG045D") or None if detection fails.
        """
        if self.gauge_type != "CDGxxxD":
            self.logger.debug("Gauge detection skipped; specific type already selected.")
            return self.gauge_type
        try:
            response = self.send_command(GaugeCommand(name="cdg_type", command_type="?"))
            if response.success and response.raw_data:
                detected_type = self.protocol.detect_gauge_type(response.raw_data)
                if detected_type:
                    self.gauge_type = detected_type
                    self.params = GAUGE_PARAMETERS[self.gauge_type]
                    self.protocol = get_protocol(self.gauge_type, self.params)
                    self.logger.info(f"Detected gauge type: {detected_type}")
                    return detected_type
                else:
                    self.logger.error("Failed to detect gauge type: No matching model found.")
                    return None
            else:
                self.logger.error(f"Gauge detection failed: {response.error_message}")
                return None
        except Exception as e:
            self.logger.error(f"Error during gauge detection: {str(e)}")
            return None

    def enable_validation(self) -> None:
        if hasattr(self.protocol, 'enable_validation'):
            self.protocol.enable_validation()

    def disable_validation(self) -> None:
        if hasattr(self.protocol, 'disable_validation'):
            self.protocol.disable_validation()

    def disconnect(self) -> bool:
        """
        Closes the serial port if it is open.

        Returns:
            True if the disconnection is successful, False otherwise.
        """
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
        Tests the connection by sending protocol-specific test commands.

        Returns:
            True if at least one test command receives a valid response, False otherwise.
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("Not connected")
            return False
        try:
            for cmd_bytes in self.protocol.test_commands():
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                formatted_cmd = self.format_response(cmd_bytes)
                self.logger.debug(f"Testing command: {formatted_cmd}")
                self.ser.write(cmd_bytes)
                self.ser.flush()
                response = self.read_response()
                if response:
                    formatted_resp = self.format_response(response)
                    self.logger.debug(f"Received response: {formatted_resp}")
                    return True
                else:
                    self.logger.debug("No response received")
            return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def send_command(self, command: GaugeCommand) -> GaugeResponse:
        """
        Creates and sends a command using the gauge protocol, then parses the response.

        Args:
            command: The GaugeCommand object representing the command.

        Returns:
            A GaugeResponse object containing the parsed response.
        """
        try:
            cmd_bytes = self.protocol.create_command(command)
            formatted_cmd = self.format_response(cmd_bytes)
            self.logger.debug(f"Sending command: {formatted_cmd}")
            result = self.manual_sender.send_manual_command(self, cmd_bytes.hex(' '), self.output_format)
            if not result['success']:
                return GaugeResponse(
                    raw_data=b"",
                    success=False,
                    error_message=result['error'],
                    formatted_data=""
                )
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
            return GaugeResponse(raw_data=b"", success=False, error_message=str(e), formatted_data="")

    def read_response(self) -> Optional[bytes]:
        """
        Reads a response from the gauge. Chooses the appropriate reading method
        based on the gauge’s protocol.

        Returns:
            The raw response bytes, or None if no response is received.
        """
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

    def format_response(self, response: bytes) -> str:
        """
        Formats the raw response using the ResponseHandler.

        Args:
            response: The raw response bytes.

        Returns:
            A formatted string representation.
        """
        return self.response_handler.format_response(response)

    def set_output_format(self, format_type: str) -> None:
        """
        Sets the communicator's output format.

        Args:
            format_type: The desired output format.
        """
        if format_type not in OUTPUT_FORMATS:
            self.logger.error(f"Invalid output format: {format_type}")
            return
        self.output_format = format_type
        self.response_handler.set_output_format(format_type)
        self.logger.debug(f"Output format set to: {format_type}")

    def apply_serial_settings(self, settings: dict) -> None:
        """
        Applies new serial settings to the open port.

        Args:
            settings: A dictionary containing serial parameter values.
        """
        try:
            if self.ser and self.ser.is_open:
                self.ser.baudrate = settings['baudrate']
                self.ser.bytesize = settings['bytesize']
                self.ser.parity = settings['parity']
                self.ser.stopbits = settings['stopbits']
                if settings.get('rs485_mode', False):
                    self.set_rs_mode("RS485")
                    if hasattr(self.protocol, 'address'):
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
        """
        Switches between RS232 and RS485 modes.

        Args:
            mode: The desired mode ("RS232" or "RS485").

        Returns:
            True if the mode is supported and set, False otherwise.
        """
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

    def set_continuous_reading(self, enabled: bool) -> None:
        """
        Enables or disables continuous reading mode.

        Args:
            enabled: True to enable, False to disable.
        """
        self.continuous_reading = enabled
        self._stop_continuous = not enabled
        self.logger.debug(f"Continuous reading {'enabled' if enabled else 'disabled'}")

    def stop_continuous_reading(self) -> None:
        """
        Signals the continuous reading loop to stop.
        """
        self._stop_continuous = True
        self.logger.debug("Stopping continuous reading")

    def read_continuous(self, callback, update_interval: float) -> None:
        """
        Continuously reads responses and calls the provided callback with each GaugeResponse.

        Args:
            callback: Function to call with each GaugeResponse.
            update_interval: The time (in seconds) between reads.
        """
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

    def _read_with_frame_sync(self, sync_byte: int, frame_size: int) -> Optional[bytes]:
        """
        Waits for a sync byte then reads a fixed-size frame.

        Args:
            sync_byte: The expected sync byte.
            frame_size: Total number of bytes in the frame.

        Returns:
            The complete frame bytes if found, None otherwise.
        """
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
        """
        Reads until the specified terminator is encountered.

        Args:
            terminator: The terminator byte sequence (e.g., b'\\').

        Returns:
            The bytes read (including the terminator) if found, otherwise None.
        """
        import time
        response = bytearray()
        start_time = time.time()
        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting:
                byte = self.ser.read(1)
                response += byte
                if response.endswith(terminator):
                    return bytes(response)
                # Special handling for certain error responses (e.g., PPG '@NAK...')
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
        """
        Reads all available bytes within the timeout period.

        Returns:
            The bytes read if any, otherwise None.
        """
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
