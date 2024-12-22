"""
Collects all gauge protocols and provides a get_protocol() factory function
so that other parts of the code can easily instantiate the correct protocol class.
"""
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
    """Factory function to get the appropriate protocol handler based on gauge type."""

    # MEMS Pirani gauges
    if gauge_type in ["PPG550", "PPG570"]:
        return PPGProtocol(
            address=params.get("address", 254),
            gauge_type=gauge_type
        )

    # Pirani/Capacitive combination gauges
    elif gauge_type in ["PCG550", "PSG550"]:
        return PCGProtocol(device_id=params.get("device_id", 0x02))

    # Cold cathode gauges
    elif gauge_type == "MAG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x14))
    elif gauge_type == "MPG500":
        return MAGMPGProtocol(device_id=params.get("device_id", 0x04))

    # Capacitive gauges
    elif gauge_type in ["CDG045D", "CDG025D"]:
        return CDGProtocol()

    # Hot cathode gauges
    elif gauge_type == "BPG40x":
        return BPG40xProtocol()
    elif gauge_type == "BPG552":
        return BPG552Protocol()

    # Combination gauges
    elif gauge_type == "BCG450":
        return BCG450Protocol()
    elif gauge_type == "BCG552":
        return BCG552Protocol()

    # Turbo pump controller
    elif gauge_type == "TC600":
        return TC600Protocol()

    else:
        raise ValueError(f"Unsupported gauge type: {gauge_type}")