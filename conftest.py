"""Deja el repositorio en el `sys.path` para que las pruebas importen
`scraper` sin instalar el paquete."""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
