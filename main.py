from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow

# Only needed to access command line arguments
import sys


def main():
    # Only one QApplication instance needed per application
    # Pass in sys.argv to allow command line arguments for app
    app = QApplication(sys.argv)
    window = MainWindow()

    # Windows hidden by default
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
