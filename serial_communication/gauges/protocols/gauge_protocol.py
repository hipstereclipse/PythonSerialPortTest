#!/usr/bin/env python3
"""
gauge_protocol.py

This module defines the abstract base class for gauge protocols. All gauge-specific
protocol implementations must inherit from this class and implement methods for:
  - Initializing command definitions.
  - Creating command frames.
  - Parsing responses from the gauge.

It also provides common utility functions, such as CRC16 checksum calculation.

Usage Example:
    protocol = SomeGaugeProtocol(address=254)
    cmd = GaugeCommand(name="pressure", command_type="?")
    command_bytes = protocol.create_command(cmd)
    response = protocol.parse_response(received_bytes)
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from serial_communication.models import GaugeCommand, GaugeResponse


class GaugeProtocol(ABC):
    """
    Abstract base class for gauge protocols.
    Provides a standardized interface for creating command frames and parsing responses.
    """

    def __init__(self, address: int = 254, logger: Optional[logging.Logger] = None):
        """
        Initializes the GaugeProtocol.

        Args:
            address (int): The device address (default: 254).
            logger (Optional[logging.Logger]): A logger instance for debugging.
        """
        self.address = address
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.rs485_mode = False  # Indicates if RS485 mode is enabled.
        self._command_defs = {}  # Dictionary of command definitions.
        self._initialize_commands()

    @abstractmethod
    def _initialize_commands(self) -> None:
        """
        Initializes command definitions specific to this protocol.
        Subclasses must populate the _command_defs dictionary.
        """
        pass

    @abstractmethod
    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Creates a serialized command frame for a given GaugeCommand.

        Args:
            command (GaugeCommand): The command to serialize.

        Returns:
            bytes: The command frame ready for transmission.
        """
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> GaugeResponse:
        """
        Parses raw response bytes into a structured GaugeResponse.

        Args:
            response (bytes): The raw response from the gauge.

        Returns:
            GaugeResponse: The parsed response.
        """
        pass

    def set_rs485_mode(self, enabled: bool) -> None:
        """
        Sets whether RS485 mode is active.

        Args:
            enabled (bool): True for RS485 mode; False for RS232.
        """
        self.rs485_mode = enabled

    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculates a CRC16-CCITT checksum for the provided data.

        Args:
            data (bytes): The input data.

        Returns:
            int: The 16-bit CRC checksum.
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
