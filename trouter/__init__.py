"""travelrouter — a travel-router appliance for Raspberry Pi Zero 2 W.

This package implements a strictly layered architecture:

    API (Flask)  ->  ConfigManager  ->  ValidationEngine
                 ->  TransactionManager  ->  HAL  ->  System services

The web/API layers never touch system config files directly. Every change
that can affect connectivity goes through the TransactionManager, which
snapshots, applies, health-checks and auto-rolls-back on failure or on a
missed user confirmation. See docs/SAFETY.md.
"""

__version__ = "0.1.1"
