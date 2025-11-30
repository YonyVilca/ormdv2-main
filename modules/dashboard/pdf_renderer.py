"""PDF rendering utilities for OFICIO and BUSQUEDA reports.
Separated from data.py for easier editing.
"""
from __future__ import annotations
import os
from datetime import datetime
from typing import List, Optional

try:
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except Exception:  # Pillow optional for watermark/banner processing
    Image = None  # type: ignore

# ---------------------- CONSTANTES DE DISEÑO ----------------------

OFICIO_MARGIN_X = 50
OFICIO_MARGIN_Y = 50
OFICIO_WRAP_CHARS = 95
OFICIO_LINE_HEIGHT = 16
OFICIO_PARAGRAPH_SPACING = 6
OFICIO_AFTER_BODY_SPACING = 20
OFICIO_HEADER_TITLE_SIZE = 12   # Título reducido
OFICIO_BODY_FONT_SIZE = 12      # Texto cuerpo
OFICIO_MOTTO_FONT_SIZE = 10     # Lema / Año fiscal más pequeño
OFICIO_DATE_FONT_SIZE = 10      # Ciudad y fecha
OFICIO_FOOTER_FONT_SIZE = 12    # Footer mantiene legibilidad
WATERMARK_SCALE_RATIO = 0.4    # % del ancho de la página

BUSQUEDA_MARGIN_X = 50
BUSQUEDA_MARGIN_TOP = 50
BUSQUEDA_WRAP_CHARS = 95
BUSQUEDA_LINE_HEIGHT = 15
BUSQUEDA_SECTION_TITLE_SIZE = 12
BUSQUEDA_TITLE_SIZE = 15
BUSQUEDA_INSTITUTION_SIZE = 18
BUSQUEDA_FOOTER_FONT_SIZE = 9

FONT_NAME = "helv"
BLACK = (0, 0, 0)
FONT_BOLD = "helvb"  # variante negrita; se validará y se caerá a FONT_NAME si no existe

DISTRIBUCION = [
    "- RENIEC · Lima ...................... 01",
    "- Archivo ............................... 01",
]


class PdfGenerationError(RuntimeError):
    pass


def _assert_fitz():
    if not fitz:
        raise PdfGenerationError("PyMuPDF no disponible; instale 'pymupdf'.")


# -------------------------------------------------------------------
#                             OFICIO
# -------------------------------------------------------------------

def generate_oficio_pdf(
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
    motto_text: str,
    logo_path: Optional[str],
    banner_path: Optional[str],
    watermark: bool,
    firmante_nombre: str,
    firmante_cargo: str,
    usuario_actual: str,  # no se imprime, se mantiene por compatibilidad
    rol_actual: str,      # idem
    ciudadano_line: str,
    firma_img_path: Optional[str] = None,
    office_number: str = "055-A",
    codigo_oficio_suffix: str = "/ORMD-55-A/SEC REG MIL/S-6. f.1",  # sufijo editable
) -> str:
    """Renderiza el PDF de OFICIO y devuelve la ruta generada."""
    _assert_fitz()
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(
        out_dir, f"oficio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    docpdf = fitz.open()
    pagepdf = docpdf.new_page()
    width, height = pagepdf.rect.width, pagepdf.rect.height
    mx, my = OFICIO_MARGIN_X, OFICIO_MARGIN_Y
    y = my

    if not ciudad or not ciudad.strip():
        ciudad = "Arequipa"

    # ------------------- Descubrimiento de recursos -------------------

    def _auto_discover(primary: Optional[str], fallbacks: list[str]) -> Optional[str]:
        if primary and os.path.exists(primary):
            return primary
        for fp in fallbacks:
            if fp and os.path.exists(fp):
                return fp
        return None

    resolved_logo = _auto_discover(
        logo_path,
        [
            os.path.join("assets", "ormd sin fondo.png"),
            os.path.join("assets", "logo.png"),
            os.path.join("assets", "logo.jpg"),
            os.path.join("assets", "logo.jpeg"),
        ],
    )
    resolved_banner = _auto_discover(
        banner_path,
        [
            os.path.join("assets", "encabezado01.png"),
            os.path.join("assets", "banner_ormd.png"),
            os.path.join("assets", "banner.png"),
            os.path.join("assets", "banner.jpg"),
        ],
    )

    def _find_signature() -> Optional[str]:
        candidatos = [
            os.path.join("assets", "firma_jefatura.png"),
            os.path.join("assets", "firma.png"),
            os.path.join("assets", "firma.jpg"),
            os.path.join("assets", "sello_firma.png"),
        ]
        for c in candidatos:
            if c and os.path.exists(c):
                return c

        assets_dir = "assets"
        if os.path.isdir(assets_dir):
            for fname in os.listdir(assets_dir):
                low = fname.lower()
                if any(k in low for k in ("firma", "sello", "jefatura")) and low.endswith(
                    (".png", ".jpg", ".jpeg")
                ):
                    return os.path.join(assets_dir, fname)
        return None

    resolved_firma = _find_signature()

    # -------------------------- Cabecera --------------------------------

    def _draw_header(page):
        nonlocal y
        local_width, _ = page.rect.width, page.rect.height
        yy = my
        drew = False

        if resolved_banner and Image:
            try:
                bimg = Image.open(resolved_banner)
                target_w = int(local_width - mx * 2)
                if bimg.width > target_w:
                    scale = target_w / bimg.width
                    target_h = int(bimg.height * scale)
                    resized = bimg.resize((target_w, target_h), Image.LANCZOS)
                else:
                    target_w, target_h = bimg.width, bimg.height
                    resized = bimg

                import tempfile
                tmpb = os.path.join(
                    tempfile.gettempdir(), f"banner_{datetime.now().timestamp()}.png"
                )
                resized.save(tmpb)
                x_offset = (local_width - target_w) / 2
                page.insert_image(
                    fitz.Rect(x_offset, yy, x_offset + target_w, yy + target_h),
                    filename=tmpb,
                    keep_proportion=True,
                )
                yy += target_h + 10
                drew = True
            except Exception:
                drew = False

        if not drew and resolved_logo and os.path.exists(resolved_logo):
            try:
                page.insert_image(
                    fitz.Rect(mx, yy, mx + 65, yy + 65),
                    filename=resolved_logo,
                    keep_proportion=True,
                )
                yy += 75
            except Exception:
                pass

        y = yy

    _draw_header(pagepdf)

    # -------------------- Lema anual + fecha ---------------------------

    if motto_text:
        try:
            display_motto = motto_text.strip()
            if "AÑO" in display_motto.upper():
                display_motto = f"·{display_motto}·"
            else:
                display_motto = f"\u201C{display_motto}\u201D"
            try:
                text_len = pagepdf.get_text_length(
                    display_motto, fontsize=OFICIO_MOTTO_FONT_SIZE, fontname=FONT_NAME
                )
            except Exception:
                text_len = len(display_motto) * 6
            text_x = (width - text_len) / 2
            pagepdf.insert_text(
                (max(mx, text_x), y),
                display_motto,
                fontsize=OFICIO_MOTTO_FONT_SIZE,
                fontname=FONT_NAME,
                color=BLACK,
            )
            y += 22
        except Exception:
            pass

    fecha_str = f"{ciudad.strip()}, {fecha}"
    try:
        fecha_len = pagepdf.get_text_length(
            fecha_str, fontsize=OFICIO_DATE_FONT_SIZE, fontname=FONT_NAME
        )
    except Exception:
        fecha_len = len(fecha_str) * 6
    fecha_x = width - OFICIO_MARGIN_X - fecha_len
    pagepdf.insert_text(
        (fecha_x, y),
        fecha_str,
        fontsize=OFICIO_DATE_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    y += 26

    # --------------------- Marca de agua (fondo) ------------------------

    if watermark and resolved_logo and os.path.exists(resolved_logo) and Image:
        try:
            img = Image.open(resolved_logo).convert("RGBA")
            alpha = img.split()[3]
            alpha = alpha.point(lambda p: int(p * 0.10))
            img.putalpha(alpha)
            target_w = int(width * WATERMARK_SCALE_RATIO)
            scale = target_w / img.width
            target_h = int(img.height * scale)
            img = img.resize((target_w, target_h), Image.LANCZOS)

            import tempfile
            tmp_file = os.path.join(
                tempfile.gettempdir(), f"wm_{datetime.now().strftime('%s')}.png"
            )
            img.save(tmp_file, format="PNG")
            center_x = (width - target_w) / 2
            center_y = (height - target_h) / 2
            pagepdf.insert_image(
                fitz.Rect(center_x, center_y, center_x + target_w, center_y + target_h),
                filename=tmp_file,
                keep_proportion=True,
                overlay=False,
            )
        except Exception:
            pass

    # ---------------- Cabecera tipo oficio (Oficio N°, etc.) -----------

    pagepdf.insert_text(
        (mx, y),
        f"Oficio N° {numero_oficio.strip()} {codigo_oficio_suffix}",
        fontsize=OFICIO_HEADER_TITLE_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    y += 30

    label_x = mx
    value_x = mx + 80

    # Señor(a)
    destinatario_full = destinatario
    if cargo_dest:
        destinatario_full += f" {cargo_dest}"
    if entidad_dest:
        destinatario_full += f" – {entidad_dest}"
    pagepdf.insert_text(
        (label_x, y),
        "Señor(a):",
        fontsize=OFICIO_BODY_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    pagepdf.insert_text(
        (value_x, y),
        destinatario_full,
        fontsize=OFICIO_BODY_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    y += 24

    # Asunto
    pagepdf.insert_text(
        (label_x, y),
        "Asunto:",
        fontsize=OFICIO_BODY_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    pagepdf.insert_text(
        (value_x, y),
        asunto,
        fontsize=OFICIO_BODY_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    y += 24

    # Referencia
    if referencia:
        pagepdf.insert_text(
            (label_x, y),
            "Ref.",
            fontsize=OFICIO_BODY_FONT_SIZE,
            fontname=FONT_NAME,
            color=BLACK,
        )
        pagepdf.insert_text(
            (value_x, y),
            referencia.strip(),
            fontsize=OFICIO_BODY_FONT_SIZE,
            fontname=FONT_NAME,
            color=BLACK,
        )
        y += 28

    # ----------------------- Helper de párrafos ------------------------

    def _draw_paragraph(par: str):
        nonlocal y
        texto = par.strip()
        if not texto:
            y += OFICIO_PARAGRAPH_SPACING
            return
        import textwrap as _tw_local
        raw_lines = texto.split("\n")
        lines: list[str] = []
        for rl in raw_lines:
            rls = rl.strip()
            if not rls:
                lines.append("")
                continue
            wrapped = _tw_local.wrap(rls, width=OFICIO_WRAP_CHARS) or [rls]
            lines.extend(wrapped)

        needed_height = len(lines) * OFICIO_LINE_HEIGHT
        available = height - OFICIO_MARGIN_Y - y
        if needed_height > available:
            max_lines = max(0, available // OFICIO_LINE_HEIGHT - 1)
            lines = lines[:max_lines]
            needed_height = len(lines) * OFICIO_LINE_HEIGHT

        rect = fitz.Rect(mx, y, width - mx, y + needed_height + 2)
        try:
            pagepdf.insert_textbox(
                rect,
                "\n".join(lines),
                fontsize=OFICIO_BODY_FONT_SIZE,
                fontname=FONT_NAME,
                color=BLACK,
                align=4,  # justificado
            )
        except Exception:
            cy = y
            for ln in lines:
                if cy > height - OFICIO_MARGIN_Y - OFICIO_LINE_HEIGHT:
                    break
                pagepdf.insert_text(
                    (mx, cy),
                    ln,
                    fontsize=OFICIO_BODY_FONT_SIZE,
                    fontname=FONT_NAME,
                    color=BLACK,
                )
                cy += OFICIO_LINE_HEIGHT
        y += needed_height + OFICIO_PARAGRAPH_SPACING

    # ----------------------- Cuerpo del oficio estructurado -------------------------
    # 4. Mensaje de saludo y contexto
    _draw_paragraph("(4) Tengo el agrado de dirigirme a usted para expresarle un cordial saludo y, en atención al documento de la referencia, informarle lo siguiente:")
    _draw_paragraph("(4) En la verificación realizada en nuestros registros sobre la existencia de ficha de inscripción militar de los ciudadanos señalados en el documento de la referencia, se ha procedido a realizar la búsqueda, con el resultado siguiente:")

    # 5. Datos del ciudadano (del sistema o manuales)
    import textwrap as _tw_local
    datos_ciudadano = []
    if ciudadano_line:
        for cline in ciudadano_line.splitlines():
            for wrapped in _tw_local.wrap(cline, width=OFICIO_WRAP_CHARS) or [cline]:
                datos_ciudadano.append(wrapped)
    _draw_paragraph("(5) DATOS DEL CIUDADANO:")
    if datos_ciudadano:
        for dline in datos_ciudadano:
            _draw_paragraph(f"(5) {dline}")
    else:
        # Si no hay datos, mostrar ejemplo para pruebas
        _draw_paragraph("(5) APELLIDOS Y NOMBRES: [No disponible]")
        _draw_paragraph("(5) FECHA DE NACIMIENTO: [No disponible]")
        _draw_paragraph("(5) LIBRETA MILITAR: [No disponible]")
        _draw_paragraph("(5) RESULTADO: [No disponible]")

    # 6. Mensaje positivo/negativo
    if resultado.upper() == "NEGATIVO":
        _draw_paragraph(
            "Por lo tanto, no existe constancia de inscripción militar a nombre del "
            "ciudadano indicado dentro de los registros físicos ni digitales de esta "
            f"Oficina de Registro Militar Departamental N.° {office_number}."
        )
    else:
        _draw_paragraph(
            "Por lo tanto, se deja constancia de la inscripción militar del ciudadano "
            "indicado dentro de los registros de esta Oficina de Registro Militar "
            f"Departamental N.° {office_number}, adjuntándose al presente oficio la "
            "documentación sustentatoria correspondiente."
        )

    _draw_paragraph(
        "Hago propicia la oportunidad para expresarle las seguridades de mi especial "
        "consideración y estima personal."
    )

    y += OFICIO_AFTER_BODY_SPACING

    # ----------------- “Dios guarde a Ud.” + firma ---------------------

    texto_dios = "Dios guarde a Ud."
    try:
        dios_len = pagepdf.get_text_length(
            texto_dios, fontsize=OFICIO_BODY_FONT_SIZE, fontname=FONT_NAME
        )
    except Exception:
        dios_len = len(texto_dios) * 6
    dios_x = width - mx - dios_len
    pagepdf.insert_text(
        (dios_x, y),
        texto_dios,
        fontsize=OFICIO_BODY_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    y += 24

    if resolved_firma and os.path.exists(resolved_firma):
        sig_w = 220
        sig_h = 120
        x_sig = width - mx - sig_w
        sig_rect = fitz.Rect(x_sig, y, x_sig + sig_w, y + sig_h)
        processed_path = resolved_firma
        if Image:
            try:
                from PIL import ImageEnhance, ImageFilter  # type: ignore
                _img = Image.open(resolved_firma).convert("RGBA")
                _img = ImageEnhance.Brightness(_img).enhance(1.35)
                _img = ImageEnhance.Contrast(_img).enhance(1.15)
                _img = _img.filter(ImageFilter.GaussianBlur(radius=1.2))
                r, g, b, a = _img.split()
                import numpy as np  # type: ignore
                arr = np.array(_img)
                mask = (arr[..., 0] < 40) & (arr[..., 1] < 40) & (arr[..., 2] < 40)
                arr[..., 3][mask] = 0
                _img = Image.fromarray(arr)
                a = _img.split()[3].point(lambda p: int(p * 0.60))
                _img.putalpha(a)
                import tempfile
                processed_path = os.path.join(
                    tempfile.gettempdir(), f"firma_{datetime.now().timestamp()}.png"
                )
                _img.save(processed_path, format="PNG")
            except Exception:
                processed_path = resolved_firma
        try:
            pagepdf.insert_image(
                sig_rect, filename=processed_path, keep_proportion=True
            )
        except Exception:
            pass

    # ----------------------------- Distribución ------------------------

    pagepdf.insert_text(
        (mx, height - 80),
        "Distribución:",
        fontsize=OFICIO_FOOTER_FONT_SIZE,
        fontname=FONT_NAME,
        color=BLACK,
    )
    off_y = height - 68
    for dline in DISTRIBUCION:
        pagepdf.insert_text(
            (mx + 20, off_y),
            dline,
            fontsize=OFICIO_FOOTER_FONT_SIZE,
            fontname=FONT_NAME,
            color=BLACK,
        )
        off_y += 12

    docpdf.save(out_path)
    docpdf.close()
    return out_path
