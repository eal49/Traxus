"""
Traxus client entry point.

Usage:
    python -m client.main
"""
from client.app import TraxusApp

if __name__ == "__main__":
    app = TraxusApp()
    app.run()
