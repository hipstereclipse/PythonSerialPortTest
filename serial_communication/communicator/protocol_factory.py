"""
protocol_factory.py

Provides a factory function to instantiate the appropriate gauge protocol
class based on the given gauge type. This abstraction decouples device-specific
logic from the rest of the code.
"""

# Import protocol classes from the gauges package.
from serial_communication.gauges.protocols.cdg_protocol import CDGProtocol
from serial_communication.gauges.protocols.magmpg_protocol import MAGMPGProtocol
from serial_communication.gauges.protocols.pcg_protocol import PCGProtocol
from serial_communication.gauges.protocols.ppg_protocol import PPGProtocol
from serial_communication.gauges.protocols.bcg450_protocol import BCG450Protocol
from serial_communication.gauges.protocols.bcg552_protocol import BCG552Protocol
from serial_communication.gauges.protocols.bpg40x_protocol import BPG40xProtocol
from serial_communication.gauges.protocols.bpg552_protocol import BPG552Protocol
from serial_communication.turbos.protocols.tc600_protocol import TC600Protocol


def get_protocol(gauge_type: str, params: dict):
    """
    Returns an instance of the appropriate protocol class for the given gauge type.

    Args:
        gauge_type: A string representing the gauge model (e.g., "PPG550").
        params: A dictionary of parameters from the configuration.

    Returns:
        An instance of a subclass of GaugeProtocol.

    Raises:
        ValueError: If the gauge type is unsupported.
    """
    if gauge_type in ["PPG550", "PPG570"]:
        return PPGProtocol(address=params.get("address", 254), gauge_type=gauge_type)
    elif gauge_type in ["PCG550", "PSG550"]:
        return PCGProtocol(device_id=params.get("device_id", 0x02))
    elif gauge_type == "MAG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x14))
    elif gauge_type == "MPG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x04))
    elif gauge_type in ["CDG045D", "CDG025D"]:
        return CDGProtocol()
    elif gauge_type == "BPG40x":
        return BPG40xProtocol()
    elif gauge_type == "BPG552":
        return BPG552Protocol()
    elif gauge_type == "BCG450":
        return BCG450Protocol()
    elif gauge_type == "BCG552":
        return BCG552Protocol()
    elif gauge_type == "TC600":
        return TC600Protocol()
    else:
        raise ValueError(f"Unsupported gauge type: {gauge_type}")
