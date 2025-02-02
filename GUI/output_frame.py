"""
GUI/output_frame.py

Implements the OutputFrame class which displays log messages and responses.
It supports format selection and keeps a history of messages.
"""

import tkinter as tk
from tkinter import ttk
from serial_communication.config import OUTPUT_FORMATS


class OutputFrame(ttk.LabelFrame):
    """
    Frame for displaying output logs and responses.
    """

    def __init__(self, parent: tk.Widget, output_format: tk.StringVar) -> None:
        """
        Initialize the OutputFrame.

        Args:
            parent: Parent Tkinter widget.
            output_format: StringVar to track the selected output format.
        """
        super().__init__(parent, text="Output")
        self.output_format = output_format
        self.messages: list[str] = []

        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(format_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(format_frame, self.output_format, "ASCII", *OUTPUT_FORMATS).pack(side=tk.LEFT, padx=5)

        self.output_text = tk.Text(self, height=20, width=80, wrap=tk.WORD)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(self.output_text, orient="vertical", command=self.output_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)

    def append_log(self, message: str) -> None:
        """
        Appends a new message to the log.
        """
        self.messages.append(message)
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)

    def clear(self) -> None:
        """
        Clears all messages from storage and display.
        """
        self.messages.clear()
        self.output_text.delete(1.0, tk.END)

    def filter_debug_messages(self, show_debug: bool) -> None:
        """
        Filters out debug messages if not wanted.
        """
        self.output_text.delete(1.0, tk.END)
        for msg in self.messages:
            if show_debug or "DEBUG" not in msg:
                self.output_text.insert(tk.END, msg + "\n")
        self.output_text.see(tk.END)
