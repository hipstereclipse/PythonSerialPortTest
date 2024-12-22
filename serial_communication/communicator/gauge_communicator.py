"""
Implements the GaugeCommunicator class that handles core serial operations and protocol interactions.
This class is the main entry for sending commands and reading responses for any supported gauge.
"""

import time                                    # Imports time for sleeps and timing operations
import logging                                 # Imports logging for debug/error output
from typing import Optional                    # Imports Optional for type hinting
import serial                                  # Imports pySerial for serial port handling
import serial.tools.list_ports                # Imports list_ports if needed

# Imports the gauge protocol and protocol factory
from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.gauges.protocols.ppg_protocol import PPGProtocol

# Imports our custom classes/functions
from serial_communication.communicator.intelligent_command_sender import IntelligentCommandSender
from serial_communication.communicator.response_handler import ResponseHandler
from serial_communication.config import GAUGE_PARAMETERS, GAUGE_OUTPUT_FORMATS, OUTPUT_FORMATS
from serial_communication.models import GaugeCommand, GaugeResponse

# Imports the protocol factory so we can get a protocol instance for each gauge type
from .protocol_factory import get_protocol


class GaugeCommunicator:
    """
    Main communicator class that manages:
     - Serial connections
     - Sending commands
     - Reading responses
     - Enabling or disabling continuous reading

    This is where the user can unify all gauge communication, so they don't have to rewrite code.
    """

    def __init__(self, port: str, gauge_type: str, logger: Optional[logging.Logger] = None):
        """
        Initializes the GaugeCommunicator for a specified port and gauge type.
         - port: e.g., COM3 or /dev/ttyUSB0
         - gauge_type: e.g., "PPG550" or "CDG025D"
         - logger: optional logger to record debug/info/error messages
        """
        # Stores the serial port and gauge type
        self.port = port
        self.gauge_type = gauge_type
        # Uses the provided logger or creates a default one if missing
        self.logger = logger or logging.getLogger(__name__)
        # pySerial Serial object (None until connect())
        self.ser: Optional[serial.Serial] = None

        # Loads gauge parameters from the config
        self.params = GAUGE_PARAMETERS[gauge_type]
        # Creates a protocol instance for this gauge using a factory function
        self.protocol = get_protocol(gauge_type, self.params)

        # Chooses an initial output format based on the gauge type
        initial_format = GAUGE_OUTPUT_FORMATS.get(gauge_type, "ASCII")
        self.output_format = initial_format

        # Creates an IntelligentCommandSender for manual commands
        self.manual_sender = IntelligentCommandSender()
        # Creates a ResponseHandler for formatting/decoding responses
        self.response_handler = ResponseHandler(initial_format)

        # Sets up default serial configuration from params
        self._init_serial_settings()
        # Sets up extra defaults (e.g., RS485 or continuous mode)
        self._init_communication_modes()

        self.logger.debug(f"Initialized {gauge_type} communicator with {initial_format} format")

    def _init_serial_settings(self):
        """
        Loads serial port settings from the gauge’s parameter dictionary (if provided).
        This helps unify logic so that we avoid repeating code.
        """
        self.baudrate = self.params["baudrate"]
        self.bytesize = self.params.get("bytesize", serial.EIGHTBITS)
        self.parity = self.params.get("parity", serial.PARITY_NONE)
        self.stopbits = self.params.get("stopbits", serial.STOPBITS_ONE)
        self.timeout = self.params.get("timeout", 2)
        self.write_timeout = self.params.get("write_timeout", 2)

    def _init_communication_modes(self):
        """
        Initializes communication-related features like:
         - rs_mode: "RS232" or "RS485"
         - whether the gauge supports continuous output
         - default or recommended values for hardware flow control
        """
        # Default to RS232
        self.rs_mode = "RS232"
        # Retrieves supported modes from gauge params
        self.rs_modes = self.params.get("rs_modes", ["RS232"])

        # Some gauges may have built-in continuous output, e.g., certain CDG's
        # We'll store a bool to indicate if the gauge supports continuous reading
        self.continuous_output = (self.gauge_type == "CDG045D")

        # Tracking variables for continuous reading
        self.continuous_reading = False
        self._stop_continuous = False

        # For RS485 timing, these are typically small delays needed to switch between TX and RX
        self.rts_level_for_tx = True
        self.rts_level_for_rx = False
        self.rts_delay_before_tx = 0.002
        self.rts_delay_before_rx = 0.002
        self.rts_delay = 0.002

    def connect(self) -> bool:
        """
        Opens the serial port with the configured settings.
        Returns True if connection test passes, else False.
        """
        try:
            # Creates and opens the serial port
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=self.timeout,
                write_timeout=self.write_timeout
            )
            # Sets RS232 or RS485 mode
            self.set_rs_mode(self.rs_mode)

            # Temporarily disables strict validation to run a test
            self.disable_validation()
            connection_result = self.test_connection()

            if connection_result:
                # If the gauge responded, re-enable validation
                self.enable_validation()

            return connection_result

        except Exception as e:
            # Logs an error if anything failed
            self.logger.error(f"Connection failed: {str(e)}")
            self.disconnect()
            return False

    def detect_gauge(self):
        """
        If the gauge_type is "CDGxxxD", tries to detect the *actual* model (CDG025D, CDG045D, etc.)
        by sending a "cdg_type" command and parsing the response.
        Returns the detected gauge type or None if detection failed.
        """
        if self.gauge_type != "CDGxxxD":
            self.logger.debug("Gauge detection skipped. Already a specific type selected.")
            return self.gauge_type

        try:
            # Sends the "cdg_type" read command
            response = self.send_command(GaugeCommand(name="cdg_type", command_type="?"))
            if response.success and response.raw_data:
                # Asks the protocol to interpret the raw_data
                detected_type = self.protocol.detect_gauge_type(response.raw_data)
                if detected_type:
                    # Updates internal references to the newly discovered type
                    self.gauge_type = detected_type
                    self.params = GAUGE_PARAMETERS[self.gauge_type]
                    self.protocol = get_protocol(self.gauge_type, self.params)
                    self.logger.info(f"Detected gauge type: {detected_type}")
                    return detected_type
                else:
                    self.logger.error("Failed to detect gauge type: No matching model found.")
                    return None
            else:
                # If the read was unsuccessful, logs the problem
                self.logger.error(f"Gauge detection failed: {response.error_message}")
                return None
        except Exception as e:
            self.logger.error(f"Error during gauge detection: {str(e)}")
            return None

    def enable_validation(self):
        """
        Calls the protocol’s method to enforce more stringent checks on responses,
        such as verifying checksums or expected lengths.
        """
        if hasattr(self.protocol, 'enable_validation'):
            self.protocol.enable_validation()

    def disable_validation(self):
        """
        Temporarily disables strict response validation to allow initial tests or unknown states.
        """
        if hasattr(self.protocol, 'disable_validation'):
            self.protocol.disable_validation()

    def disconnect(self) -> bool:
        """
        Closes the serial port if open. Returns True if it closed, False otherwise.
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
        Tests the connection by sending a set of 'test commands' specified by the protocol.
        If any command yields a valid response, returns True. Otherwise returns False.
        """
        if not self.ser or not self.ser.is_open:
            self.logger.error("Not connected")
            return False
        try:
            # Grabs the current user-chosen output format
            current_format = self.output_format
            self.logger.debug(f"Testing connection using {current_format} format")

            for cmd_bytes in self.protocol.test_commands():
                # Clears any leftover data in input/output buffers
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()

                # Logs the command in a user-readable format
                formatted_cmd = self.format_response(cmd_bytes)
                self.logger.debug(f"Testing command: {formatted_cmd}")

                # Sends the command
                self.ser.write(cmd_bytes)
                self.ser.flush()

                # Reads the response
                response = self.read_response()

                if response:
                    # If we got data back, logs it
                    formatted_resp = self.format_response(response)
                    self.logger.debug(f"Received response: {formatted_resp}")
                    return True
                else:
                    self.logger.debug("No response received")

            return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False

    def send_command(self, command: 'GaugeCommand') -> 'GaugeResponse':
        """
        Creates the appropriate command bytes via the protocol,
        sends them, and returns the parsed response as a GaugeResponse.
        """
        try:
            # Builds the raw command bytes
            cmd_bytes = self.protocol.create_command(command)
            # Logs a human-friendly version of the command
            formatted_cmd = self.format_response(cmd_bytes)
            self.logger.debug(f"Sending command: {formatted_cmd}")

            # Uses the IntelligentCommandSender to handle write/read cycle
            result = self.manual_sender.send_manual_command(self, cmd_bytes.hex(' '), self.output_format)
            if not result['success']:
                return GaugeResponse(
                    raw_data=b"",
                    success=False,
                    error_message=result['error'],
                    formatted_data=""
                )

            if result['response_raw']:
                # Decodes the raw hex back into bytes
                response_bytes = bytes.fromhex(result['response_raw'])
                # Asks the protocol to parse them into a structured object
                return self.protocol.parse_response(response_bytes)

            return GaugeResponse(
                raw_data=b"",
                success=False,
                error_message="No response received",
                formatted_data=""
            )
        except Exception as e:
            # On error, returns a GaugeResponse with error info
            self.logger.error(f"Command failed: {str(e)}")
            return GaugeResponse(raw_data=b"", success=False, error_message=str(e), formatted_data="")

    def read_response(self) -> Optional[bytes]:
        """
        Reads a response from the gauge. The method is specialized for different gauge behaviors:
         - Some gauges provide a continuous output block with a sync byte
         - Some gauges, like PPG, end with backslash
         - Others just read all available bytes
        Returns the raw bytes or None if no data found.
        """
        if not self.ser:
            return None

        try:
            # If this gauge supports continuous data, we read a fixed frame size
            if self.continuous_output:
                response = self._read_with_frame_sync(0x07, 9)
            # If the protocol is PPG, read until a terminator
            elif isinstance(self.protocol, PPGProtocol):
                response = self._read_until_terminator(b'\\')
            else:
                # Default: read everything available within the timeout
                response = self._read_available()

            if response:
                # Logs the raw response in the current format
                formatted_resp = self.format_response(response)
                self.logger.debug(f"Received response: {formatted_resp}")

            return response
        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None

    def format_response(self, response: bytes) -> str:
        """
        Uses the ResponseHandler to convert raw bytes into a user-readable string
        based on the chosen output format (Hex, ASCII, etc.).
        """
        return self.response_handler.format_response(response)

    def set_output_format(self, format_type: str):
        """
        Sets the communicator’s output format, so all logs and debug prints
        are consistent with what the user expects.
        """
        if format_type not in OUTPUT_FORMATS:
            self.logger.error(f"Invalid output format: {format_type}")
            return
        self.output_format = format_type
        self.response_handler.set_output_format(format_type)
        self.logger.debug(f"Output format set to: {format_type}")

    def apply_serial_settings(self, settings: dict):
        """
        Applies updated serial settings on-the-fly if the port is open.
        Useful when the user changes baud rate or RS485 mode in the GUI.
        """
        try:
            if self.ser and self.ser.is_open:
                self.ser.baudrate = settings['baudrate']
                self.ser.bytesize = settings['bytesize']
                self.ser.parity = settings['parity']
                self.ser.stopbits = settings['stopbits']

                # Switches between RS232/RS485 if necessary
                if settings.get('rs485_mode', False):
                    self.set_rs_mode("RS485")
                    if isinstance(self.protocol, PPGProtocol):
                        # Sets the PPG address if we’re in RS485
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
        Switches to RS485 or RS232 if supported by the gauge.
        Returns True if successful, False if the gauge does not support the requested mode.
        """
        if mode not in self.rs_modes:
            return False
        self.rs_mode = mode
        if self.ser and self.ser.is_open:
            # For RS485, we often need custom lines
            if mode == "RS485":
                self.ser.setDTR(True)
                self.ser.setRTS(False)
            else:
                # RS232
                self.ser.setDTR(True)
                self.ser.setRTS(True)
        return True

    def set_continuous_reading(self, enabled: bool):
        """
        Tells the communicator if we want continuous reading to start or stop.
        This flag is used in read_continuous().
        """
        self.continuous_reading = enabled
        self._stop_continuous = not enabled
        self.logger.debug(f"Continuous reading {'enabled' if enabled else 'disabled'}")

    def stop_continuous_reading(self):
        """
        Sets an internal flag so that any continuous reading loop can exit gracefully.
        """
        self._stop_continuous = True
        self.logger.debug("Stopping continuous reading")

    def read_continuous(self, callback, update_interval: float):
        """
        Repeatedly reads data from the gauge at a specified interval.
        Calls 'callback' each time with a GaugeResponse object.
        This method runs in a background thread to avoid freezing the GUI.
        """
        import time

        # Ensures that once set_continuous_reading(false) is called, this loop breaks
        self._stop_continuous = False
        while not self._stop_continuous and self.ser and self.ser.is_open:
            try:
                # Reads a single response
                response = self.read_response()
                if response:
                    # Asks the protocol to parse it
                    gauge_response = self.protocol.parse_response(response)
                    callback(gauge_response)
                # Sleeps for the desired interval
                time.sleep(update_interval)
            except Exception as e:
                # If an error occurs, calls back with an error response
                self.logger.error(f"Continuous reading error: {str(e)}")
                callback(self.response_handler.create_gauge_response(
                    raw_data=b"",
                    success=False,
                    error_message=f"Reading error: {str(e)}"
                ))

    # Helper methods for reading data in different styles:

    def _read_with_frame_sync(self, sync_byte: int, frame_size: int) -> Optional[bytes]:
        """
        Waits for a sync_byte, then reads frame_size bytes total.
        Some gauges produce a constant stream of fixed-size frames.
        """
        import time
        start_time = time.time()
        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting >= 1:
                # Reads 1 byte
                byte = self.ser.read(1)
                # Checks if it matches the sync byte
                if byte and byte[0] == sync_byte:
                    # Reads the remaining frame
                    remaining = self.ser.read(frame_size - 1)
                    if len(remaining) == frame_size - 1:
                        return byte + remaining
            time.sleep(0.001)
        return None

    def _read_until_terminator(self, terminator: bytes) -> Optional[bytes]:
        """
        Reads until a certain terminator is encountered, e.g., b'\\' in ASCII.
        Also handles certain special cases like NAK for PPG.
        """
        import time
        response = bytearray()
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting:
                byte = self.ser.read(1)
                response += byte
                # If we find the terminator, returns the data
                if response.endswith(terminator):
                    return bytes(response)

                # Some PPG gauges send '@NAK...' if error
                if response.startswith(b'@NAK'):
                    while not response.endswith(b'\\'):
                        if self.ser.in_waiting:
                            response += self.ser.read(1)
                    return bytes(response)
            else:
                if response:
                    # If the gauge is silent but we have data, returns it
                    return bytes(response)
                time.sleep(0.01)

        # If nothing was received, returns None or the partial response
        return bytes(response) if response else None

    def _read_available(self) -> Optional[bytes]:
        """
        Reads all available bytes within the set timeout.
        This is a fallback for simple protocols.
        """
        import time
        response = bytearray()
        start_time = time.time()

        while (time.time() - start_time) < self.timeout:
            if self.ser.in_waiting:
                response += self.ser.read(1)
            else:
                # If we have some data but no more is coming, return it
                if response:
                    return bytes(response)
                time.sleep(0.01)

        return bytes(response) if response else None
