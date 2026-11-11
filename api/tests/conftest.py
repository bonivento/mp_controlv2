"""Configuración común de las pruebas de la API.

Las pruebas no llevan sesión de Supabase: la verificación del JWT se desactiva
aquí para todas, y `tests/routers/test_auth.py` la vuelve a activar para probar
los rechazos. Debe ejecutarse antes de importar `main`.
"""

import os

os.environ.setdefault("AUTH_DISABLED", "1")
