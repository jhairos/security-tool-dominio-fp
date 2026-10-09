"""
config.py
=========
Configuracion general de Security Tool Jairo Suntaxi C.

Solo contiene parametros de la aplicacion (nombre, version, rutas,
registro e interfaz). La configuracion del analisis de dominios vive en
``routines/dominio_fp/dominio_fp_config.py``.
"""
from __future__ import annotations

from pathlib import Path

# --- Identificacion de la aplicacion ---------------------------------
APP_NAME: str = "Security Tool Jairo Suntaxi C"
APP_CODE: str = "SECURITY_TOOL_JSC"
APP_VERSION: str = "3.0.0"
APP_BUILD: str = "v3"
APP_AUTHOR: str = "Jairo Suntaxi C ©"


def version_completa() -> str:
    """Version mostrada en la interfaz y en los registros: 3.0.0 (v3)."""
    return f"{APP_VERSION} ({APP_BUILD})"


# --- Rutas ------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
LOGS_DIR: Path = BASE_DIR / "logs"
EXPORTS_DIR: Path = BASE_DIR / "exports"

for _d in (LOGS_DIR, EXPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --- Registro ---------------------------------------------------------
MAIN_LOG_FILE: Path = LOGS_DIR / "security_tool.log"
LOG_MAX_BYTES: int = 2_000_000
LOG_BACKUP_COUNT: int = 5

# --- Interfaz ---------------------------------------------------------
DEFAULT_THEME: str = "dark"          # dark | light
#: Cadena vacia: la ventana se ajusta automaticamente al monitor.
WINDOW_GEOMETRY: str = ""
WINDOW_MIN_SIZE: tuple[int, int] = (960, 600)
GUI_POLL_MS: int = 120               # frecuencia de lectura de la cola
