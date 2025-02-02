"""
base_communication.py

Implements the BaseCommunicationHandler class that provides core serial communication functionality.
Handles connection setup, sending commands, reading responses, and error handling.
"""

import logging
from typing import Optional, Dict, Any, List
import serial
from serial.tools import list_ports
import time


class BaseCommunicationHandler:
    """
    Base class for serial communication handlers.
    """

    def __init__(self, port: str, device_type: str, logger: Optional[logging.Logger] = None):
        """
        Initializes the communication handler.

        Args:
            port: The serial port identifier (e.g., "COM1").
            device_type: A string identifying the device type.
            logger: Optional logger instance.
        """
        self.port = port
        self.device_type = device_type
        self.logger = logger or logging.getLogger(__name__)
        self.ser: Optional[serial.Serial] = None
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
        Establishes the serial connection with the current settings.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            self.ser = serial.Serial(port=self.port, **self.current_settings)
            self.logger.info(f"Connected to {self.device_type} on {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        Safely closes the serial connection.

        Returns:
            True if disconnected successfully, False otherwise.
        """
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.logger.info(f"Disconnected from {self.device_type}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error disconnecting: {str(e)}")
            return False

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Updates the serial connection settings.

        Args:
            settings: Dictionary of serial parameters to update.

        Returns:
            True if the settings were applied successfully, False otherwise.
        """
        try:
            self.current_settings.update(settings)
            if self.ser and self.ser.is_open:
                for key, value in settings.items():
                    setattr(self.ser, key, value)
                self.logger.info(f"Serial settings updated: {settings}")
                return True
        except Exception as e:
            self.logger.error(f"Failed to update settings: {str(e)}")
        return False

    def send_command(self, command: bytes) -> Optional[bytes]:
        """
        Sends raw command bytes to the device and returns the response.

        Args:
            command: The raw command bytes.

        Returns:
            The response bytes if successful, None otherwise.
        """
        try:
            if not self.ser or not self.ser.is_open:
                raise Exception("Not connected")
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.logger.debug(f"Sending command: {command.hex(' ')}")
            self.ser.write(command)
            self.ser.flush()
            response = self.read_response()
            if response:
                self.logger.debug(f"Received response: {response.hex(' ')}")
                return response
            return None
        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            return None

    def read_response(self) -> Optional[bytes]:
        """
        Reads response bytes from the device, within the timeout period.

        Returns:
            The response bytes if available, otherwise None.
        """
        try:
            if not self.ser:
                return None
            response = bytearray()
            start_time = time.time()
            while (time.time() - start_time) < self.current_settings['timeout']:
                if self.ser.in_waiting:
                    response.extend(self.ser.read(self.ser.in_waiting))
                    if response:
                        return bytes(response)
                time.sleep(0.01)
            return bytes(response) if response else None
        except Exception as e:
            self.logger.error(f"Read failed: {str(e)}")
            return None

    @staticmethod
    def list_ports() -> List[str]:
        """
        Lists available serial ports.

        Returns:
            A list of available port names.
        """
        return [p.device for p in list_ports.comports()]

    def log_message(self, message: str, level: str = "INFO") -> None:
        """
        Centralizes logging of messages.

        Args:
            message: The message to log.
            level: The logging level ("DEBUG", "INFO", "ERROR").
        """
        if level.upper() == "DEBUG":
            self.logger.debug(message)
        elif level.upper() == "ERROR":
            self.logger.error(message)
        else:
            self.logger.info(message)
