# utils/extractors.py
# -*- coding: utf-8 -*-
import json
from typing import Any, Dict

from jpg import preprocess_image, extract_with_gemini as _jpg_extract
from pdf import analizar_documento_smv as _pdf_extract

# Alias que pueden venir del modelo
ALIASES = {
    "dni_o_lm": "lm",
    "libreta_militar": "lm",
}

# Estructura base que espera tu UI
BASE = {
    "dni": None, "lm": None, "or": None, "clase": None, "libro": None, "folio": None,
    "apellidos": None, "nombres": None, "fecha_nacimiento": None, "presto_servicio": "NO",
    "gran_unidad": None, "unidad_alta": None, "unidad_baja": None,
    "fecha_alta": None, "fecha_baja": None, "grado": None, "motivo_baja": None,
}

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 3:
            inner = parts[1]
            if inner.lower().startswith("json"):
                inner = inner[4:].strip()
            return inner.strip()
    return s

def _best_dict_from_list(lst: list) -> Dict[str, Any]:
    best = {}
    best_score = -1
    for item in lst:
        if isinstance(item, dict):
            score = sum(1 for v in item.values() if v not in (None, "", [], {}))
            if score > best_score:
                best = item
                best_score = score
    return best

def _coerce_to_dict(obj: Any) -> Dict[str, Any]:
    """Convierte cualquier respuesta (dict/list/str) a dict normalizado y completo."""
    if obj is None:
        d = {}
    elif isinstance(obj, dict):
        d = obj
    elif isinstance(obj, list):
        d = _best_dict_from_list(obj)
    elif isinstance(obj, str):
        try:
            d = json.loads(_strip_code_fences(obj))
        except Exception:
            d = {}
    else:
        d = {}

    # Aplica alias → claves estándar
    for src, dst in ALIASES.items():
        if src in d and dst not in d:
            d[dst] = d[src]

    out = {**BASE, **d}
    out["presto_servicio"] = "SI" if str(out.get("presto_servicio") or "").upper() == "SI" else "NO"
    return out

def extract_image(path: str) -> Dict[str, Any]:
    """Imagen (JPG/PNG) → dict normalizado."""
    processed = preprocess_image(path)
    data = _jpg_extract(processed)
    return _coerce_to_dict(data)

def extract_pdf(path: str) -> Dict[str, Any]:
    """PDF → dict normalizado."""
    data = _pdf_extract(path)
    return _coerce_to_dict(data)
