from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import struct
import math
from .models import GaugeCommand, GaugeResponse

class GaugeProtocol(ABC):
    @abstractmethod
    def create_command(self, command: GaugeCommand) -> bytes:
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> GaugeResponse:
        pass

class PPG550Protocol(GaugeProtocol):
    """Protocol handler for PPG550 gauge - uses MKS-compatible ASCII format"""

    def __init__(self, address: int = 254):
        # Initialize with default address 254 if none provided
        self.address = address

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create command string and convert to bytes."""
        # Build the command string
        cmd = f"@{self.address}{command.name}"
        if command.command_type == "?":
            cmd += "?"
        elif command.command_type == "!" and command.parameters:
            cmd += f"!{command.parameters.get('value', '')}"
        cmd += ";FF"

        # Return as bytes
        return cmd.encode('ascii')

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse response and handle different formats."""
        try:
            # Remove @ACK and ;FF from response
            decoded = response.decode('ascii').strip()
            if decoded.startswith('@ACK'):
                decoded = decoded[4:]
            if decoded.endswith(';FF'):
                decoded = decoded[:-3]

            return GaugeResponse(
                raw_data=response,
                formatted_data=decoded,
                success=True
            )
        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=str(e)
            )

    def test_commands(self) -> list[bytes]:
        """Generate test commands for debugging."""
        # Create commands to check connection; here are examples for product name, version, etc.
        commands = [
            f"@{self.address}PRD?;FF",  # Command to get product name
            f"@{self.address}SWV?;FF",  # Command to get software version
            f"@{self.address}SER?;FF"  # Command to get serial number
        ]
        # Return commands as encoded ASCII bytes
        return [cmd.encode('ascii') for cmd in commands]

class PCG550Protocol(GaugeProtocol):
    """Protocol handler for PCG550/PSG550 gauges"""

    def __init__(self, device_id: int):
        self.device_id = device_id
        # Initialize CRC table for faster calculations
        self.crc16_tab = self._generate_crc16_table()

    def _generate_crc16_table(self):
        """Generate CRC-16 lookup table using the polynomial from the manual"""
        table = []
        for i in range(256):
            crc = 0
            c = i << 8

            for j in range(8):
                if (crc ^ c) & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc = crc << 1
                c = c << 1
                crc = crc & 0xFFFF

            table.append(crc)
        return table

    def _calculate_crc16(self, data: bytes) -> int:
        """
        Calculate CRC-16 CCITT for the command.
        Implementation matches example in manual:
        - Initial value: 0xFFFF
        - Polynomial: 0x1021
        - Input not reflected
        - Result not reflected
        """
        crc = 0xFFFF  # Initial value
        for byte in data:
            crc = ((self.crc16_tab[(crc >> 8) ^ byte]) ^ (crc << 8)) & 0xFFFF
        return crc

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create binary command according to protocol specification"""
        pid = command.parameters.get("pid", 0)
        cmd = command.parameters.get("cmd", 0)

        msg = bytearray([
            0x00,  # RS232 Address (always 0)
            0x02,  # Device ID (2 for gauge)
            0x00,  # Ack (0 for request)
            0x05,  # Message Length (5 bytes following)
            cmd,  # Command (1=read, 3=write)
            (pid >> 8) & 0xFF,  # PID MSB
            pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved
        ])

        # Calculate CRC16
        crc = self._calculate_crc16(msg)
        # Add CRC in little-endian format
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def test_commands(self) -> list[bytes]:
        """Generate test commands for debugging"""
        commands = [
            # Try reading product name first (PID 208 = 0xD0)
            bytearray([0x00, 0x02, 0x00, 0x05, 0x01, 0x00, 0xD0, 0x00, 0x00]),
            # Try reading software version (PID 218 = 0xDA)
            bytearray([0x00, 0x02, 0x00, 0x05, 0x01, 0x00, 0xDA, 0x00, 0x00]),
            # Try reading serial number (PID 207 = 0xCF)
            bytearray([0x00, 0x02, 0x00, 0x05, 0x01, 0x00, 0xCF, 0x00, 0x00])
        ]

        # Add CRC to each command
        result = []
        for cmd in commands:
            crc = self._calculate_crc16(cmd)
            cmd.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            result.append(bytes(cmd))

        return result

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse binary response from PCG550/PSG550"""
        if not response or len(response) < 6:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message="Response too short"
            )

        try:
            # Verify initial bytes
            if response[1] != 0x02:  # Should be device ID
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Invalid device ID: {response[1]:02x}"
                )

            # Extract message length from header
            msg_length = response[3]
            expected_length = msg_length + 6  # Header(4) + Payload(msg_length) + CRC(2)

            if len(response) != expected_length:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Invalid message length. Expected {expected_length}, got {len(response)}"
                )

            # Verify CRC
            data = response[:-2]
            received_crc = (response[-1] << 8) | response[-2]  # CRC is little-endian
            calculated_crc = self._calculate_crc16(data)

            if received_crc != calculated_crc:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"CRC verification failed. Expected {calculated_crc:04x}, got {received_crc:04x}"
                )

            # Extract command type and PID
            cmd_type = response[4]
            pid = (response[5] << 8) | response[6]

            # Extract payload (skip header)
            payload = response[7:-2]

            # Format based on PID
            if pid == 221:  # Pressure
                if len(payload) >= 4:
                    value = int.from_bytes(payload, byteorder='big', signed=True)
                    pressure = value / (2 ** 20)
                    formatted_data = f"{pressure:.2e} mbar"
                else:
                    formatted_data = ' '.join(f'{b:02x}' for b in payload)
            elif pid in [208, 218]:  # Product name or Software version
                try:
                    formatted_data = payload.decode('ascii').strip('\x00')
                except:
                    formatted_data = ' '.join(f'{b:02x}' for b in payload)
            else:
                formatted_data = ' '.join(f'{b:02x}' for b in payload)

            return GaugeResponse(
                raw_data=response,
                formatted_data=formatted_data,
                success=True
            )

        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=str(e)
            )


class MAGMPGProtocol(GaugeProtocol):
    """Protocol handler for MAG500/MPG500 gauges"""

    def __init__(self, device_id: int):
        self.device_id = device_id

    def test_commands(self) -> list[bytes]:
        """Generate test commands for debugging"""
        test_cmds = []

        # 1. Try to read device exception status first (PID 228 = 0xE4)
        msg1 = bytearray([
            0x00,  # Address (0 for RS232)
            self.device_id,  # Device ID (4 for MPG500, 20 for MAG500)
            0x00,  # Ack (0 for request)
            0x05,  # Message Length
            0x01,  # Command (read)
            0x00, 0xE4,  # PID for device exception
            0x00, 0x00  # Reserved
        ])
        crc = self._calculate_crc16(msg1)
        msg1.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        test_cmds.append(bytes(msg1))

        # 2. Try reading product name (PID 208 = 0xD0)
        msg2 = bytearray([
            0x00,  # Address
            self.device_id,  # Device ID
            0x00,  # Ack
            0x05,  # Message Length
            0x01,  # Command (read)
            0x00, 0xD0,  # PID for product name
            0x00, 0x00  # Reserved
        ])
        crc = self._calculate_crc16(msg2)
        msg2.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        test_cmds.append(bytes(msg2))

        # 3. Try reading pressure (PID 221 = 0xDD)
        msg3 = bytearray([
            0x00,  # Address
            self.device_id,  # Device ID
            0x00,  # Ack
            0x05,  # Message Length
            0x01,  # Command (read)
            0x00, 0xDD,  # PID for pressure
            0x00, 0x00  # Reserved
        ])
        crc = self._calculate_crc16(msg3)
        msg3.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        test_cmds.append(bytes(msg3))

        # 4. Try reading software version (PID 218 = 0xDA)
        msg4 = bytearray([
            0x00,  # Address
            self.device_id,  # Device ID
            0x00,  # Ack
            0x05,  # Message Length
            0x01,  # Command (read)
            0x00, 0xDA,  # PID for software version
            0x00, 0x00  # Reserved
        ])
        crc = self._calculate_crc16(msg4)
        msg4.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        test_cmds.append(bytes(msg4))

        # For MAG500, also try reading CCIG status
        if self.device_id == 0x14:  # MAG500
            msg5 = bytearray([
                0x00,  # Address
                self.device_id,  # Device ID
                0x00,  # Ack
                0x05,  # Message Length
                0x01,  # Command (read)
                0x02, 0x15,  # PID 533 (0x0215) for CCIG status
                0x00, 0x00  # Reserved
            ])
            crc = self._calculate_crc16(msg5)
            msg5.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            test_cmds.append(bytes(msg5))

        # For MPG500, try reading active sensor
        if self.device_id == 0x04:  # MPG500
            msg5 = bytearray([
                0x00,  # Address
                self.device_id,  # Device ID
                0x00,  # Ack
                0x05,  # Message Length
                0x01,  # Command (read)
                0x00, 0xDF,  # PID 223 (0xDF) for active sensor
                0x00, 0x00  # Reserved
            ])
            crc = self._calculate_crc16(msg5)
            msg5.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            test_cmds.append(bytes(msg5))

        return test_cmds

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create binary command according to protocol specification"""
        pid = command.parameters.get("pid", 0)
        cmd = command.parameters.get("cmd", 0)

        # For write commands with parameters
        data = b''
        if command.command_type == "!" and command.parameters.get("value") is not None:
            value = command.parameters["value"]
            if isinstance(value, bool):
                data = bytes([1 if value else 0])
            elif isinstance(value, int):
                data = value.to_bytes(4, byteorder='big', signed=True)
            elif isinstance(value, float):
                # Convert to LogFixs32en26 if needed
                if command.parameters.get("format") == "LogFixs32en26":
                    value = self._to_logfixs32en26(value)
                data = value.to_bytes(4, byteorder='big', signed=True)

        # Build message
        msg = bytearray([
            0x00,  # Address (0 for RS232)
            self.device_id,  # Device ID (4 for MPG500, 20 for MAG500)
            0x00,  # Ack (0 for request)
            0x05 + len(data),  # Message Length
            cmd,  # Command (1=read, 3=write)
            (pid >> 8) & 0xFF,  # PID MSB
            pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved
        ])

        # Add data for write commands
        if data:
            msg.extend(data)

        # Calculate CRC16
        crc = self._calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse binary response from MAG500/MPG500"""
        if not response or len(response) < 6:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message="Response too short"
            )

        try:
            # Verify device ID
            if response[1] != self.device_id:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Invalid device ID: {response[1]:02x}"
                )

            # Extract message length from header
            msg_length = response[3]
            expected_length = msg_length + 6  # Header(4) + Payload(msg_length) + CRC(2)

            if len(response) != expected_length:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Invalid message length. Expected {expected_length}, got {len(response)}"
                )

            # Verify CRC
            data = response[:-2]
            received_crc = (response[-1] << 8) | response[-2]  # CRC is little-endian
            calculated_crc = self._calculate_crc16(data)

            if received_crc != calculated_crc:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"CRC verification failed. Expected {calculated_crc:04x}, got {received_crc:04x}"
                )

            # Extract command type and PID
            cmd_type = response[4]
            pid = (response[5] << 8) | response[6]

            # Extract payload (skip header)
            payload = response[7:-2]

            # Format based on PID
            if pid == 221:  # Pressure
                if len(payload) >= 4:
                    value = int.from_bytes(payload, byteorder='big', signed=True)
                    pressure = self._from_logfixs32en26(value)
                    formatted_data = f"{pressure:.2e} mbar"
                else:
                    formatted_data = ' '.join(f'{b:02x}' for b in payload)
            elif pid == 533:  # CCIG Status
                if len(payload) >= 1:
                    status = payload[0]
                    states = {0: "Off", 1: "On (not ignited)", 3: "On and ignited"}
                    formatted_data = states.get(status, f"Unknown ({status})")
            elif pid in [208, 218]:  # Product name or Software version
                try:
                    formatted_data = payload.decode('ascii').strip('\x00')
                except:
                    formatted_data = ' '.join(f'{b:02x}' for b in payload)
            else:
                formatted_data = ' '.join(f'{b:02x}' for b in payload)

            return GaugeResponse(
                raw_data=response,
                formatted_data=formatted_data,
                success=True
            )

        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=str(e)
            )

    def _calculate_crc16(self, data: bytes) -> int:
        """Calculate CRC16 according to protocol specification"""
        crc = 0xFFFF
        for byte in data:
            crc = crc ^ (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    def _to_logfixs32en26(self, mbar_value: float) -> int:
        """Convert mbar value to LogFixs32en26 format"""
        try:
            log_value = math.log10(mbar_value)
            return int(log_value * (2 ** 26))
        except:
            return 0

    def _from_logfixs32en26(self, raw_value: int) -> float:
        """Convert LogFixs32en26 value to mbar"""
        try:
            return 10 ** (raw_value / (2 ** 26))
        except:
            return 0.0

class ASCIIProtocol(GaugeProtocol):
    def create_command(self, command: GaugeCommand) -> bytes:
        cmd = f"@254{command.name}{command.command_type}"
        if command.parameters and command.command_type == "!":
            cmd += str(command.parameters.get("value", ""))
        cmd += ";FF\r\n"
        return cmd.encode('ascii')

    def parse_response(self, response: bytes) -> GaugeResponse:
        try:
            decoded = response.decode('utf-8', errors='replace').strip()
            return GaugeResponse(
                raw_data=response,
                formatted_data=decoded,
                success=True
            )
        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=str(e)
            )

class BinaryProtocol(GaugeProtocol):
    def __init__(self, device_id: int):
        self.device_id = device_id

    def create_command(self, command: GaugeCommand) -> bytes:
        pid = command.parameters.get("pid", 0)
        cmd = command.parameters.get("cmd", 0)

        msg = bytearray([
            0x00,
            self.device_id,
            0x00,
            0x05,
            cmd,
            (pid >> 8) & 0xFF,
            pid & 0xFF,
            0x00, 0x00
        ])

        crc = self._calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        return bytes(msg)

    def _calculate_crc16(self, data: bytes) -> int:
        crc = 0xFFFF
        for byte in data:
            crc = crc ^ (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        return crc

    def parse_response(self, response: bytes) -> GaugeResponse:
        if len(response) < 7:  # Minimum length for valid response
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message="Response too short"
            )

        try:
            # Extract message length and verify
            msg_length = response[3]
            if len(response) != msg_length + 6:  # Including header and CRC
                raise ValueError("Invalid message length")

            # Verify CRC
            received_crc = (response[-1] << 8) | response[-2]
            calculated_crc = self._calculate_crc16(response[:-2])
            if received_crc != calculated_crc:
                raise ValueError("CRC verification failed")

            # Format data based on command type
            data = response[4:-2]  # Extract payload
            formatted_data = ' '.join(f'{b:02x}' for b in data)

            return GaugeResponse(
                raw_data=response,
                formatted_data=formatted_data,
                success=True
            )
        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=str(e)
            )