"""
Provides the abstract base class for gauge protocols and common utility functions.
All gauge-specific protocol implementations will inherit from GaugeProtocol.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from serial_communication.models import GaugeCommand, GaugeResponse


class GaugeProtocol(ABC):
    """
    Defines the basic interface that all gauge protocols must implement.
    Each gauge protocol must provide ways to initialize, create commands,
    and parse responses.
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
        Initializes all relevant command definitions for the gauge.
        """
        pass

    @abstractmethod
    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Creates and returns the command bytes for the given GaugeCommand object.
        """
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses raw response bytes from the gauge into a structured GaugeResponse.
        """
        pass

    def set_rs485_mode(self, enabled: bool):
        """
        Enables or disables RS485 mode for the gauge.
        """
        self.rs485_mode = enabled

    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculates a CRC16 with the CCITT polynomial.
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
