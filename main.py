#main.py
"""
Main entry point for the Gauge Communication Program.
Initializes the GUI and starts the application.
"""

import sys                 # Imports the sys module to handle Python runtime settings and exceptions
import tkinter as tk       # Imports tkinter for GUI creation
from tkinter import messagebox  # Imports messagebox for dialog popups
import logging             # Imports logging to handle application logging
from pathlib import Path    # Imports Path for easy cross-platform path handling

from GUI.main_app import GaugeApplication  # Imports the main GUI application class
from serial_communication.config import setup_logging  # Imports the function to set up logging


def setup_exception_handling(root, logger):
    """
    Configures global exception handler to log errors and show user-friendly messages.
    root: The main Tkinter root window.
    logger: The Logger instance to record errors.
    """

    def show_error(msg):
        """
        Shows an error dialog to inform the user that an error occurred.
        msg: The error message to display.
        """
        messagebox.showerror("Error", f"An error occurred: {msg}\n\nCheck the log for details.")

    def handle_exception(exc_type, exc_value, exc_traceback):
        """
        Handles all uncaught exceptions.
        Logs the error, then shows an error dialog to the user.
        """
        # Checks if the exception is a KeyboardInterrupt to gracefully quit
        if issubclass(exc_type, KeyboardInterrupt):
            root.quit()
            return

        # Logs the uncaught exception details
        logger.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        # Schedules a call to show the error message in the GUI
        root.after(100, lambda: show_error(str(exc_value)))

    # Assigns sys.excepthook to our custom exception handler
    sys.excepthook = handle_exception


def create_app_directories():
    """
    Creates necessary application directories if they don't exist.
    Returns a tuple of (app_dir, log_dir, config_dir).
    """

    # Defines the base directory in the user's home folder
    app_dir = Path.home() / ".gauge_communicator"
    # Defines where logs will be stored
    log_dir = app_dir / "logs"
    # Defines where config files may be stored
    config_dir = app_dir / "config"

    # Creates each directory if it doesn't already exist
    for directory in [app_dir, log_dir, config_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return app_dir, log_dir, config_dir


def main():
    """
    Main function to start the Gauge Communicator application.
    Creates directories, sets up logging, and starts the Tkinter GUI.
    """
    # Creates any needed folders for logs/config
    app_dir, log_dir, config_dir = create_app_directories()

    # Initializes logging for the application
    logger = setup_logging("GaugeCommunicator")
    logger.info("Starting Gauge Communication Program")

    # Creates the main Tkinter window
    root = tk.Tk()
    # Tells Tkinter how to handle the window close (X button)
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app))

    # Sets up a global exception handler to catch errors
    setup_exception_handling(root, logger)

    try:
        # Instantiates the main GUI application
        app = GaugeApplication(root)
        logger.info("Application initialized successfully")

        # Determines desired window dimensions
        window_width = 800
        window_height = 650
        # Gets the user’s screen size
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        # Calculates the center coordinates
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)
        # Positions the window in the center of the screen
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

        # Starts the GUI event loop
        root.mainloop()

    except Exception as e:
        # Logs the exception and shows an error dialog if startup fails
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        messagebox.showerror(
            "Startup Error",
            f"Failed to start application: {str(e)}\n\nCheck the log for details."
        )
        sys.exit(1)


def on_closing(root, app):
    """
    Handles application shutdown.
    Safely closes the app and then destroys the Tkinter root.
    """
    try:
        # Calls the application’s on_closing handler for cleanup
        app.on_closing()
    except Exception as e:
        logging.error(f"Error during shutdown: {str(e)}", exc_info=True)
    finally:
        # Destroys the main window to exit
        root.destroy()


if __name__ == "__main__":
    # Entry point to run the main function
    main()
