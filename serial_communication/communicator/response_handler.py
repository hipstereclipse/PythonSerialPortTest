"""
response_handler.py
Defines the ResponseHandler class for formatting and processing gauge responses.
"""

from ..models import GaugeResponse


class ResponseHandler:
    """
    Handles formatting and processing of all gauge responses, including suggestions
    for output formats or specialized parsing for certain protocols.
    """

    def __init__(self, output_format: str = "ASCII"):
        self.output_format = output_format

    def format_response(self, response: bytes) -> str:
        """Format response according to selected output format."""
        if not response:
            return "No response"

        try:
            if self.output_format == "Hex":
                return ' '.join(f'{byte:02x}' for byte in response)
            elif self.output_format == "Binary":
                return ' '.join(f'{bin(byte)[2:].zfill(8)}' for byte in response)
            elif self.output_format == "ASCII":
                return response.decode('ascii', errors='replace')
            elif self.output_format == "UTF-8":
                return response.decode('utf-8', errors='replace')
            elif self.output_format == "Decimal":
                return ' '.join(str(byte) for byte in response)
            else:  # Raw Bytes
                return str(response)
        except Exception as e:
            return f"Error formatting response: {str(e)}"

    def suggest_format(self, raw_response: bytes) -> str:
        """Suggest the best output format based on the response content."""
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

    def set_output_format(self, format_type: str):
        """Update the output format."""
        self.output_format = format_type

    def process_cdg_frame(self, response: bytes) -> dict:
        """
        Process CDG gauge specific 9-byte frame format. Return a dictionary with
        parsed values or an error message.
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
        """Calculate pressure value from two bytes for a CDG gauge."""
        pressure_value = (high_byte << 8) | low_byte
        if pressure_value & 0x8000:
            pressure_value = -((~pressure_value + 1) & 0xFFFF)
        return pressure_value / 16384.0

    def _verify_cdg_checksum(self, frame: bytes) -> bool:
        if len(frame) != 9:
            return False
        calc_checksum = sum(frame[1:8]) & 0xFF
        return calc_checksum == frame[8]

    def parse_ppg_response(self, response: bytes) -> dict:
        """Parse PPG gauge ASCII response format."""
        try:
            decoded = response.decode('ascii').strip()
            if not decoded.startswith('@') or not decoded.endswith(';FF'):
                return {"error": "Invalid response format"}

            if decoded.startswith('@ACK'):
                data = decoded[4:-3]  # remove @ACK and ;FF
            elif decoded.startswith('@NAK'):
                return {"error": f"Command failed: {decoded[4:-3]}"}
            else:
                data = decoded[1:-3]  # remove @ and ;FF

            return {
                "data": data,
                "values": data.split(',') if ',' in data else [data]
            }
        except Exception as e:
            return {"error": f"Parse error: {str(e)}"}

    def create_gauge_response(self, raw_data: bytes, formatted_data: str = "",
                              success: bool = True, error_message: str = None) -> GaugeResponse:
        """Create a standardized GaugeResponse object."""
        return GaugeResponse(
            raw_data=raw_data,
            formatted_data=formatted_data or self.format_response(raw_data),
            success=success,
            error_message=error_message
        )
