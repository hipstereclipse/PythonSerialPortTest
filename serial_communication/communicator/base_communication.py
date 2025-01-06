# serial_communication/base_communication.py

"""
Provides the base communication handler class that serves as the foundation for all serial devices.
This class implements core functionality used by both gauges and turbos.
"""

import logging
from typing import Optional, Dict, Any
import serial
from serial.tools import list_ports


class BaseCommunicationHandler:
    """
    Base class implementing core serial communication functionality.
    Handles connection management, basic I/O, and error handling.
    """

    def __init__(self, port: str, device_type: str, logger: Optional[logging.Logger] = None):
        """
        Initializes the communication handler with specified port and device settings.

        Args:
            port: Serial port identifier (e.g. "COM1")
            device_type: String identifying the device type (e.g. "BCG450")
            logger: Optional logger instance for output
        """
        # Stores the serial port identifier
        self.port = port

        # Stores the type of device being controlled
        self.device_type = device_type

        # Creates or stores logger instance
        self.logger = logger or logging.getLogger(__name__)

        # Initializes serial connection object (None until connect() called)
        self.ser: Optional[serial.Serial] = None

        # Stores current serial settings
        self.current_settings = {
            'baudrate': 9600,
            'bytesize': serial.EIGHTBITS,
            'parity': serial.PARITY_NONE,
            'stopbits': serial.STOPBITS_ONE,
            'timeout': 1.0,
            'write_timeout': 1.0
        }

    def connect(self) -> bool:
        """
        Establishes the serial connection with current settings.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Creates and opens serial port with current settings
            self.ser = serial.Serial(
                port=self.port,
                **self.current_settings
            )

            # Logs successful connection
            self.logger.info(f"Connected to {self.device_type} on {self.port}")
            return True

        except Exception as e:
            # Logs connection failure
            self.logger.error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        Safely closes the serial connection.

        Returns:
            bool: True if disconnect successful, False otherwise
        """
        try:
            if self.ser and self.ser.is_open:
                # Closes the serial port
                self.ser.close()
                # Logs disconnection
                self.logger.info(f"Disconnected from {self.device_type}")
                return True
            return False

        except Exception as e:
            # Logs disconnection failure
            self.logger.error(f"Error disconnecting: {str(e)}")
            return False

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Updates serial connection settings.

        Args:
            settings: Dictionary of serial parameters to update

        Returns:
            bool: True if settings updated successfully, False otherwise
        """
        try:
            # Updates stored settings
            self.current_settings.update(settings)

            # Applies new settings if connected
            if self.ser and self.ser.is_open:
                for key, value in settings.items():
                    setattr(self.ser, key, value)

                # Logs settings update
                self.logger.info(f"Serial settings updated: {settings}")
                return True

        except Exception as e:
            # Logs settings update failure
            self.logger.error(f"Failed to update settings: {str(e)}")

        return False

    def send_command(self, command: bytes) -> Optional[bytes]:
        """
        Sends raw command bytes and returns response.

        Args:
            command: Raw command bytes to send

        Returns:
            Optional[bytes]: Response bytes if successful, None otherwise
        """
        try:
            if not self.ser or not self.ser.is_open:
                raise Exception("Not connected")

            # Clears input/output buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            # Logs command being sent
            self.logger.debug(f"Sending command: {command.hex(' ')}")

            # Writes command bytes
            self.ser.write(command)
            self.ser.flush()

            # Reads response
            response = self.read_response()

            if response:
                # Logs received response
                self.logger.debug(f"Received response: {response.hex(' ')}")
                return response

            return None

        except Exception as e:
            # Logs command failure
            self.logger.error(f"Command failed: {str(e)}")
            return None

    def read_response(self) -> Optional[bytes]:
        """
        Reads response bytes from device.

        Returns:
            Optional[bytes]: Response bytes if successful, None otherwise
        """
        try:
            if not self.ser:
                return None

            # Reads available bytes
            response = bytearray()

            # Implements timeout
            start_time = time.time()
            while (time.time() - start_time) < self.current_settings['timeout']:
                if self.ser.in_waiting:
                    response.extend(self.ser.read(self.ser.in_waiting))

                    # Returns completed response
                    if response:
                        return bytes(response)

                time.sleep(0.01)

            return None

        except Exception as e:
            # Logs read failure
            self.logger.error(f"Read failed: {str(e)}")
            return None

    @staticmethod
    def list_ports() -> List[str]:
        """
        Lists available serial ports.

        Returns:
            List[str]: List of available port names
        """
        return [p.device for p in list_ports.comports()]

    def log_message(self, message: str, level: str = "INFO") -> None:
        """
        Centralizes logging functionality.

        Args:
            message: Message to log
            level: Log level (DEBUG, INFO, ERROR)
        """
        if level.upper() == "DEBUG":
            self.logger.debug(message)
        elif level.upper() == "INFO":
            self.logger.info(message)
        elif level.upper() == "ERROR":
            self.logger.error(message)