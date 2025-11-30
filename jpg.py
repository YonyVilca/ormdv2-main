# jpg.py
# -*- coding: utf-8 -*-

import os
import re
import json
import cv2
import numpy as np
import vertexai
import traceback

from vertexai.generative_models import (
    GenerativeModel, Content, Part,
    HarmCategory, HarmBlockThreshold
)

# ==================== CONFIGURACIÓN ====================
PROJECT_ID  = "ormd-476617"   # <-- CAMBIA ESTO
LOCATION    = "us-central1"
IMAGE_PATH  = "7.jpg"         # <-- Ruta de la imagen a procesar
MODEL_NAME  = "gemini-2.0-flash-001"  # Mejor para OCR manuscrito
KEY_PATH = "ormd-476617-56cca3f6e4a6.json" 
# ======================================================


# ------------------- Utilidades de normalización -------------------
MES = {
    "ENE":"01","FEB":"02","MAR":"03","ABR":"04","MAY":"05","JUN":"06",
    "JUL":"07","AGO":"08","SET":"09","SEPT":"09","SEP":"09","OCT":"10",
    "NOV":"11","DIC":"12","DEC":"12"
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

def _pick_best_object_from_list(lst):
    """Si Gemini devuelve una lista, quedarnos con el dict más completo."""
    best = None
    best_score = -1
    for item in lst:
        if isinstance(item, dict):
            score = sum(1 for v in item.values() if v not in (None, "", [], {}))
            if score > best_score:
                best = item; best_score = score
    return best if best is not None else (lst[0] if lst else None)

def normalize_result(d: dict) -> dict:
    """Sanea y normaliza campos según reglas del SMV."""
    if not isinstance(d, dict):
        return {}

    # --- DNI (8 dígitos) ------------------------------------------  # >>> DNI
    dni_raw = (d.get("dni") or "")
    dni_digits = re.sub(r"\D", "", str(dni_raw))
    if dni_digits:
        # Ajuste a 8 dígitos (rellenar con ceros a la izquierda si falta)
        if len(dni_digits) < 11:
            dni_digits = dni_digits.zfill(11)
        d["dni"] = dni_digits[:11]
    else:
        d["dni"] = None

    # --- LM: 10 dígitos ---
    lm = (d.get("dni_o_lm") or "")
    lm_digits = re.sub(r"\D", "", str(lm))
    if lm_digits:
        if len(lm_digits) < 11:
            lm_digits = lm_digits.zfill(10)
        d["dni_o_lm"] = lm_digits
    else:
        d["dni_o_lm"] = None

    # --- OR: ddd + letra (repara 0↔6, A↔4) ---
    or_raw = (d.get("or") or "")
    or_raw = re.sub(r"\s", "", str(or_raw)).upper()
    if or_raw:
        if or_raw.endswith("4"):
            or_raw = or_raw[:-1] + "A"
        or_raw = re.sub(r"[^A-Z0-9]", "", or_raw)
        if re.fullmatch(r"6\d{2}[A-Z]", or_raw):
            or_raw = "0" + or_raw[1:]
        if re.fullmatch(r"\d{3}[A-Z]", or_raw):
            d["or"] = or_raw
        else:
            digs = re.findall(r"\d", or_raw)
            lets = re.findall(r"[A-Z]", or_raw)
            d["or"] = ("".join(digs[:3]) + (lets[-1] if lets else "")) if len(digs) >= 3 and lets else None
    else:
        d["or"] = None

    # --- LIBRO / FOLIO: compactar y mantener ceros a la izquierda ---
    for k in ("libro", "folio"):
        val = d.get(k)
        if val is not None:
            sval = re.sub(r"\s+", "", str(val)).strip()
            d[k] = sval if sval else None

    # --- Fecha de nacimiento: DD/MM/AAAA (mapear meses en letras) ---
    fn = (d.get("fecha_nacimiento") or "")
    s = str(fn).upper().replace(".", "/").replace("-", "/").strip()
    for k, v in MES.items():
        s = re.sub(fr"(\d{{1,2}})[/ ]{k}[/ ](\d{{4}})", fr"\1/{v}/\2", s)
    m = re.match(r"^\s*(\d{1,2})[ /](\d{1,2})[ /](\d{2,4})\s*$", s)
    if m:
        dd = int(m.group(1)); mm = int(m.group(2)); yyyy = m.group(3)
        if len(yyyy) == 2:
            yyyy = "19" + yyyy
        d["fecha_nacimiento"] = f"{dd:02d}/{mm:02d}/{yyyy}" if (1<=dd<=31 and 1<=mm<=12 and len(yyyy)==4) else None
    else:
        d["fecha_nacimiento"] = None

    # --- CLASE: exactamente 2 dígitos (del documento; NO inferir) ---
    clase = (d.get("clase") or "")
    clase_digits = re.sub(r"\D", "", str(clase))
    if len(clase_digits) >= 4:
        d["clase"] = clase_digits[-4:]  # tomar últimos 2 dígitos visibles
    else:
        d["clase"] = None

    # --- Nombres y apellidos: mayúsculas y espacios simples ---
    for k in ("apellidos", "nombres"):
        val = d.get(k)
        if val:
            d[k] = re.sub(r"\s+", " ", str(val)).strip().upper()

    # --- presto_servicio: SI/NO ---
    ps = str(d.get("presto_servicio", "")).strip().upper()
    d["presto_servicio"] = "SI" if ps == "SI" else "NO"

    return d


# ------------------- Preprocesamiento de imagen -------------------
def preprocess_image(image_path: str) -> str:
    """Mejora la imagen para OCR: rotación simple, CLAHE, Otsu, dilate suave."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"No se pudo leer la imagen: {image_path}")

    # Rotación básica (muchas están apaisadas)
    h, w = img.shape[:2]
    if w > h:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = np.ones((1, 1), np.uint8)
    binary = cv2.dilate(binary, kernel, iterations=1)

    temp_path = "temp_processed.png"
    cv2.imwrite(temp_path, binary)
    print(f"Imagen preprocesada: {temp_path}")
    return temp_path


# ------------------- Prompt -------------------
PROMPT = """
DEVUELVE EXCLUSIVAMENTE UN ÚNICO OBJETO JSON VÁLIDO (no listas, sin texto extra).
Procesa solo el documento de esta solicitud.

Eres experto en Hojas de Registro del Servicio Militar del Perú (SMV).
Extrae SOLO lo visible y aplica corrección prudente de OCR.

CAMPOS A ENTREGAR (clave exacta):
{
  "dni": "...",                 
  "lm": "...",
  "or": "...",
  "clase": "...",
  "libro": "...",
  "folio": "...",
  "apellidos": "...",
  "nombres": "...",
  "fecha_nacimiento": "...",
  "presto_servicio": "SI|NO",

  "gran_unidad": null,
  "unidad_alta": null,
  "unidad_baja": null,
  "fecha_alta": null,
  "fecha_baja": null,
  "grado": null,
  "motivo_baja": null
}

REGLAS:
- dni: número junto a “DNI” / “N° DNI” (11 dígitos). Si <11 dígitos, anteponer ceros.
  Si no aparece claramente, devolver null.
- "lm": "6-8 dígitos cerca de LM, LSM, LIBRETA MILITAR o N° OR",
- or: “DDD[L]” (tres dígitos + una letra). Si la última casilla parece “4”, interprétala como “A”.
  Si dudas entre 0 y 6 en la primera casilla, prioriza 0 (055A sobre 655A).
- clase: **CUATRO DÍGITOS exactamente** tal como aparece en el documento (00–99).
  **No convertir a año ni inferir desde la fecha de nacimiento.**
- libro, folio: devolver lo indicado (respetar ceros a la izquierda).
- apellidos / nombres: MAYÚSCULAS, espacios simples, sin inventar; en apellidos concatena paterno + materno.
- fecha_nacimiento: “DD/MM/AAAA”. Mapea meses: ENE=01, FEB=02, MAR=03, ABR=04, MAY=05, JUN=06,
  JUL=07, AGO=08, SET=09, OCT=10, NOV=11, DIC=12.
- presto_servicio: “SI” si existe alguno entre {grado, fecha_alta, unidad_alta/baja, motivo_baja}; si no, “NO”.
- SI "presto_servicio" == "SI" → incluir:
  "gran_unidad", "unidad_alta", "unidad_baja", "fecha_alta", "fecha_baja", "grado", "motivo_baja"
- Si la imagen muestra dos páginas, devuelve SOLO la hoja principal completa.

Responde SOLO con el objeto JSON.
"""


# ------------------- Llamada a Gemini -------------------
def extract_with_gemini(processed_image_path: str) -> dict | None:
    # 1. AUTENTICACIÓN: Establecer la clave JSON de la cuenta de servicio
    # Asume que KEY_PATH es una variable global o definida en la configuración.
    if not os.path.exists(KEY_PATH):
        print(f"[ERROR Autenticación] No se encontró el archivo de clave JSON en la ruta: {KEY_PATH}")
        return None
        
    # 2. INICIALIZACIÓN DE VERTEX AI CON CREDENCIALES EXPLÍCITAS
    try:
        from google.oauth2 import service_account
        
        # Cargar credenciales explícitamente
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        
        # Inicializar Vertex AI con credenciales explícitas
        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        print(f"[INFO] Vertex AI inicializado con credenciales del service account: {credentials.service_account_email}")
    except Exception as e:
        print(f"[ERROR Vertex AI Init] Fallo al inicializar la sesión: {e}")
        print("Asegúrate de que la Service Account tiene los roles necesarios:")
        print("- Vertex AI User (roles/aiplatform.user)")
        print("- Storage Object Viewer (roles/storage.objectViewer)")
        return None
        
    model = GenerativeModel(MODEL_NAME)

    # 3. PREPARAR LA IMAGEN
    try:
        with open(processed_image_path, "rb") as f:
            img_bytes = f.read()
    except Exception as e:
        print(f"[ERROR IO] No se pudo leer la imagen preprocesada: {e}")
        return None

    image_part = Part.from_data(mime_type="image/png", data=img_bytes)

    # 4. LLAMADA A LA API (Con TRY/EXCEPT detallado)
    try:
        print("Enviando solicitud al modelo...")
        response = model.generate_content(
            [image_part, PROMPT],
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
                "max_output_tokens": 1024
            }
        )

        # 5. PROCESAMIENTO DE LA RESPUESTA
        raw = _strip_code_fences(response.text)
        data = json.loads(raw)

        # Manejo de listas de respuesta (si Gemini devuelve una lista)
        if isinstance(data, list):
            data = _pick_best_object_from_list(data)
        if not isinstance(data, dict):
            raise ValueError("La respuesta de Gemini no es un objeto JSON válido.")

        return normalize_result(data)

    except Exception as e:
        # IMPRIMIR LA TRAZA DE ERROR COMPLETA PARA DIAGNÓSTICO
        print("\n--- INICIO DE LA TRAZA DE ERROR DETALLADA ---")
        traceback.print_exc() # Muestra la línea exacta donde falló
        print("--- FIN DE LA TRAZA DE ERROR DETALLADA ---\n")
        
        error_msg = str(e)
        
        # Detectar errores específicos de conectividad
        if "DNS resolution failed" in error_msg or "ServiceUnavailable" in error_msg:
            print(f"[ERROR CONECTIVIDAD] Sin conexión a Vertex AI: {e}")
            print("💡 Sugerencias:")
            print("  - Verificar conexión a internet")
            print("  - Revisar configuración de proxy/firewall")  
            print("  - Intentar en unos minutos")
            return {"error": "sin_conexion", "mensaje": "No se puede conectar a Vertex AI. Revisa tu conexión a internet."}
        elif "PERMISSION_DENIED" in error_msg:
            print(f"[ERROR PERMISOS] Credenciales inválidas: {e}")
            return {"error": "permisos", "mensaje": "Credenciales de Google Cloud inválidas o expiradas."}
        else:
            print(f"[ERROR Gemini Detallado] Falló la llamada a la API o el procesamiento del JSON: {e}")
            return {"error": "procesamiento", "mensaje": f"Error en el procesamiento: {str(e)}"}


# ------------------- MAIN -------------------
def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: No se encontró {IMAGE_PATH}")
        return

    print("1) Preprocesando imagen...")
    processed = preprocess_image(IMAGE_PATH)

    print("2) Enviando a Gemini...")
    result = extract_with_gemini(processed)

    if result:
        print("\nEXTRACCIÓN EXITOSA:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        with open("resultado.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\nGuardado en 'resultado.json'")
    else:
        print("Falló la extracción.")

    try:
        if os.path.exists("temp_processed.png"):
            os.remove("temp_processed.png")
    except Exception:
        pass


if __name__ == "__main__":
    main()
