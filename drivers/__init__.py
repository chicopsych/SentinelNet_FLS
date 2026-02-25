"""
drivers/
Camada de drivers por fabricante.

Cada arquivo aqui implementa um driver concreto
que herda de core.base_driver.NetworkDeviceDriver.

Implementados:
- mikrotik_driver.py  (Task 03 ✅)

Planejados:
- cisco_driver.py     (futuro)
- fiberhome_driver.py (futuro)
"""

from .mikrotik_driver import MikroTikDriver

__all__ = ["MikroTikDriver"]
