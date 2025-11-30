# utils/ocr_smv.py
import os, re, json
from dataclasses import dataclass
from typing import Dict, Any

MES = {
    "ENE":"01","FEB":"02","MAR":"03","ABR":"04","MAY":"05","JUN":"06",
    "JUL":"07","AGO":"08","SET":"09","SEPT":"09","SEP":"09","OCT":"10",
    "NOV":"11","DIC":"12","DEC":"12"
}

@dataclass
class OCRConfig:
    engine: str = "gemini"          # "gemini" | "tesseract"
    project_id: str | None = os.getenv("VERTEX_PROJECT")
    location: str | None = os.getenv("VERTEX_LOCATION", "us-central1")
    key_path: str | None = os.getenv("VERTEX_KEY_PATH")
    model_name: str = os.getenv("VERTEX_MODEL", "gemini-2.0-flash-001")

def _normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    # Normalización mínima para que la UI funcione
    out = {k: (None if d.get(k) in ("", None) else d.get(k)) for k in d.keys()} if isinstance(d, dict) else {}
    for k in ["dni","lm","or","clase","libro","folio","apellidos","nombres","fecha_nacimiento","presto_servicio",
              "gran_unidad","unidad_alta","unidad_baja","fecha_alta","fecha_baja","grado","motivo_baja"]:
        out.setdefault(k, None)
    # DNI a 11 dígitos (relleno)
    if out.get("dni"):
        digits = re.sub(r"\D","", str(out["dni"]))
        if digits:
            if len(digits) < 11:
                digits = digits.zfill(11)
            out["dni"] = digits[:11]
    # OR DDD+L
    if out.get("or"):
        s = re.sub(r"\s","", str(out["or"])).upper()
        if s.endswith("4"): s = s[:-1] + "A"
        out["or"] = s if re.fullmatch(r"\d{3}[A-Z]", s) else None
    # Fecha DD/MM/AAAA (muy básica)
    if out.get("fecha_nacimiento"):
        s = str(out["fecha_nacimiento"]).upper().replace(".","/").replace("-","/")
        for k,v in MES.items():
            s = re.sub(fr"(\d{{1,2}})[/ ]{k}[/ ](\d{{4}})", fr"\1/{v}/\2", s)
        m = re.match(r"^\s*(\d{1,2})[ /](\d{1,2})[ /](\d{2,4})\s*$", s)
        if m:
            dd, mm, yyyy = int(m.group(1)), int(m.group(2)), m.group(3)
            if len(yyyy)==2: yyyy = "19"+yyyy
            out["fecha_nacimiento"] = f"{dd:02d}/{mm:02d}/{yyyy}" if 1<=dd<=31 and 1<=mm<=12 else None
        else:
            out["fecha_nacimiento"] = None
    # Presto servicio
    out["presto_servicio"] = "SI" if str(out.get("presto_servicio") or "").strip().upper()=="SI" else "NO"
    return out

def extract_from_file(path: str, cfg: OCRConfig) -> Dict[str, Any]:
    """
    STUB: devuelve campos vacíos normalizados para permitir flujos de edición manual.
    Reemplázame por la versión completa (Gemini + preprocesado) del canvas.
    """
    base = {
        "dni": None, "lm": None, "or": None, "clase": None, "libro": None, "folio": None,
        "apellidos": None, "nombres": None, "fecha_nacimiento": None, "presto_servicio": "NO",
        "gran_unidad": None, "unidad_alta": None, "unidad_baja": None,
        "fecha_alta": None, "fecha_baja": None, "grado": None, "motivo_baja": None
    }
    return _normalize(base)
