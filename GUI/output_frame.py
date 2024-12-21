"""
OutputFrame: Displays logs and gauge responses with optional format selection.
"""

import tkinter as tk
from tkinter import ttk

from serial_communication.config import OUTPUT_FORMATS


class OutputFrame(ttk.LabelFrame):
    """
    Frame for displaying command outputs and response logs.
    Provides a text area for logs and an option to select output formats.
    """

    def __init__(self, parent, output_format: tk.StringVar):
        super().__init__(parent, text="Output")
        self.output_format = output_format

        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            format_frame,
            self.output_format,
            "ASCII",
            *OUTPUT_FORMATS
        ).pack(side=tk.LEFT, padx=5)

        self.output_text = tk.Text(self, height=20, width=80, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.output_text, orient="vertical", command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

    def append_log(self, message: str):
        """Add a message to the log and scroll to the end."""
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)

    def clear(self):
        """Clear all text from the log."""
        self.output_text.delete(1.0, tk.END)
