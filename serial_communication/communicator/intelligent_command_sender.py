#!/usr/bin/env python3
"""
intelligent_command_sender.py

This module contains the IntelligentCommandSender class which is responsible for:
  - Detecting the format of user-supplied command strings (e.g., hexadecimal, binary, decimal, ASCII).
  - Converting these strings into the appropriate byte sequence for transmission over the serial port.
  - Sending manual commands via the communicator’s serial interface.

Usage Example:
    result = IntelligentCommandSender.send_manual_command(communicator, "0xAA BB CC")
    if result["success"]:
        print("Response (formatted):", result["response_formatted"])
    else:
        print("Error:", result["error"])
"""

import time
from typing import Tuple, Dict, Any
from ..config import OUTPUT_FORMATS


class IntelligentCommandSender:
    """
    Handles detection and conversion of user command strings into byte sequences.
    """

    @staticmethod
    def detect_format(input_string: str) -> Tuple[str, str]:
        """
        Determines the format of the input command string.

        Args:
            input_string: The raw user input command.

        Returns:
            A tuple (format_type, normalized_string) where format_type is one of:
              "binary", "hex_prefixed", "hex_escaped", "decimal", "decimal_csv", "hex", or "ascii",
              and normalized_string is the input with extraneous formatting removed.
        """
        input_string = input_string.strip()
        # Binary: only 0's, 1's, and spaces.
        if all(c in '01 ' for c in input_string):
            return "binary", input_string.replace(" ", "")
        # Hexadecimal with '0x' prefix.
        if input_string.lower().startswith('0x') or ' 0x' in input_string.lower():
            return "hex_prefixed", input_string.lower().replace("0x", "").replace(" ", "")
        # Escaped hexadecimal (e.g., "\x41\x42").
        if '\\x' in input_string:
            return "hex_escaped", input_string.replace("\\x", "").replace(" ", "")
        # Space-separated decimal numbers.
        if all(part.isdigit() for part in input_string.split()):
            return "decimal", input_string
        # Comma-separated decimals.
        if ',' in input_string and all(part.strip().isdigit() for part in input_string.split(',')):
            return "decimal_csv", input_string
        # Check if valid hex string without prefix.
        if all(c in '0123456789ABCDEFabcdef ' for c in input_string):
            return "hex", input_string.replace(" ", "")
        # Default to ASCII.
        return "ascii", input_string

    @staticmethod
    def convert_to_bytes(format_type: str, input_string: str) -> bytes:
        """
        Converts the normalized input string to a byte sequence based on the detected format.

        Args:
            format_type: The detected format (e.g., "binary", "hex", etc.).
            input_string: The normalized string.

        Returns:
            A bytes object representing the command.

        Raises:
            ValueError: If the conversion fails or the format is unsupported.
        """
        try:
            if format_type == "binary":
                # Ensure the binary string length is a multiple of 8 bits.
                while len(input_string) % 8 != 0:
                    input_string += '0'
                return bytes(int(input_string[i:i+8], 2) for i in range(0, len(input_string), 8))
            elif format_type in ["hex", "hex_prefixed", "hex_escaped"]:
                return bytes.fromhex(input_string)
            elif format_type in ["decimal", "decimal_csv"]:
                if ',' in input_string:
                    numbers = [int(x.strip()) for x in input_string.split(',')]
                else:
                    numbers = [int(x) for x in input_string.split()]
                return bytes(numbers)
            elif format_type == "ascii":
                return input_string.encode('ascii')
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        except Exception as e:
            raise ValueError(f"Conversion error: {str(e)}")

    @staticmethod
    def format_output_suggestion(raw_response: bytes) -> str:
        """
        Suggests the best output format based on the content of the raw response.

        Args:
            raw_response: The raw response bytes.

        Returns:
            A string such as "ASCII" or "Hex" suggesting the best display format.
        """
        if not raw_response:
            return "Hex"
        try:
            decoded = raw_response.decode('ascii')
            if all(32 <= ord(c) <= 126 or c in '\r\n' for c in decoded):
                return "ASCII"
        except Exception:
            pass
        if any(b > 127 for b in raw_response):
            return "Hex"
        if all(b < 100 for b in raw_response):
            return "Decimal"
        return "Hex"

    @staticmethod
    def send_manual_command(communicator, input_string: str, force_format: str = None) -> Dict[str, Any]:
        """
        Interprets and sends the user-supplied command string via the communicator.

        Args:
            communicator: An instance of GaugeCommunicator.
            input_string: The command string provided by the user (e.g., "0xAA BB CC").
            force_format: If provided, forces the output format (e.g., "ASCII", "Hex").

        Returns:
            A dictionary with the following keys:
                - success: True if the command was sent and a response was received.
                - error: Any error message encountered.
                - response_raw: The raw response as a hexadecimal string.
                - response_formatted: The response formatted according to the selected output format.
                - input_format_detected: The format detected from the input.
                - rs_mode: The current RS mode from the communicator.
        """
        try:
            input_format, normalized = IntelligentCommandSender.detect_format(input_string)
            command_bytes = IntelligentCommandSender.convert_to_bytes(input_format, normalized)
            result: Dict[str, Any] = {
                "input_format_detected": input_format,
                "success": False,
                "error": None,
                "response_formatted": None,
                "response_raw": None,
                "rs_mode": communicator.rs_mode
            }
            if communicator.ser and communicator.ser.is_open:
                # Clear buffers before sending.
                communicator.ser.reset_input_buffer()
                communicator.ser.reset_output_buffer()
                # For RS485, adjust RTS settings if applicable.
                if communicator.rs_mode == "RS485":
                    if hasattr(communicator.ser, 'rs485_mode'):
                        communicator.ser.rs485_mode = communicator.rs485_config
                    communicator.ser.setRTS(communicator.rts_level_for_tx)
                    time.sleep(communicator.rts_delay_before_tx)
                communicator.ser.write(command_bytes)
                communicator.ser.flush()
                if communicator.rs_mode == "RS485":
                    communicator.ser.setRTS(communicator.rts_level_for_rx)
                    time.sleep(communicator.rts_delay_before_rx)
                time.sleep(communicator.rts_delay)
                response = communicator.read_response()
                if response:
                    suggested_format = force_format or communicator.output_format
                    communicator.set_output_format(suggested_format)
                    result.update({
                        "success": True,
                        "response_raw": response.hex(),
                        "response_formatted": communicator.format_response(response)
                    })
                else:
                    result["error"] = "No response received"
            else:
                result["error"] = "Port not open"
            return result
        except Exception as e:
            communicator.logger.error(f"Manual command failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response_formatted": None,
                "response_raw": None
            }
