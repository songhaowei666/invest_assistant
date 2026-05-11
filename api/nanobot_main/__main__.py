"""
Entry point for running nanobot_main as a module: python -m nanobot_main
"""

from nanobot_main.cli.commands import app

if __name__ == "__main__":
    app()
