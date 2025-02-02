"""
__init__.py

Initializes the gauges package by importing all gauge command definitions and
creating a mapping from gauge types to their corresponding command classes.
"""

from serial_communication.gauges.commands.bcg450_commands import BCG450Command
from serial_communication.gauges.commands.bcg552_commands import BCG552Command
from serial_communication.gauges.commands.bpg552_commands import BPG552Command
from serial_communication.gauges.commands.cdg_commands import CDGCommand
from serial_communication.gauges.commands.magmpg_commands import MAG500Command, MPG500Command
from serial_communication.gauges.commands.opg_commands import OPGCommand
from serial_communication.gauges.commands.pcg550_commands import PCG550Command
from serial_communication.gauges.commands.psg550_commands import PSG550Command

__all__ = [
    'BCG450Command',
    'BCG552Command',
    'BPG552Command',
    'CDGCommand',
    'MAG500Command',
    'MPG500Command',
    'OPGCommand',
    'PCG550Command',
    'PSG550Command'
]

GAUGE_COMMAND_MAP = {
    'BCG450': BCG450Command,
    'BCG552': BCG552Command,
    'BPG552': BPG552Command,
    'CDG025D': CDGCommand,
    'CDG045D': CDGCommand,
    'MAG500': MAG500Command,
    'MPG500': MPG500Command,
    'PCG550': PCG550Command,
    'PSG550': PSG550Command,
    'PPG550': None,  # PPG uses ASCII commands defined in config
    'PPG570': None,  # PPG uses ASCII commands defined in config
}


def get_command_class(gauge_type: str):
    """
    Retrieves the command class for a specific gauge type.

    Args:
        gauge_type: The type of gauge.

    Returns:
        The corresponding command class.

    Raises:
        ValueError: If the gauge type is unknown.
    """
    if gauge_type not in GAUGE_COMMAND_MAP:
        raise ValueError(f"Unknown gauge type: {gauge_type}")
    return GAUGE_COMMAND_MAP[gauge_type]
