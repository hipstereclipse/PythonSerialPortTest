"""
response_handler.py

Defines the ResponseHandler class for converting raw gauge response bytes
into human-readable strings according to various output formats.
"""

from ..models import GaugeResponse


class ResponseHandler:
    """
    Formats and processes raw responses from gauges.
    """

    def __init__(self, output_format: str = "ASCII"):
        """
        Initializes the ResponseHandler.

        Args:
            output_format: The default output format (e.g., "ASCII", "Hex").
        """
        self.output_format = output_format

    def format_response(self, response: bytes) -> str:
        """
        Converts raw bytes to a formatted string according to the output format.

        Args:
            response: The raw response bytes.

        Returns:
            A formatted string representation.
        """
        if not response:
            return "No response"
        try:
            if self.output_format == "Hex":
                return ' '.join(f'{byte:02x}' for byte in response)
            elif self.output_format == "Binary":
                return ' '.join(f'{byte:08b}' for byte in response)
            elif self.output_format == "ASCII":
                return response.decode('ascii', errors='replace')
            elif self.output_format == "UTF-8":
                return response.decode('utf-8', errors='replace')
            elif self.output_format == "Decimal":
                return ' '.join(str(byte) for byte in response)
            else:
                return str(response)
        except Exception as e:
            return f"Error formatting response: {str(e)}"

    def suggest_format(self, raw_response: bytes) -> str:
        """
        Suggests the best output format for the given raw response.

        Args:
            raw_response: The raw response bytes.

        Returns:
            A string indicating the suggested format.
        """
        if not raw_response:
            return "Hex"
        try:
            decoded = raw_response.decode('ascii')
            if all(32 <= ord(c) <= 126 or c in '\r\n' for c in decoded):
                return "ASCII"
        except:
            pass
        if any(b > 127 for b in raw_response):
            return "Hex"
        if all(b < 100 for b in raw_response):
            return "Decimal"
        return "Hex"

    def set_output_format(self, format_type: str) -> None:
        """
        Updates the output format.

        Args:
            format_type: The new output format to use.
        """
        self.output_format = format_type

    def process_cdg_frame(self, response: bytes) -> dict:
        """
        Processes a 9-byte CDG frame and returns a dictionary with parsed values.

        Args:
            response: The 9-byte frame from a CDG gauge.

        Returns:
            A dictionary with parsed data or an error message.
        """
        if len(response) != 9:
            return {"error": "Invalid frame length"}
        try:
            return {
                "start_byte": response[0],
                "page_no": response[1],
                "status": {
                    "unit": (response[2] >> 4) & 0x03,
                    "heating": bool(response[2] & 0x80),
                    "temp_ok": bool(response[2] & 0x40),
                    "emission": bool(response[2] & 0x20),
                },
                "error": response[3],
                "pressure": self._calculate_cdg_pressure(response[4], response[5]),
                "read_value": response[6],
                "sensor_type": response[7],
                "checksum": response[8],
                "checksum_valid": self._verify_cdg_checksum(response),
            }
        except Exception as e:
            return {"error": f"Frame processing error: {str(e)}"}

    def _calculate_cdg_pressure(self, high_byte: int, low_byte: int) -> float:
        """
        Calculates pressure from two bytes using fixed-point arithmetic.

        Args:
            high_byte: The high byte.
            low_byte: The low byte.

        Returns:
            The calculated pressure as a float.
        """
        pressure_value = (high_byte << 8) | low_byte
        if pressure_value & 0x8000:
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        return pressure_value / 16384.0

    def _verify_cdg_checksum(self, frame: bytes) -> bool:
        """
        Verifies the checksum of a 9-byte CDG frame.

        Args:
            frame: The 9-byte frame.

        Returns:
            True if the checksum is valid, False otherwise.
        """
        if len(frame) != 9:
            return False
        calc_checksum = sum(frame[1:8]) & 0xFF
        return calc_checksum == frame[8]

    def parse_ppg_response(self, response: bytes) -> dict:
        """
        Parses an ASCII response from a PPG gauge.

        Args:
            response: The raw response bytes.

        Returns:
            A dictionary with the parsed data or an error.
        """
        try:
            decoded = response.decode('ascii', errors='replace').strip()
            if not decoded.startswith('@') or not decoded.endswith(';FF'):
                return {"error": "Invalid response format"}
            if decoded.startswith('@ACK'):
                data = decoded[4:-3]
            elif decoded.startswith('@NAK'):
                return {"error": f"Command failed: {decoded[4:-3]}"}
            else:
                data = decoded[1:-3]
            return {
                "data": data,
                "values": data.split(',') if ',' in data else [data]
            }
        except Exception as e:
            return {"error": f"Parse error: {str(e)}"}

    def create_gauge_response(
        self,
        raw_data: bytes,
        formatted_data: str = "",
        success: bool = True,
        error_message: str = None
    ) -> GaugeResponse:
        """
        Creates a standardized GaugeResponse object.

        Args:
            raw_data: The raw response bytes.
            formatted_data: An optional preformatted response string.
            success: True if the command was successful.
            error_message: An error message if not successful.

        Returns:
            A GaugeResponse instance.
        """
        return GaugeResponse(
            raw_data=raw_data,
            formatted_data=formatted_data or self.format_response(raw_data),
            success=success,
            error_message=error_message
        )
