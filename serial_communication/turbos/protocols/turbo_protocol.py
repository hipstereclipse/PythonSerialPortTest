#!/usr/bin/env python3
"""
turbo_protocol.py

Defines the abstract base class for turbo pump protocols.
All turbo-specific protocols must implement methods for:
  - Initializing command definitions.
  - Creating command frames.
  - Parsing responses.

This file ensures that turbo protocols share a consistent interface.
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
            address (int): The device address.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.address = address
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.rs485_mode = False
        self._command_defs = {}
        self._initialize_commands()

    @abstractmethod
    def _initialize_commands(self) -> None:
        """Loads device-specific command definitions."""
        pass

    @abstractmethod
    def create_command(self, command: Any) -> bytes:
        """
        Creates a command frame for a given turbo command.

        Args:
            command: The turbo command to serialize.

        Returns:
            bytes: The serialized command frame.
        """
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """
        Parses the raw response from the turbo controller.

        Args:
            response (bytes): The raw response bytes.

        Returns:
            dict: Parsed response data.
        """
        pass

    def calculate_crc16(self, data: bytes) -> int:
        """
        Calculates a CRC16-CCITT checksum.

        Args:
            data (bytes): The input data.

        Returns:
            int: The 16-bit checksum.
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
            enabled (bool): True for RS485, False for RS232.
        """
        self.rs485_mode = enabled
