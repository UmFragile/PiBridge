"""Hardware Abstraction Layer.

Everything above this package addresses NICs by stable UUID, never by kernel
name. The HAL is the only place that knows wlan0/eth0 exist.
"""
