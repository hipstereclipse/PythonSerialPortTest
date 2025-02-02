"""
turbo_protocol.py

Defines the abstract base class for turbo pump protocols.
All turbo-specific protocols inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import logging


class TurboProtocol(ABC):
    """
    Abstract base class defining the interface for turbo pump protocols.
    """

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        """
        Initializes the TurboProtocol.

        Args:
            address: The device address.
            logger: Optional logger.
        """
        self.address = address
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.rs485_mode = False
        self._command_defs = {}
        self._initialize_commands()

    @abstractmethod
    def _initialize_commands(self):
        """Loads device-specific command definitions."""
        pass

    @abstractmethod
    def create_command(self, command: Any) -> bytes:
        """
        Creates the device-specific command bytes.

        Args:
            command: The turbo command.

        Returns:
            The raw command bytes.
        """
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """
        Parses the raw response bytes into structured data.

        Args:
            response: The raw response bytes.

        Returns:
            A dictionary of parsed response data.
        """
        pass

    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculates a CRC16-CCITT checksum.

        Args:
            data: The input bytes.

        Returns:
            The CRC16 checksum as an integer.
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

    def set_rs485_mode(self, enabled: bool) -> None:
        """
        Enables or disables RS485 mode.

        Args:
            enabled: True for RS485, False for RS232.
        """
        self.rs485_mode = enabled
