# modules/digitalizacion/digitalizacion_controller.py
import os
from datetime import datetime

def guess_mime(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext in (".jpg", ".jpeg"): return "image/jpeg"
    if ext == ".png": return "image/png"
    if ext == ".pdf": return "application/pdf"
    return "application/octet-stream"

def persist_extraction(user_id: int, username: str, extracted: dict, src_path: str, original_name: str, mime: str):
    # STUB: reemplázalo luego por la versión completa que guarda en tu BD.
    # Deja un log visible para confirmar que se llamó bien.
    return {"ok": True, "documento_id": 0, "ciudadano_id": 0, "at": datetime.now().isoformat()}
