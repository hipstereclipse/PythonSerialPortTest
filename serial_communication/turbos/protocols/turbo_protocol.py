# serial_communication/turbos/protocols/turbo_protocol.py

"""
Base protocol class for turbo pump controllers.
Defines standard interface that all turbo protocols must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import logging


class TurboProtocol(ABC):
    """
    Abstract base class defining interface for turbo pump protocols.
    All turbo-specific protocols inherit from this class.
    """

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        """
        Initializes base protocol with address and logger.

        Args:
            address: Device address (default 254)
            logger: Optional logger for output messages
        """
        # Stores device address
        self.address = address

        # Creates or stores logger instance
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        # Tracks if operating in RS485 mode
        self.rs485_mode = False

        # Command definitions populated by subclasses
        self._command_defs = {}

        # Loads device-specific commands
        self._initialize_commands()

    @abstractmethod
    def _initialize_commands(self):
        """Loads device-specific command definitions - implemented by subclasses"""
        pass

    @abstractmethod
    def create_command(self, command: Any) -> bytes:
        """
        Creates device-specific command bytes.

        Args:
            command: Command to send

        Returns:
            bytes: Raw command bytes to send
        """
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """
        Parses device response into structured data.

        Args:
            response: Raw response bytes

        Returns:
            dict: Parsed response data
        """
        pass

    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculates CRC16-CCITT checksum.
        Used by most turbo protocols for message validation.

        Args:
            data: Input bytes for CRC calculation

        Returns:
            int: 16-bit CRC value
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
            crc &= 0xFFFF
        return crc

    def set_rs485_mode(self, enabled: bool):
        """
        Enables or disables RS485 mode.

        Args:
            enabled: Whether to enable RS485 mode
        """
        self.rs485_mode = enabled