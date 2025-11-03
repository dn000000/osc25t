"""
Main entry point for sysaudit when run as a module.
Allows execution via: python -m sysaudit
"""

from sysaudit.cli import cli

if __name__ == '__main__':
    cli()
