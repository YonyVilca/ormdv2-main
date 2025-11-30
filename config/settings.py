from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL")
    SECRET_KEY = os.getenv("SECRET_KEY")
    LOGO_PATH = str(BASE_DIR / os.getenv("LOGO_PATH", "assets/logo.png"))
    # Imagen de encabezado tipo banda para oficios (ancho completo)
    HEADER_BANNER_PATH = str(BASE_DIR / os.getenv("HEADER_BANNER_PATH", "assets/header_banner.png"))
    # Lema anual configurable
    ANNUAL_MOTTO = os.getenv("ANNUAL_MOTTO", "AÑO DE LA RECUPERACIÓN Y CONSOLIDACIÓN DE LA ECONOMÍA PERUANA")
    # Número de ORMD para redactar conclusiones
    ORMD_OFICINA_NUMERO = os.getenv("ORMD_OFICINA_NUMERO", "055-A")
    WINDOW_WIDTH = 450
    WINDOW_HEIGHT = 650
