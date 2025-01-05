"""
turbo_serial_settings_frame.py
Provides a specialized serial settings frame for the Turbo Connection,
mirroring your approach from the main GUI but adapted for Turbo usage.

The user can configure:
 - Baud rate
 - Data bits
 - Parity
 - Stop bits
Then click "Apply" to call an apply_callback with the new settings dict.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


class TurboSerialSettingsFrame(ttk.LabelFrame):
    """
    Specialized TurboSerialSettingsFrame for adjusting Turbo COM parameters
    (baud, bits, parity, stopbits), with an "Apply" button that triggers a callback.
    """

    def __init__(self, parent, apply_callback: Callable[[dict], None]):
        """
        parent: The parent widget (TurboFrame)
        apply_callback: A function to call when user clicks "Apply,"
                        passing the chosen serial settings as a dict.
        """
        super().__init__(parent, text="Turbo Serial Config")
        self.apply_callback = apply_callback

        # Initialize variables for each setting
        self.baud_var = tk.StringVar(value="9600")
        self.bytesize_var = tk.StringVar(value="8")
        self.parity_var = tk.StringVar(value="N")
        self.stopbits_var = tk.StringVar(value="1")

        # Builds the UI
        self._create_widgets()

    def _create_widgets(self):
        """
        Places comboboxes for baud, bits, parity, stop bits, plus an "Apply" button.
        """
        # Creates an inner frame for alignment
        settings_frame = ttk.Frame(self)
        settings_frame.pack(fill=tk.X, padx=5, pady=5)

        # Baud
        ttk.Label(settings_frame, text="Baud:").pack(side=tk.LEFT, padx=2)
        baud_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.baud_var,
            values=["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"],
            width=7,
            state="readonly"
        )
        baud_combo.pack(side=tk.LEFT, padx=2)

        # Data bits
        ttk.Label(settings_frame, text="Bits:").pack(side=tk.LEFT, padx=2)
        bits_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.bytesize_var,
            values=["5", "6", "7", "8"],
            width=2,
            state="readonly"
        )
        bits_combo.pack(side=tk.LEFT, padx=2)

        # Parity
        ttk.Label(settings_frame, text="Parity:").pack(side=tk.LEFT, padx=2)
        parity_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.parity_var,
            values=["N", "E", "O", "M", "S"],
            width=2,
            state="readonly"
        )
        parity_combo.pack(side=tk.LEFT, padx=2)

        # Stop bits
        ttk.Label(settings_frame, text="Stop:").pack(side=tk.LEFT, padx=2)
        stop_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.stopbits_var,
            values=["1", "1.5", "2"],
            width=3,
            state="readonly"
        )
        stop_combo.pack(side=tk.LEFT, padx=2)

        # "Apply" button
        apply_btn = ttk.Button(
            settings_frame,
            text="Apply",
            command=self._on_apply
        )
        apply_btn.pack(side=tk.LEFT, padx=5)

    def _on_apply(self):
        """
        Called when user hits "Apply." Gathers the current settings into a dict,
        calls the provided callback function with them.
        """
        settings = {
            "baudrate": int(self.baud_var.get()),
            "bytesize": int(self.bytesize_var.get()),
            "parity": self.parity_var.get(),
            "stopbits": float(self.stopbits_var.get())
        }
        self.apply_callback(settings)
