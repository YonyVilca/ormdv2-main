"""Script rápido para generar un OFICIO de prueba usando pdf_renderer.
Ejecutar: .\.venv\Scripts\python.exe test_pdf_renderer.py
Asegúrate de tener en assets/ los archivos sello.png y firma.png para ver el bloque de firma completo.
"""
from modules.dashboard.pdf_renderer import generate_oficio_pdf, build_ciudadano_line
from datetime import datetime
import os

# Directorio de salida
OUT_DIR = os.path.join("storage", "data", "reports")

# Parámetros de muestra
ciudad = "Arequipa"
fecha = datetime.now().strftime("%d/%m/%Y")
asunto = "Remite información solicitada del ciudadano"
referencia = "Oficio 123-2025-RENIEC"
destinatario = "JEFE NACIONAL DEL RENIEC"
cargo_dest = "JEFE NACIONAL"
entidad_dest = "REGISTRO NACIONAL DE IDENTIFICACIÓN Y ESTADO CIVIL - RENIEC"
numero_oficio = "055-A-2025-001"
resultado = "POSITIVO"  # probar también NEGATIVO
institucion_nombre = "MINISTERIO DE DEFENSA - EJÉRCITO DEL PERÚ"
motto_text = "La gloria se alcanza con disciplina"
logo_path = os.path.join("assets", "logo.png")  # opcional
banner_path = os.path.join("assets", "banner.png")  # si existe se usa
watermark = True
firmante_nombre = "GUSTAVO ADOLFO HINOJOSA GAMBOA"
firmante_cargo = "Tte Crl CAB - JEFE DE LA ORMD N° 055-A"
usuario_actual = "admin"
rol_actual = "JEFE"
# Construir línea ciudadano
ciudadano_line = build_ciudadano_line(
    "PEREZ QUISPE",
    "JUAN CARLOS",
    "15/05/1990",
    "LM-998877",
    resultado,
)

# Generar
ruta = generate_oficio_pdf(
    out_dir=OUT_DIR,
    ciudad=ciudad,
    fecha=fecha,
    asunto=asunto,
    referencia=referencia,
    destinatario=destinatario,
    cargo_dest=cargo_dest,
    entidad_dest=entidad_dest,
    numero_oficio=numero_oficio,
    resultado=resultado,
    institucion_nombre=institucion_nombre,
    motto_text=motto_text,
    logo_path=logo_path,
    banner_path=banner_path,
    watermark=watermark,
    firmante_nombre=firmante_nombre,
    firmante_cargo=firmante_cargo,
    usuario_actual=usuario_actual,
    rol_actual=rol_actual,
    ciudadano_line=ciudadano_line,
    office_number="055-A",
)
print("PDF generado:", ruta)
print("Abrir manualmente si no se abre automáticamente.")
