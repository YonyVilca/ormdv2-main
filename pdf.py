import vertexai
from vertexai.generative_models import GenerativeModel, Part, HarmCategory, HarmBlockThreshold
import json
import base64
import os
from typing import Dict, Any

# === CONFIGURACIÓN ===
PROJECT_ID = "ormd-476617"        # ← TU PROJECT ID
LOCATION = "us-central1"            # o europe-west1, etc.
KEY_PATH = "ormd-476617-56cca3f6e4a6.json"           # ← Ruta a tu JSON key

def analizar_documento_smv(ruta_documento: str) -> Dict[str, Any]:
    # AUTENTICACIÓN: Inicializar Vertex AI con credenciales explícitas
    try:
        from google.oauth2 import service_account
        
        if not os.path.exists(KEY_PATH):
            return {"error": f"Archivo de clave de servicio no encontrado: {KEY_PATH}", "raw": None}
        
        # Cargar credenciales explícitamente
        credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
        
        # Inicializar Vertex AI con credenciales explícitas
        vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
        print(f"[INFO] Vertex AI inicializado con credenciales del service account: {credentials.service_account_email}")
    except Exception as e:
        return {"error": f"Error de autenticación: {e}", "raw": None}
    # Leer archivo
    with open(ruta_documento, "rb") as f:
        file_data = f.read()

    # MIME type
    _, ext = os.path.splitext(ruta_documento.lower())
    mime_type = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.pdf': 'application/pdf'
    }.get(ext, 'application/octet-stream')

    document_part = Part.from_data(data=file_data, mime_type=mime_type)

    # Prompt
    prompt = """Eres un extractor experto para documentos del Servicio Militar Peruano (SMV) con calidad de escaneo variable y campos manuscritos. Devuelve **SOLO** un JSON válido UTF-8, sin comentarios ni texto extra..

REGLAS:
1. Solo texto visible.
2. Corrige OCR: §→S, ¢→C, ¡→I, ñ→M, ª→°, ³→3, Ã→A, Á→A, É→E, etc.
3. Si no existe → null.
4. NO inventes.
5. SOLO JSON.

CAMPOS:
{
  "dni": "8 dígitos cerca de DNI o N° (solo si dice DNI)",
  "lm": "6-8 dígitos cerca de LM, LSM, LIBRETA MILITAR o N° OR",
  "or": "Cerca de OR o N° OR",
  "clase": "Año 4 dígitos cerca de CLASE:",
  "libro": "Cerca de LIBRO:",
  "folio": "Cerca de FOLIO:",
  "apellidos": "PATERNO + MATERNO (MAYÚSCULAS)",
  "nombres": "NOMBRES completos (MAYÚSCULAS)",
  "fecha_nacimiento": "DD/MM/AAAA". Mapea meses: ENE=01, FEB=02, MAR=03, ABR=04, MAY=05, JUN=06,
  JUL=07, AGO=08, SET=09, OCT=10, NOV=11, DIC=12.,
  "presto_servicio": "SI si hay AL MENOS UNO de: UNIDAD ALTA, FECHA ALTA, GRADO, MOTIVO BAJA → NO si todos vacíos"
}

SI "presto_servicio" == "SI" → incluir:
  "gran_unidad", "unidad_alta", "unidad_baja", "fecha_alta", "fecha_baja", "grado", "motivo_baja"
"""

    # Modelo
    model = GenerativeModel("gemini-2.0-flash-001")

    try:
        response = model.generate_content(
            [document_part, prompt],
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
                "max_output_tokens": 2048,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        json_text = response.text.strip()
        return json.loads(json_text)

    except Exception as e:
        return {"error": str(e), "raw": response.text if 'response' in locals() else None}


# === USO ===
if __name__ == "__main__":
    ruta = "2.pdf"  # Cambia por tu archivo

    if not os.path.exists(ruta):
        print(f"Archivo no encontrado: {ruta}")
    else:
        resultado = analizar_documento_smv(ruta)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))