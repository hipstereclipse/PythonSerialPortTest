"""
turbo_serial_settings_frame.py
Defines a specialized serial settings frame for the turbo connection,
similar to your normal SerialSettingsFrame but dedicated to Turbo comm settings.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

class TurboSerialSettingsFrame(ttk.LabelFrame):
    """
    Specialized frame for configuring turbo communication settings:
     - Baud rate
     - Data bits
     - Parity
     - Stop bits
     - Possibly RS485 toggles, etc.
    """

    def __init__(self, parent):
        """
        Initializes a dedicated frame for Turbo comm configuration.
        You can adapt or expand it as needed, mimicking SerialSettingsFrame logic.
        """
        super().__init__(parent, text="Turbo Serial Config")

        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")
        self.rs485_mode = tk.BooleanVar(value=False)

        self._create_widgets()

    def _create_widgets(self):
        """
        Lays out widgets for baud rate, data bits, parity, stop bits, RS485, etc.
        """
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=5, pady=5)

        # Baud
        ttk.Label(frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_menu = ttk.Combobox(
            frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=7
        )
        baud_menu.pack(side=tk.LEFT, padx=2)

        # Data bits
        ttk.Label(frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bits_menu = ttk.Combobox(
            frame,
            textvariable=self.bytesize_var,
            values=["5", "6", "7", "8"],
            width=2
        )
        bits_menu.pack(side=tk.LEFT, padx=2)

        # Parity
        ttk.Label(frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_menu = ttk.Combobox(
            frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=2
        )
        parity_menu.pack(side=tk.LEFT, padx=2)

        # Stop bits
        ttk.Label(frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stop_menu = ttk.Combobox(
            frame,
            textvariable=self.stopbits_var,
            values=["1", "1.5", "2"],
            width=3
        )
        stop_menu.pack(side=tk.LEFT, padx=2)

        # RS485 toggle
        self.rs485_check = ttk.Checkbutton(
            frame,
            text="RS485",
            variable=self.rs485_mode
        )
        self.rs485_check.pack(side=tk.LEFT, padx=2)

        # Apply button (placeholder). In real code, you'd do something like apply to turbo communicator.
        apply_btn = ttk.Button(
            frame,
            text="Apply",
            command=self._on_apply
        )
        apply_btn.pack(side=tk.LEFT, padx=5)

    def _on_apply(self):
        """
        Called when user hits "Apply".
        Typically you'd push these settings to a turbo communicator object if you have one.
        """
        # For demonstration, we just print or do nothing.
        print(f"Turbo config applied: baud={self.baud_var.get()}, bits={self.bytesize_var.get()},"
              f" parity={self.parity_var.get()}, stop={self.stopbits_var.get()}, rs485={self.rs485_mode.get()}")
