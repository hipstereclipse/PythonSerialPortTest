"""
SerialSettingsFrame: Manages RS232/RS485 settings and manual command input.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class SerialSettingsFrame(ttk.LabelFrame):
    """
    Frame for controlling RS232/RS485 serial port settings and manual command entry.
    Provides UI elements to configure serial parameters and send arbitrary commands.
    """

    def __init__(self, parent, settings_callback: Callable, command_callback: Callable):
        """
        Initialize the SerialSettingsFrame with callbacks for settings changes and manual commands.
        """
        super().__init__(parent, text="Serial Settings & Manual Command")

        self.settings_callback = settings_callback
        self.command_callback = command_callback
        self.logger = None

        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")
        self.rs485_mode = tk.BooleanVar(value=False)
        self.rs485_addr = tk.StringVar(value="254")

        self.cmd_history = []
        self.history_index = -1

        self._create_widgets()

    def set_logger(self, logger):
        """Assigns a logger instance."""
        self.logger = logger

    def _create_widgets(self):
        """Creates all widgets in the serial settings frame."""
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # Left Side: Basic Serial Settings
        left_frame = ttk.Frame(settings_frame)
        left_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(left_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_menu = ttk.Combobox(
            left_frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=7
        )
        baud_menu.pack(side=tk.LEFT, padx=2)

        ttk.Label(left_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bytesize_menu = ttk.Combobox(
            left_frame,
            textvariable=self.bytesize_var,
            values=["5", "6", "7", "8"],
            width=2
        )
        bytesize_menu.pack(side=tk.LEFT, padx=2)

        # Center: Parity and Stop Bits
        center_frame = ttk.Frame(settings_frame)
        center_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(center_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_menu = ttk.Combobox(
            center_frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=2
        )
        parity_menu.pack(side=tk.LEFT, padx=2)

        ttk.Label(center_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stopbits_menu = ttk.Combobox(
            center_frame,
            textvariable=self.stopbits_var,
            values=["1", "1.5", "2"],
            width=3
        )
        stopbits_menu.pack(side=tk.LEFT, padx=2)

        # Right Side: RS485 Settings
        right_frame = ttk.Frame(settings_frame)
        right_frame.pack(side=tk.LEFT, padx=5)

        rs485_frame = ttk.Frame(right_frame)
        rs485_frame.pack(side=tk.LEFT, padx=2)

        self.rs485_check = ttk.Checkbutton(
            rs485_frame,
            text="RS485",
            variable=self.rs485_mode,
            command=self._on_rs485_change
        )
        self.rs485_check.pack(side=tk.LEFT, padx=2)

        ttk.Label(rs485_frame, text="Addr:").pack(side=tk.LEFT, padx=2)
        self.rs485_addr_entry = ttk.Entry(rs485_frame, textvariable=self.rs485_addr, width=4)
        self.rs485_addr_entry.pack(side=tk.LEFT, padx=2)

        ttk.Button(right_frame, text="Apply", command=self.apply_settings, width=8).pack(side=tk.LEFT, padx=5)

        self._update_rs485_address_state()

    def _update_rs485_address_state(self):
        """Enables or disables RS485 address entry based on RS485 mode."""
        state = 'normal' if self.rs485_mode.get() else 'disabled'
        self.rs485_addr_entry.configure(state=state)

    def _on_rs485_change(self):
        """Handles RS485 mode toggle."""
        self._update_rs485_address_state()
        settings = self.get_current_settings()
        self.settings_callback(settings)

    def get_current_settings(self) -> dict:
        """Returns the current serial settings in a dict."""
        return {
            'baudrate': int(self.baud_var.get()),
            'bytesize': int(self.bytesize_var.get()),
            'parity': self.parity_var.get(),
            'stopbits': float(self.stopbits_var.get()),
            'rs485_mode': self.rs485_mode.get(),
            'rs485_address': int(self.rs485_addr.get())
        }

    def apply_settings(self):
        """Applies all serial settings by calling the settings callback."""
        settings = self.get_current_settings()
        self.settings_callback(settings)

        settings_msg = (
            f"\nSerial settings applied:\n"
            f"Baud Rate: {settings['baudrate']}\n"
            f"Data Bits: {settings['bytesize']}\n"
            f"Parity: {settings['parity']}\n"
            f"Stop Bits: {settings['stopbits']}\n"
        )
        if settings['rs485_mode']:
            settings_msg += (
                f"RS485 Mode: Enabled\n"
                f"RS485 Address: {settings['rs485_address']}\n"
            )
        else:
            settings_msg += f"RS485 Mode: Disabled\n"

        if self.logger:
            self.logger.info(settings_msg)

    # Example placeholders for manual command entry if needed:
    def send_command(self, event=None):
        """Send a manual command from some entry field (if you had one)."""
        pass

    def history_up(self, event):
        """Go up in command history."""
        pass

    def history_down(self, event):
        """Go down in command history."""
        pass

    def set_rs485_mode(self, enabled: bool, address: int = 254):
        """Enable or disable RS485 mode and set address."""
        self.rs485_mode.set(enabled)
        self.rs485_addr.set(str(address))
        self._update_rs485_address_state()
        self._on_rs485_change()
