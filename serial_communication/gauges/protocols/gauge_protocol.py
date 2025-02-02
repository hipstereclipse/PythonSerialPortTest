"""
gauge_protocol.py

Defines the abstract base class for gauge protocols.
All gauge-specific protocol implementations inherit from this class and must implement
the methods for initializing commands, creating command frames, and parsing responses.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from serial_communication.models import GaugeCommand, GaugeResponse


class GaugeProtocol(ABC):
    """
    Abstract base class defining the interface for gauge protocols.
    """

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        self.address = address
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.rs485_mode = False
        self._command_defs = {}
        self._initialize_commands()

    @abstractmethod
    def _initialize_commands(self):
        """
        Initializes all available command definitions.
        """
        pass

    @abstractmethod
    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Creates a properly formatted command frame for the given GaugeCommand.

        Args:
            command: The GaugeCommand to send.

        Returns:
            A bytes object representing the command frame.
        """
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses raw response bytes into a structured GaugeResponse.

        Args:
            response: The raw response bytes.

        Returns:
            A GaugeResponse object.
        """
        pass

    def set_rs485_mode(self, enabled: bool) -> None:
        """
        Sets the RS485 mode flag.

        Args:
            enabled: True to enable RS485 mode, False for RS232.
        """
        self.rs485_mode = enabled

    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculates a CRC16-CCITT checksum for the given data.

        Args:
            data: The input bytes.

        Returns:
            The 16-bit checksum as an integer.
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
