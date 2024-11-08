from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
import struct
import math
import binascii

from .config import GAUGE_PARAMETERS
from .models import GaugeCommand, GaugeResponse


class GaugeProtocol(ABC):
    @abstractmethod
    def create_command(self, command: GaugeCommand) -> bytes:
        pass

    @abstractmethod
    def parse_response(self, response: bytes) -> GaugeResponse:
        pass

    @abstractmethod
    def test_commands(self) -> List[bytes]:
        pass

class CDGProtocol(GaugeProtocol):
    """Protocol handler for INFICON CDG gauges - 9-byte send string, 5-byte receipt string"""

    def __init__(self):
        self.service_commands = {
            'read': 0x00,
            'write': 0x10,
            'special': 0x40
        }

        self.variables = {
            'data_tx_mode': 0x00,
            'unit': 0x01,
            'filter': 0x02,
            'sp1_level_low_h': 0x04,
            'sp1_level_low_l': 0x05,
            'sp2_level_low_h': 0x06,
            'sp2_level_low_l': 0x07,
            'sp1_level_high_h': 0x08,
            'sp1_level_high_l': 0x09,
            'sp2_level_high_h': 0x0A,
            'sp2_level_high_l': 0x0B,
            'software_version': 0x10,
            'zero_adjust_value_h': 0x15,
            'zero_adjust_value_l': 0x16,
            'dc_output_offset_h': 0x17,
            'dc_output_offset_l': 0x18,
            'extended_error_h': 0x36,
            'extended_error_l': 0x37,
            'pressure_range_exp': 0x38,
            'pressure_range_mantissa': 0x39,
            'gauge_config': 0x3A,
            'cdg_type': 0x3B
        }

        self.special_commands = {
            'reset': (0x00, 0x00),
            'factory_reset': (0x01, 0x00),
            'zero_adjust': (0x02, 0x00)
        }

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create a 5-byte receipt string command"""
        if command.command_type == "special":
            # Handle special commands (reset, factory reset, zero adjust)
            addr, data = self.special_commands.get(command.name, (0, 0))
            cmd_type = self.service_commands['special']
        elif command.command_type == "!":
            # Handle write commands
            addr = self.variables.get(command.name, 0)
            data = command.parameters.get("value", 0)
            cmd_type = self.service_commands['write']
        else:
            # Handle read commands
            addr = self.variables.get(command.name, 0)
            data = 0
            cmd_type = self.service_commands['read']

        # Build 5-byte receipt string
        msg = bytearray([
            0x03,  # Byte 0: Fixed length (3)
            cmd_type,  # Byte 1: Service command
            addr,  # Byte 2: Address byte
            data,  # Byte 3: Data byte
            0x00  # Byte 4: Will be filled with checksum
        ])

        # Calculate checksum (sum of bytes 1-3)
        checksum = sum(msg[1:4]) & 0xFF
        msg[4] = checksum

        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse the 9-byte send string response"""
        if not response or len(response) != 9:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=f"Invalid response length: expected 9, got {len(response) if response else 0}"
            )

        try:
            # Verify response format
            if response[0] != 0x07:  # First byte must be 7
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message="Invalid start byte"
                )

            # Extract fields
            page_no = response[1]
            status = response[2]
            error = response[3]
            pressure_high = response[4]
            pressure_low = response[5]
            read_value = response[6]
            sensor_type = response[7]
            checksum = response[8]

            # Verify checksum
            calc_checksum = sum(response[1:8]) & 0xFF
            if calc_checksum != checksum:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Checksum mismatch: expected {checksum:02x}, got {calc_checksum:02x}"
                )

            # Parse status byte
            pressure_unit = (status >> 4) & 0x03
            unit_str = {0: "mbar", 1: "Torr", 2: "Pa"}.get(pressure_unit, "unknown")

            # Calculate pressure value
            pressure_value = (pressure_high << 8) | pressure_low
            if pressure_value & 0x8000:  # Handle negative values
                pressure_value = -((~pressure_value + 1) & 0xFFFF)

            # Format pressure in scientific notation with 2 decimal places
            pressure = pressure_value / 16384.0  # Scale factor for CDG
            formatted_pressure = f"{pressure:.2e} {unit_str}"

            # Format full response
            formatted_data = {
                "pressure": formatted_pressure,
                "status": {
                    "unit": unit_str,
                    "heating": bool(status & 0x80),
                    "temp_ok": bool(status & 0x40),
                    "emission": bool(status & 0x20)
                },
                "errors": self._parse_error_byte(error)
            }

            return GaugeResponse(
                raw_data=response,
                formatted_data=str(formatted_data),
                success=True
            )

        except Exception as e:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message=f"Parse error: {str(e)}"
            )

    def _parse_error_byte(self, error: int) -> dict:
        """Parse the error byte into human-readable format"""
        return {
            "rs232_sync_error": bool(error & 0x01),
            "syntax_error": bool(error & 0x02),
            "invalid_read_cmd": bool(error & 0x04),
            "sp1_status": bool(error & 0x08),
            "sp2_status": bool(error & 0x10),
            "extended_error": bool(error & 0x80)
        }

    def test_commands(self) -> List[bytes]:
        """Generate test commands for initial connection"""
        commands = [
            # Read software version
            bytearray([0x03, 0x00, 0x10, 0x00, 0x10]),  # Checksum = 0x10
            # Read pressure unit
            bytearray([0x03, 0x00, 0x01, 0x00, 0x01]),  # Checksum = 0x01
            # Read gauge type
            bytearray([0x03, 0x00, 0x3B, 0x00, 0x3B])  # Checksum = 0x3B
        ]
        return [bytes(cmd) for cmd in commands]

    def create_command_from_config(self, gauge_name: str, command_name: str) -> bytes:
        """Create a command using the configuration settings for the given gauge."""
        config = GAUGE_PARAMETERS.get(gauge_name, {})
        command_details = config.get("commands", {}).get(command_name, {})
        cmd_type = command_details.get("cmd")
        cmd_name = command_details.get("name", "")

        # Handle special or standard commands accordingly
        if cmd_type == "special":
            return self.create_quick_command(cmd_name)  # You can reuse your quick command logic here

        # Adjust further for read/write types if needed
        return self.create_command(GaugeCommand(
            name=cmd_name,
            command_type="read" if cmd_type == "read" else "write",
            parameters={"value": 0}  # Adjust as needed based on your command logic
        ))


class PPG550Protocol(GaugeProtocol):
    """Protocol handler for PPG550 gauge - MKS ASCII protocol"""

    def __init__(self, address: int = 254):
        self.address = address

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create ASCII command string per PPG550 spec"""
        cmd = f"@{self.address:03d}{command.name}"

        if command.command_type == "?":
            cmd += "?"
        elif command.command_type == "!" and command.parameters:
            value = command.parameters.get("value", "")
            if isinstance(value, (int, float)):
                cmd += f"!{value:.2e}"
            else:
                cmd += f"!{value}"

        cmd += ";FF\r\n"
        return cmd.encode('ascii')

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse ASCII response from PPG550"""
        try:
            # Decode and validate basic format
            decoded = response.decode('ascii').strip()
            if not decoded.startswith('@') or not decoded.endswith(';FF'):
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message="Invalid response format"
                )

            # Remove framing
            if decoded.startswith('@ACK'):
                decoded = decoded[4:]
            elif decoded.startswith('@NAK'):
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Command failed: {decoded[4:]}"
                )

            if decoded.endswith(';FF'):
                decoded = decoded[:-3]

            # Handle special response formats
            if ',' in decoded:  # Multi-value response
                values = decoded.split(',')
                formatted_data = ', '.join(values)
            else:
                formatted_data = decoded.strip()

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

    def test_commands(self) -> List[bytes]:
        """Generate PPG550 test commands for initial connection"""
        commands = [
            # Product name query
            f"@{self.address:03d}PRD?;FF\r\n",
            # Software version
            f"@{self.address:03d}SWV?;FF\r\n",
            # Serial number
            f"@{self.address:03d}SER?;FF\r\n",
            # Combined pressure reading
            f"@{self.address:03d}PR3?;FF\r\n"
        ]
        return [cmd.encode('ascii') for cmd in commands]


class PCG550Protocol(GaugeProtocol):
    """Protocol handler for PCG550 gauge - RS232C binary format"""

    def __init__(self, device_id: int = 0x02):
        self.device_id = device_id
        self.crc16_tab = self._generate_crc16_table()

    def _generate_crc16_table(self) -> List[int]:
        """Generate CRC-16 lookup table with polynomial 0x1021"""
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
        """Calculate CRC-16 CCITT (0x1021 polynomial)"""
        crc = 0xFFFF
        for byte in data:
            crc = ((self.crc16_tab[(crc >> 8) ^ byte]) ^ (crc << 8)) & 0xFFFF
        return crc

    def create_command(self, command: GaugeCommand) -> bytes:
        """Create binary command for PCG550"""
        pid = command.parameters.get("pid", 0)
        cmd_type = 1 if command.command_type == "?" else 3

        # Create message frame
        msg = bytearray([
            0x00,  # RS232 Address (always 0)
            self.device_id,  # Device ID (2 for PCG550)
            0x00,  # Ack (0 for request)
            0x05,  # Message Length (5 bytes following)
            cmd_type,  # Command type (1=read, 3=write)
            (pid >> 8) & 0xFF,  # PID MSB
            pid & 0xFF,  # PID LSB
            0x00, 0x00  # Reserved bytes
        ])

        # Calculate and append CRC
        crc = self._calculate_crc16(msg)
        msg.extend([crc & 0xFF, (crc >> 8) & 0xFF])  # Little endian CRC

        return bytes(msg)

    def parse_response(self, response: bytes) -> GaugeResponse:
        """Parse binary response from PCG550"""
        if not response or len(response) < 6:
            return GaugeResponse(
                raw_data=response,
                formatted_data="",
                success=False,
                error_message="Response too short"
            )

        try:
            # Verify device ID and message format
            if response[1] != self.device_id:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"Invalid device ID: {response[1]:02x}"
                )

            msg_length = response[3]
            expected_length = msg_length + 6

            # Verify CRC
            data = response[:-2]
            received_crc = (response[-1] << 8) | response[-2]
            calculated_crc = self._calculate_crc16(data)

            if received_crc != calculated_crc:
                return GaugeResponse(
                    raw_data=response,
                    formatted_data="",
                    success=False,
                    error_message=f"CRC check failed: expected {calculated_crc:04x}, got {received_crc:04x}"
                )

            # Extract command type and PID
            cmd_type = response[4]
            pid = (response[5] << 8) | response[6]
            payload = response[7:-2]

            # Format based on PID
            if pid == 221:  # Pressure
                value = int.from_bytes(payload, byteorder='big', signed=True)
                pressure = value / (2 ** 20)  # Fixs32en20 format
                formatted_data = f"{pressure:.2e} mbar"
            elif pid == 222:  # Temperature
                value = int.from_bytes(payload, byteorder='big', signed=True)
                temp = value / (2 ** 20)
                formatted_data = f"{temp:.1f}°C"
            elif pid == 207:  # Serial number
                formatted_data = str(int.from_bytes(payload, byteorder='big'))
            elif pid in [208, 218]:  # Product name/version
                formatted_data = payload.decode('ascii').strip('\x00')
            elif pid == 228:  # Device errors
                error_code = int.from_bytes(payload, byteorder='big')
                formatted_data = f"Error code: {error_code}"
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
                error_message=f"Parse error: {str(e)}"
            )

    def test_commands(self) -> List[bytes]:
        """Generate PCG550 test commands for initial connection"""
        cmds = [
            # Try product name first (PID 208)
            bytearray([
                0x00,  # RS232 Address (always 0)
                self.device_id,  # Device ID (2 for gauge)
                0x00,  # Ack (0 for request)
                0x05,  # Message Length (5 bytes following)
                0x01,  # Command type (read)
                0x00, 0xD0,  # PID 208 (0xD0) - product name
                0x00, 0x00  # Reserved
            ]),
            # Try software version (PID 218)
            bytearray([
                0x00, self.device_id, 0x00, 0x05, 0x01,
                0x00, 0xDA,  # PID 218 (0xDA) - software version
                0x00, 0x00
            ]),
            # Try reading pressure (PID 221)
            bytearray([
                0x00, self.device_id, 0x00, 0x05, 0x01,
                0x00, 0xDD,  # PID 221 (0xDD) - pressure
                0x00, 0x00
            ])
        ]

        # Add CRC to each command
        result = []
        for cmd in cmds:
            crc = self._calculate_crc16(cmd)
            cmd_with_crc = bytearray(cmd)
            cmd_with_crc.extend([crc & 0xFF, (crc >> 8) & 0xFF])  # Little-endian CRC
            result.append(bytes(cmd_with_crc))

        return result


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