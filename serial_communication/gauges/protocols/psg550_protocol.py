#!/usr/bin/env python3
"""
psg550_protocol.py

Implements the protocol for PSG550 Pirani/Piezo combination gauges.
This protocol uses a binary structure similar to the PCG protocol.
"""

import struct
from typing import Dict, Any, Optional

from serial_communication.gauges.protocols.gauge_protocol import GaugeProtocol
from serial_communication.models import GaugeCommand
from serial_communication.param_types import CommandDefinition, ParamType

class PSG550Protocol(GaugeProtocol):
    """
    Protocol implementation for PSG550 gauges.
    """

    def __init__(self, address: int = 254, logger: Optional[Any] = None):
        super().__init__(address, logger)
        self.device_id = 0x02  # Device ID for PSG550

    def _initialize_commands(self) -> None:
        """
        Initializes command definitions for PSG550 gauges.
        """
        self._command_defs = {
            "pressure": CommandDefinition(
                pid=221,
                name="pressure",
                description="Read pressure measurement (Fixs32en20)",
                read=True,
                write=False,
                continuous=True
            ),
            "temperature": CommandDefinition(
                pid=222,
                name="temperature",
                description="Read sensor temperature",
                read=True,
                write=False
            ),
            "software_version": CommandDefinition(
                pid=218,
                name="software_version",
                description="Read software version",
                read=True,
                write=False
            ),
            "serial_number": CommandDefinition(
                pid=207,
                name="serial_number",
                description="Read serial number",
                read=True,
                write=False
            ),
            "error_status": CommandDefinition(
                pid=228,
                name="error_status",
                description="Read error status",
                read=True,
                write=False
            ),
            "pirani_full_scale": CommandDefinition(
                pid=33000,
                name="pirani_full_scale",
                description="Read Pirani full scale",
                read=True,
                write=False
            ),
            "pirani_adjust": CommandDefinition(
                pid=417,
                name="pirani_adjust",
                description="Perform Pirani adjustment",
                read=False,
                write=True
            )
        }

    def create_command(self, command: GaugeCommand) -> bytes:
        """
        Constructs a binary command frame for PSG550 gauges.

        Returns:
            bytes: The command frame.
        """
        cmd_def = self._command_defs.get(command.name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command.name}")
        msg = bytearray([
            0x00 if not self.rs485_mode else self.address,
            self.device_id,
            0x00,
            0x05,
            0x01 if cmd_def.read else 0x03,
            (cmd_def.pid >> 8) & 0xFF,
            cmd_def.pid & 0xFF,
            0x00, 0x00
        ])
        if command.command_type == "!" and command.parameters and cmd_def.write:
            value = command.parameters.get("value", 0)
            msg.extend([int(value) & 0xFF])
            msg[3] = len(msg) - 4
        crc = self.calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        return bytes(msg)

    def parse_response(self, response: bytes) -> Dict[str, Any]:
        """
        Parses the binary response from a PSG550 gauge.

        Returns:
            dict: A dictionary containing the parsed response.
        """
        if len(response) < 7:
            return {"success": False, "error": "Response too short", "raw_data": response, "formatted_data": ""}
        device_id = response[1]
        msg_length = response[3]
        if device_id != self.device_id:
            return {"success": False, "error": "Invalid device ID", "raw_data": response, "formatted_data": ""}
        if len(response) != msg_length + 6:
            return {"success": False, "error": "Invalid message length", "raw_data": response, "formatted_data": ""}
        received_crc = (response[-1] << 8) | response[-2]
        calculated_crc = self.calculate_crc16(response[:-2])
        if received_crc != calculated_crc:
            return {"success": False, "error": "CRC mismatch", "raw_data": response, "formatted_data": ""}
        data = response[7:-2]
        return {"success": True, "raw_data": data.hex(' ').upper()}
