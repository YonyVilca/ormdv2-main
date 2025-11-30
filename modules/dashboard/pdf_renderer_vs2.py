"""PDF renderer alternativo (VS2) para pruebas rápidas de formato OFICIO institucional.
Utiliza PyMuPDF (fitz) y estructura por bloques numerados.
"""
from datetime import datetime
import os
try:
    import fitz  # type: ignore
except Exception:
    fitz = None

FONT_NAME = "helv"
BLACK = (0, 0, 0)

OFICIO_MARGIN_X = 50
OFICIO_MARGIN_Y = 50 - int(2 * 28.35)  # 2cm en puntos (aprox 28.35pt/cm)
OFICIO_LINE_HEIGHT = 16
OFICIO_HEADER_TITLE_SIZE = 12
OFICIO_BODY_FONT_SIZE = 12
OFICIO_FOOTER_FONT_SIZE = 12

DISTRIBUCION = [
    "- RENIEC · Lima ...................... 01",
    "- Archivo ............................... 01",
]

def generate_oficio_pdf_vs2(
    out_dir: str,
    ciudad: str,
    fecha: str,
    asunto: str,
    referencia: str,
    destinatario: str,
    cargo_dest: str,
    entidad_dest: str,
    numero_oficio: str,
    resultado: str,
    institucion_nombre: str,
    firmante_nombre: str,
    firmante_cargo: str,
    usuario_actual: str,
    rol_actual: str,
    ciudadano_line: str,
    year_fiscal: str = "AÑO DE LA RECUPERACIÓN Y CONSOLIDACIÓN DE LA ECONOMÍA PERUANA",
    firma_img_path: str = None,
) -> str:
    if not fitz:
        raise RuntimeError("PyMuPDF no disponible; instale 'pymupdf'.")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir, f"oficio_vs2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    docpdf = fitz.open()
    pagepdf = docpdf.new_page()
    width, height = pagepdf.rect.width, pagepdf.rect.height
    mx, my = OFICIO_MARGIN_X, OFICIO_MARGIN_Y
    # Offsets parametrizables para cada bloque
    offset_img = 0
    offset_ano = 10  # Espacio entre imagen y año
    offset_fecha = 8  # Espacio entre año y fecha
    offset_oficio = 8
    offset_dest = 8
    offset_asunto = 8
    offset_ref = 8
    offset_titulo8 = 12
    offset_texto8 = 8
    y = my
    # Utilidad para justificar texto
    def insert_textbox_justified(text, y, fontsize=OFICIO_BODY_FONT_SIZE, height_box=40):
        rect = fitz.Rect(mx, y, width - mx, y + height_box)
        pagepdf.insert_textbox(
            rect,
            text,
            fontsize=fontsize,
            fontname=FONT_NAME,
            color=BLACK,
            align=4,  # Justificado
        )
    def insert_textbox_centered(text, y, fontsize=OFICIO_BODY_FONT_SIZE, height_box=24):
        rect = fitz.Rect(mx, y, width - mx, y + height_box)
        pagepdf.insert_textbox(
            rect,
            text,
            fontsize=fontsize,
            fontname=FONT_NAME,
            color=BLACK,
            align=1,  # Centrado
        )
    def insert_text_right(text, y, fontsize=OFICIO_BODY_FONT_SIZE):
        # Estimación simple del ancho del texto (6px por caracter)
        text_len = len(text) * (fontsize // 2)
        x = width - mx - text_len - int(20 * 2.835)  # mover 20mm más a la izquierda
        pagepdf.insert_text((x, y), text, fontsize=fontsize, fontname=FONT_NAME, color=BLACK)

    # Imagen de encabezado aumentada 30% y bajada 1cm
    banner_path = os.path.join("assets", "encabezado01.png")
    banner_h = int(60 * 1.3)
    y += int(1 * 28.35)  # Bajar encabezado 1cm
    if os.path.exists(banner_path):
        try:
            pagepdf.insert_image(
                fitz.Rect(mx, y, width - mx, y + banner_h),
                filename=banner_path,
                keep_proportion=True,
            )
            y += banner_h + offset_img
        except Exception:
            pass
    # Año centrado, tamaño 10
    y += offset_ano
    ano = year_fiscal
    y -= int(0.4 * 28.35)  # Subir el año 4mm (previo)
    y -= int(0.3 * 28.35)  # Subir el año otros 3mm más
    insert_textbox_centered(f"{ano}", y, 10, 18)
    y += 18

    # (La firma solo se inserta en la posición final, no aquí)
    # Fecha alineada completamente a la derecha
    y += offset_fecha
    fecha_texto = f"{ciudad}, {fecha}"
    rect_fecha = fitz.Rect(mx, y, width - mx, y + 24)
    pagepdf.insert_textbox(rect_fecha, fecha_texto, fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=2)  # 2 = derecha
    y += 24
    # Oficio
    y += offset_oficio
    insert_textbox_justified(f"Ofício Nº {numero_oficio}", y, OFICIO_HEADER_TITLE_SIZE, 24)
    y += 24
    # Señor(a), Asunto y Referencia con espacio y alineación uniforme
    y += offset_dest
    destinatario_full = destinatario
    if cargo_dest:
        destinatario_full += f" {cargo_dest}"
    if entidad_dest:
        destinatario_full += f" – {entidad_dest}"
    # Señor(a): [contenido alineado derecha]
    label_w = 110
    value_x = mx + int(2.5 * 28.35)  # 2.5 cm en puntos
    value_w = width - mx - int(2.5 * 28.35)
    # Señor(a):
    rect_label_senor = fitz.Rect(mx, y, mx + label_w, y + 24)
    rect_value_senor = fitz.Rect(value_x, y, value_x + value_w, y + 24)
    pagepdf.insert_textbox(rect_label_senor, "Señor(a):", fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=0)
    pagepdf.insert_textbox(rect_value_senor, f"{destinatario_full}", fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=0)
    y += 28
    # Asunto:
    rect_label_asunto = fitz.Rect(mx, y, mx + label_w, y + 24)
    rect_value_asunto = fitz.Rect(value_x, y, value_x + value_w, y + 24)
    pagepdf.insert_textbox(rect_label_asunto, "Asunto:", fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=0)
    pagepdf.insert_textbox(rect_value_asunto, f"{asunto}", fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=0)
    y += 28
    # Ref.:
    rect_label_ref = fitz.Rect(mx, y, mx + label_w, y + 24)
    rect_value_ref = fitz.Rect(value_x, y, value_x + value_w, y + 24)
    pagepdf.insert_textbox(rect_label_ref, "Ref:", fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=0)
    pagepdf.insert_textbox(rect_value_ref, f"{referencia}", fontsize=OFICIO_HEADER_TITLE_SIZE, fontname=FONT_NAME, color=BLACK, align=0)
    y += 28
    # (8) Cuerpo destacado y visible
    y += offset_titulo8
    punto8_titulo = "INFORME DE VERIFICACIÓN"
    insert_textbox_justified(punto8_titulo, y, OFICIO_HEADER_TITLE_SIZE, 28)
    y += 28
    y += offset_texto8
    punto8_texto_1 = "Tengo el agrado de dirigirme a usted para expresarle un cordial saludo y, en atención al documento de la referencia, informarle lo siguiente:"
    punto8_texto_2 = "En la verificación realizada en nuestros registros sobre la existencia de ficha de inscripción militar de los ciudadanos señalados en el documento de la referencia, se ha procedido a realizar la búsqueda, con el resultado siguiente:"
    # Sangría de 4.5 espacios solo en el primer texto
    sangria = " " * 4
    texto_sangrado_1 = f"{sangria}{punto8_texto_1}"
    insert_textbox_justified(texto_sangrado_1, y, OFICIO_BODY_FONT_SIZE, 50)
    y += 50
    # El texto intermedio sin sangría
    insert_textbox_justified(punto8_texto_2, y, OFICIO_BODY_FONT_SIZE, 80)
    y += 80
    # (9) Datos del ciudadano (mostrar título sin número, subido 1cm)
    y -= int(1 * 28.35)  # Subir datos del ciudadano 1cm
    insert_textbox_justified("DATOS DEL CIUDADANO:", y, OFICIO_HEADER_TITLE_SIZE, 20)
    y += 20
    if ciudadano_line:
        datos_ciudadano = ciudadano_line.split("|")
        for idx, part in enumerate(datos_ciudadano):
            label = ""
            if idx == 0:
                label = "Apellidos y Nombres: "
            elif "Fecha Nac" in part:
                label = "Fecha de Nacimiento: "
            elif "LM" in part:
                label = "Libreta Militar: "
            elif "Resultado" in part:
                label = "Resultado: "
            insert_textbox_justified(f"{label}{part.replace('Fecha Nac:', '').replace('LM:', '').replace('Resultado:', '').strip()}", y, OFICIO_BODY_FONT_SIZE, 22)
            y += 22
    else:
        insert_textbox_justified("[No disponible]", y, OFICIO_BODY_FONT_SIZE, 22)
        y += 22
    # (10) Resultado y cortesía (sin número)
    resultado_texto = "Por lo tanto, no existe constancia de inscripción militar a nombre del ciudadano indicado dentro de los registros físicos ni digitales de esta Oficina de Registro Militar Departamental N.° 055-A."
    if resultado.upper() == "POSITIVO":
        resultado_texto = "Por lo tanto, se deja constancia de la inscripción militar del ciudadano indicado dentro de los registros de esta Oficina de Registro Militar Departamental N.° 055-A, adjuntándose al presente oficio la documentación sustentatoria correspondiente."
    resultado_sangrado = f"{sangria}{resultado_texto}"
    insert_textbox_justified(resultado_sangrado, y, OFICIO_BODY_FONT_SIZE, 60)
    y += 60
    insert_textbox_justified("Hago propicia la oportunidad para expresarle las seguridades de mi especial consideración y estima personal.", y, OFICIO_BODY_FONT_SIZE, 24)
    y += 24
    # (11) Dios guarde a Ud. a la derecha (sin número)
    insert_text_right("Dios guarde a Ud.", y, OFICIO_BODY_FONT_SIZE)
    y += 24
    # Imagen de la firma subida por el usuario, debajo del punto 11 (aumentada 40% más y alineada a la derecha)
    if firma_img_path and os.path.exists(firma_img_path):
        sig_w = int(220 * 2.37)
        sig_h = int(60 * 2.37)
        x_sig = width - mx - sig_w + int(45 * 2.835)
        sig_rect = fitz.Rect(x_sig, y - int(5 * 2.835), x_sig + sig_w, y + sig_h - int(5 * 2.835))
        try:
            pagepdf.insert_image(sig_rect, filename=firma_img_path, keep_proportion=True)
        except Exception:
            pass
        y += sig_h + 18
    # Distribución (sin número)
    pagepdf.insert_text((mx, height - 80), "Distribución:", fontsize=OFICIO_FOOTER_FONT_SIZE, fontname=FONT_NAME, color=BLACK)
    off_y = height - 68
    # Cargo dinámico en distribución
    cargo_dist = cargo_dest if cargo_dest else "-"
    pagepdf.insert_text((mx + 20, off_y), f"{cargo_dist} ……………………………01", fontsize=OFICIO_FOOTER_FONT_SIZE, fontname=FONT_NAME, color=BLACK)
    off_y += 12
    pagepdf.insert_text((mx + 20, off_y), "-Archivo …………………………………… 01", fontsize=OFICIO_FOOTER_FONT_SIZE, fontname=FONT_NAME, color=BLACK)
    docpdf.save(out_path)
    docpdf.close()
    return out_path
