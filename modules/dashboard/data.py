def generate_busqueda_pdf(out_dir, lines, usuario_actual, rol_actual, institucion):
    try:
        from fpdf import FPDF
    except ImportError:
        import subprocess; subprocess.run(["pip", "install", "fpdf"])
        from fpdf import FPDF
    path = os.path.join(out_dir, "busqueda_preview.pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Institución: {institucion}", ln=True)
    pdf.cell(200, 10, txt=f"Usuario: {usuario_actual} | Rol: {rol_actual}", ln=True)
    pdf.ln(5)
    # Mostrar todos los datos relevantes
    for line in lines:
        # Reemplazar bullets y caracteres incompatibles
        safe_line = line.replace("•", "-").replace("–", "-")
        pdf.multi_cell(0, 10, txt=safe_line.encode('latin-1', 'replace').decode('latin-1'))
    pdf.output(path)
    return path
def build_ciudadano_line(apellidos, nombres, fecha_nac, lm, resultado):
    return f"{apellidos}, {nombres} | Fecha Nac: {fecha_nac} | LM: {lm} | Resultado: {resultado}"
"""Gestión de Datos (Ciudadanos) UI and logic."""

import os
import json
import shutil
import base64
import subprocess
from datetime import datetime
from config.settings import Config
from typing import List, Optional

import flet as ft
from modules.dashboard.pdf_renderer import (
    generate_oficio_pdf,
)
from modules.dashboard.pdf_renderer_vs2 import generate_oficio_pdf_vs2

try:  # PyMuPDF
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

from sqlalchemy import select, or_

from database.connection import SessionLocal
from database import models
ACCENT_COLOR = ft.Colors.GREEN_600
PRIMARY_COLOR = ft.Colors.GREEN_800
SECONDARY_COLOR = ft.Colors.RED_600  # Bandera Perú / énfasis
NEUTRAL_COLOR = ft.Colors.BLUE_GREY_100
BG_COLOR = ft.Colors.GREEN_50
CARD_BG = ft.Colors.WHITE
CARD_BORDER_COLOR = ft.Colors.GREEN_100


def _fmt_date(d):
    return d.strftime("%Y-%m-%d") if d else ""


def _fetch_citizens(search: str = "") -> List[models.Ciudadano]:
    """Obtiene hasta 200 ciudadanos, aplicando filtro LIKE si hay búsqueda."""
    session = SessionLocal()
    try:
        stmt = select(models.Ciudadano).order_by(models.Ciudadano.id_ciudadano.desc()).limit(200)
        if search:
            like = f"%{search.upper()}%"
            stmt = (
                select(models.Ciudadano)
                .where(
                    or_(
                        models.Ciudadano.dni.like(like),
                        models.Ciudadano.lm.like(like),
                        models.Ciudadano.apellidos.like(like),
                        models.Ciudadano.nombres.like(like),
                    )
                )
                .order_by(models.Ciudadano.id_ciudadano.desc())
                .limit(200)
            )
        rows = session.execute(stmt).scalars().all()
        return rows
    finally:
        session.close()


def _fetch_documents(id_ciudadano: int) -> List[models.Documento]:
    session = SessionLocal()
    try:
        stmt = (
            select(models.Documento)
            .join(models.CiudadanoDocumento, models.CiudadanoDocumento.id_documento == models.Documento.id_documento)
            .where(models.CiudadanoDocumento.id_ciudadano == id_ciudadano)
            .order_by(models.Documento.id_documento.desc())
        )
        return session.execute(stmt).scalars().all()
    finally:
        session.close()


def _update_citizen(c: models.Ciudadano, dni: str, lm: str, ap: str, no: str, uid: Optional[int]) -> bool:
    """Update citizen base fields in DB. Inputs should be uppercase already."""
    session = SessionLocal()
    try:
        db_c = session.get(models.Ciudadano, c.id_ciudadano)
        if not db_c:
            return False
        db_c.dni = (dni or "").strip() or None
        db_c.lm = (lm or "").strip() or None
        db_c.apellidos = (ap or "").strip() or None
        db_c.nombres = (no or "").strip() or None
        db_c.fecha_ultima_modificacion = datetime.now()
        if uid:
            db_c.id_usuario_ultima_modificacion = uid
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def build(page: ft.Page, user_data: Optional[dict] = None) -> ft.Control:
    """Builds the Gestión de Datos view."""

    def _norm_role(name: str) -> str:
        n = (name or "").strip().lower()
        mapping = {
            "administrador": "administrador",
            "admin": "administrador",
            "acceso 1": "administrador",
            "editor": "editor",
            "acceso 2": "editor",
            "operador": "operador",
            "ingresador": "operador",
            "acceso 3": "operador",
            "consulta": "consulta",
            "acceso 4": "consulta",
        }
        return mapping.get(n, n)

    def is_admin() -> bool:
        if not user_data:
            return False
        name = (user_data.get("rol") or user_data.get("rol_nombre") or "")
        if _norm_role(name) == "administrador":
            return True
        # fallback by id (if 1 is seeded as Admin)
        return str(user_data.get("id_rol", "")) == "1"

    def can_edit_data() -> bool:
        if not user_data:
            return False
        name = (user_data.get("rol") or user_data.get("rol_nombre") or "")
        return _norm_role(name) in ("administrador", "editor") or is_admin()

    # State
    citizens: List[models.Ciudadano] = []
    selected: Optional[models.Ciudadano] = None
    docs: List[models.Documento] = []
    servicio: Optional[models.DatosServicioMilitar] = None
    # Para reportes: recordar última búsqueda (para generar reporte sin selección)
    last_search_query: str = ""
    last_search_count: int = 0

    # Search and list
    search_field = ft.TextField(label="Buscar DNI / LM / Apellidos / Nombres", expand=True)
    refresh_btn = ft.FilledButton("Buscar", icon=ft.Icons.SEARCH)
    citizens_list = ft.ListView(expand=True, spacing=6, padding=0, auto_scroll=False)

    # Detail controls
    detail_title = ft.Text("Detalle del Ciudadano", size=20, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)
    dni_field = ft.TextField(label="DNI", width=200)
    lm_field = ft.TextField(label="Libreta Militar (LM)", width=220)
    apellidos_field = ft.TextField(label="Apellidos", expand=True)
    nombres_field = ft.TextField(label="Nombres", expand=True)
    fecha_nac_field = ft.TextField(label="Fecha Nacimiento (YYYY-MM-DD)", width=200)
    # Permitir solo números y formatear automáticamente a DD/MM/YYYY
    def format_fecha_nac(e):
        raw = (fecha_nac_field.value or "").strip()
        if raw.isdigit() and len(raw) == 8:
            # 11031998 → 11/03/1998
            formatted = f"{raw[:2]}/{raw[2:4]}/{raw[4:]}"
            fecha_nac_field.value = formatted
            fecha_nac_field.update()
    fecha_nac_field.on_blur = format_fecha_nac
    presto_dd = ft.Dropdown(label="¿Prestó servicio?", options=[ft.dropdown.Option("SI"), ft.dropdown.Option("NO")], width=180)

    # Servicio Militar fields
    clase_field = ft.TextField(label="Clase", width=120)
    libro_field = ft.TextField(label="Libro", width=120)
    folio_field = ft.TextField(label="Folio", width=120)
    ref_doc_field = ft.TextField(label="Ref. Doc Origen", width=200)
    fecha_alta_field = ft.TextField(label="Fecha Alta (YYYY-MM-DD)", width=180)
    fecha_baja_field = ft.TextField(label="Fecha Baja (YYYY-MM-DD)", width=180)
    unidad_alta_field = ft.TextField(label="Unidad Alta", width=220)
    unidad_baja_field = ft.TextField(label="Unidad Baja", width=220)
    grado_field = ft.TextField(label="Grado", width=160)
    motivo_baja_field = ft.TextField(label="Motivo Baja", width=220)

    save_detail_btn = ft.FilledButton("Guardar Cambios", icon=ft.Icons.SAVE)
    report_btn = ft.FilledTonalButton(
        "Reporte",
        icon=ft.Icons.DESCRIPTION,
        style=ft.ButtonStyle(
            padding={"left":16, "right":20, "top":12, "bottom":12},
            shape=ft.RoundedRectangleBorder(radius=22),
            bgcolor={ft.ControlState.DEFAULT: ft.Colors.BLUE_GREY_100, ft.ControlState.HOVERED: ft.Colors.BLUE_GREY_200},
        ),
        tooltip="Generar reporte / oficio",
    )
    add_files_btn = ft.OutlinedButton("Añadir Archivos", icon=ft.Icons.ATTACH_FILE)
    delete_btn = ft.OutlinedButton(
        "Eliminar Ciudadano",
        icon=ft.Icons.DELETE_OUTLINE,
        style=ft.ButtonStyle(color=ft.Colors.RED_700),
    )

    # Uppercase enforcement
    def enforce_upper(tf: ft.TextField):
        def _on_change(e: ft.ControlEvent):
            new = (tf.value or "").upper()
            if new != tf.value:
                tf.value = new
                try:
                    import json
                    tf.update()
                except Exception:
                    pass
        tf.on_change = _on_change

    for _tf in [search_field, dni_field, lm_field, apellidos_field, nombres_field, clase_field, libro_field, folio_field, ref_doc_field, unidad_alta_field, unidad_baja_field, grado_field, motivo_baja_field]:
        enforce_upper(_tf)

    # Citizens list
    # Consulta logging
    def _log_consulta(c: models.Ciudadano):
        try:
            import json
            from datetime import datetime as _dt
            logs_dir = os.path.join("storage", "data", "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_path = os.path.join(logs_dir, "consultas.jsonl")
            rec = {
                "ts": _dt.now().isoformat(),
                "id_usuario": (user_data or {}).get("id_usuario"),
                "usuario": (user_data or {}).get("username") or (user_data or {}).get("nombre_usuario"),
                "rol": (user_data or {}).get("rol") or (user_data or {}).get("rol_nombre"),
                "accion": "consulta_ciudadano",
                "id_ciudadano": c.id_ciudadano,
                "dni": c.dni,
                "lm": c.lm,
                "apellidos": c.apellidos,
                "nombres": c.nombres,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _log_busqueda(query: str, resultados: int):
        try:
            import json
            from datetime import datetime as _dt
            logs_dir = os.path.join("storage", "data", "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_path = os.path.join(logs_dir, "consultas.jsonl")
            rec = {
                "ts": _dt.now().isoformat(),
                "id_usuario": (user_data or {}).get("id_usuario"),
                "usuario": (user_data or {}).get("username") or (user_data or {}).get("nombre_usuario"),
                "rol": (user_data or {}).get("rol") or (user_data or {}).get("rol_nombre"),
                "accion": "busqueda",
                "query": query,
                "resultados": resultados,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def pick(c: models.Ciudadano):
        nonlocal selected, docs
        selected = c
        populate_detail()
        docs = _fetch_documents(c.id_ciudadano)
        populate_docs()
        populate_service()
        _log_consulta(c)
        page.update()

    def populate_citizens():
        citizens_list.controls.clear()
        for c in citizens:
            linea1 = f"{c.apellidos or ''}, {c.nombres or ''}"
            linea2 = f"DNI: {c.dni or '-'} • LM: {c.lm or '-'}"
            linea3 = f"ID: {c.id_ciudadano}"
            item = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(linea1, weight=ft.FontWeight.W_600),
                        ft.Text(linea2, size=12, color=ft.Colors.BLUE_GREY_600),
                        ft.Text(linea3, size=11, color=ft.Colors.BLUE_GREY_600),
                    ], spacing=3, expand=True),
                    ft.IconButton(icon=ft.Icons.VISIBILITY, tooltip="Ver", icon_size=18, padding=ft.padding.all(4), on_click=lambda e, c=c: pick(c)),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                on_click=lambda e, c=c: pick(c),
            )
            citizens_list.controls.append(item)

    def load_citizens():
        nonlocal citizens
        citizens = _fetch_citizens((search_field.value or "").strip())
        populate_citizens()
        page.update()

    # Detail population
    def populate_detail():
        if not selected:
            detail_title.value = "Detalle del Ciudadano"
            dni_field.value = ""
            lm_field.value = ""
            apellidos_field.value = ""
            nombres_field.value = ""
            fecha_nac_field.value = ""
            presto_dd.value = None
            save_detail_btn.disabled = True
            add_files_btn.disabled = True
            delete_btn.disabled = True
        else:
            detail_title.value = f"Ciudadano #{selected.id_ciudadano}"
            dni_field.value = selected.dni or ""
            lm_field.value = selected.lm or ""
            apellidos_field.value = selected.apellidos or ""
            nombres_field.value = selected.nombres or ""
            fecha_nac_field.value = selected.fecha_nacimiento.strftime("%Y-%m-%d") if selected.fecha_nacimiento else ""
            presto_dd.value = "SI" if selected.presto_servicio else ("NO" if selected.presto_servicio is not None else None)
            save_detail_btn.disabled = not can_edit_data()
            add_files_btn.disabled = False
            delete_btn.disabled = not is_admin()

    # Service population
    def populate_service():
        nonlocal servicio
        if not selected:
            for f in [clase_field, libro_field, folio_field, ref_doc_field, fecha_alta_field, fecha_baja_field, unidad_alta_field, unidad_baja_field, grado_field, motivo_baja_field]:
                f.value = ""
            return
        session = SessionLocal()
        ua = ub = gr = mb = ""
        try:
            servicio = session.execute(
                select(models.DatosServicioMilitar).where(models.DatosServicioMilitar.id_ciudadano == selected.id_ciudadano)
            ).scalar_one_or_none()
            if servicio:
                # Touch relationships while session is open
                ua = servicio.unidad_alta.nombre_unidad if servicio.unidad_alta else ""
                ub = servicio.unidad_baja.nombre_unidad if servicio.unidad_baja else ""
                gr = servicio.grado.descripcion if servicio.grado else ""
                mb = servicio.motivo_baja.descripcion if servicio.motivo_baja else ""
        finally:
            session.close()
        if not servicio:
            for f in [clase_field, libro_field, folio_field, ref_doc_field, fecha_alta_field, fecha_baja_field, unidad_alta_field, unidad_baja_field, grado_field, motivo_baja_field]:
                f.value = ""
        else:
            clase_field.value = servicio.clase or ""
            libro_field.value = servicio.libro or ""
            folio_field.value = servicio.folio or ""
            ref_doc_field.value = servicio.referencia_documento_origen or ""
            fecha_alta_field.value = _fmt_date(servicio.fecha_alta)
            fecha_baja_field.value = _fmt_date(servicio.fecha_baja)
            unidad_alta_field.value = ua
            unidad_baja_field.value = ub
            grado_field.value = gr
            motivo_baja_field.value = mb

    # Save with confirmation modal
    def save_detail(e):
        if not selected:
            return

        def do_real_save():
            from datetime import datetime as _dt
            uid = (user_data or {}).get("id_usuario")
            # Parse fecha nacimiento
            fnac_raw = (fecha_nac_field.value or "").strip()
            fnac_val = None
            if fnac_raw:
                try:
                    fnac_val = _dt.strptime(fnac_raw, "%Y-%m-%d").date()
                except Exception:
                    page.dialog = ft.AlertDialog(
                        title=ft.Text("Fecha inválida"),
                        content=ft.Text("Fecha de nacimiento no válida. Formato: YYYY-MM-DD"),
                        modal=True,
                    )
                    page.dialog.open = True
                    page.update()
                    return

            ok = _update_citizen(
                selected,
                (dni_field.value or "").upper(),
                (lm_field.value or "").upper(),
                (apellidos_field.value or "").upper(),
                (nombres_field.value or "").upper(),
                uid,
            )

            if ok:
                session2 = SessionLocal()
                try:
                    db_c = session2.get(models.Ciudadano, selected.id_ciudadano)
                    if db_c:
                        db_c.fecha_nacimiento = fnac_val
                        val_presto = presto_dd.value
                        if val_presto == "SI":
                            db_c.presto_servicio = True
                        elif val_presto == "NO":
                            db_c.presto_servicio = False
                        db_c.fecha_ultima_modificacion = datetime.now()
                        if uid:
                            db_c.id_usuario_ultima_modificacion = uid
                        # Servicio militar
                        serv = session2.execute(
                            select(models.DatosServicioMilitar).where(models.DatosServicioMilitar.id_ciudadano == db_c.id_ciudadano)
                        ).scalar_one_or_none()
                        def _parse_date(s: Optional[str]):
                            s = (s or "").strip()
                            if not s:
                                return None
                            try:
                                return _dt.strptime(s, "%Y-%m-%d").date()
                            except Exception:
                                return None
                        if not serv:
                            serv = models.DatosServicioMilitar(id_ciudadano=db_c.id_ciudadano)
                            session2.add(serv)
                        serv.clase = (clase_field.value or "").upper() or None
                        serv.libro = (libro_field.value or "").upper() or None
                        serv.folio = (folio_field.value or "").upper() or None
                        serv.referencia_documento_origen = (ref_doc_field.value or "").upper() or None
                        serv.fecha_alta = _parse_date(fecha_alta_field.value)
                        serv.fecha_baja = _parse_date(fecha_baja_field.value)
                        session2.commit()
                except Exception as ex:
                    session2.rollback()
                    page.dialog = ft.AlertDialog(title=ft.Text("Error"), content=ft.Text(str(ex)), modal=True)
                    page.dialog.open = True
                    page.update()
                    return
                finally:
                    session2.close()

            if ok:
                done = ft.AlertDialog(
                    title=ft.Text("Cambios guardados"),
                    content=ft.Text("Los datos fueron actualizados correctamente."),
                    modal=True,
                )
                page.open(done)
                load_citizens()
                for _c in citizens:
                    if _c.id_ciudadano == selected.id_ciudadano:
                        pick(_c)
                        break
            else:
                page.dialog = ft.AlertDialog(title=ft.Text("Error"), content=ft.Text("No se pudo actualizar"), modal=True)
                page.dialog.open = True
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("¿Guardar cambios?", weight=ft.FontWeight.BOLD),
            content=ft.Text("Se actualizarán los datos del ciudadano."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.FilledButton("Guardar", icon=ft.Icons.SAVE, on_click=lambda e: (page.close(dlg), do_real_save())),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )
        page.open(dlg)

    save_detail_btn.on_click = save_detail

    # File picker for documents
    file_picker = ft.FilePicker()
    try:
        page.overlay.append(file_picker)
    except Exception:
        pass

    def add_files(e):
        if not selected:
            return

        def on_result(res: ft.FilePickerResultEvent):
            if not res or not res.files:
                return
            session = SessionLocal()
            try:
                base_dir = os.path.join("storage", "data")
                os.makedirs(base_dir, exist_ok=True)
                for f in res.files:
                    src = f.path
                    if not src or not os.path.exists(src):
                        continue
                    name = os.path.basename(src)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    dst = os.path.join(base_dir, f"{ts}_{name}")
                    shutil.copy2(src, dst)

                    # Crear Documento y vincular
                    doc = models.Documento(
                        nombre_archivo=name,
                        ruta_almacenamiento=os.path.abspath(dst),
                        fecha_extraccion=datetime.now(),
                        id_usuario_extraccion=(user_data or {}).get("id_usuario") or 1,
                    )
                    session.add(doc)
                    session.flush()
                    session.add(models.CiudadanoDocumento(id_ciudadano=selected.id_ciudadano, id_documento=doc.id_documento))
                session.commit()
                # recargar docs
                nonlocal docs
                docs = _fetch_documents(selected.id_ciudadano)
                populate_docs()
                page.snack_bar = ft.SnackBar(content=ft.Text("Archivo(s) añadidos"), open=True)
                # Notificar a Inicio para refrescar métricas (documento digitalizado nuevo)
                try:
                    if hasattr(page, "pubsub") and hasattr(page.pubsub, "send_all"):
                        page.pubsub.send_all({"type": "stats_changed"})
                except Exception:
                    pass
            except Exception as ex:
                session.rollback()
                page.dialog = ft.AlertDialog(title=ft.Text("Error"), content=ft.Text(str(ex)), modal=True)
                page.dialog.open = True
            finally:
                session.close()
                page.update()

        file_picker.on_result = on_result
        file_picker.pick_files(allow_multiple=True)

    add_files_btn.on_click = add_files

    # Delete with confirmation
    # Auditoría de eliminaciones
    def _log_eliminacion(payload: dict):
        try:
            import json
            from datetime import datetime as _dt
            logs_dir = os.path.join("storage", "data", "logs")
            os.makedirs(logs_dir, exist_ok=True)
            log_path = os.path.join(logs_dir, "auditoria_eliminaciones.jsonl")
            payload = dict(payload)
            payload["ts"] = _dt.now().isoformat()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _trash_move(path: str) -> tuple[bool, str]:
        try:
            trash_dir = os.path.join("storage", "data", ".trash")
            os.makedirs(trash_dir, exist_ok=True)
            base = os.path.basename(path)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dst = os.path.join(trash_dir, f"{ts}_{base}")
            shutil.move(path, dst)
            return True, dst
        except Exception:
            return False, ""

    def on_delete(e):
        if not selected or not is_admin():
            return

        delete_files_chk = ft.Checkbox(label="Eliminar archivos físicos", value=True)
        # Mostrar resumen previo
        info_prev = ft.Text(
            f"Se eliminará el ciudadano ID {selected.id_ciudadano} y sus referencias. Los documentos que queden sin otros vínculos también se eliminarán.",
            size=12,
        )

        def confirm(_):
            nonlocal selected, docs
            session = SessionLocal()
            files_to_trash = []
            removed_docs = 0
            removed_files = 0
            snapshot = {}
            try:
                # Snapshot del ciudadano, servicio y documentos antes de borrar
                snap_docs = []
                try:
                    # capturar datos visibles
                    snap_c = {
                        "id_ciudadano": selected.id_ciudadano,
                        "dni": selected.dni,
                        "lm": selected.lm,
                        "apellidos": selected.apellidos,
                        "nombres": selected.nombres,
                        "fecha_nacimiento": _fmt_date(selected.fecha_nacimiento),
                        "presto_servicio": selected.presto_servicio,
                    }
                    # servicio militar (si existe)
                    serv = session.execute(
                        select(models.DatosServicioMilitar).where(models.DatosServicioMilitar.id_ciudadano == selected.id_ciudadano)
                    ).scalar_one_or_none()
                    snap_serv = None
                    if serv:
                        snap_serv = {
                            "id_servicio": serv.id_servicio,
                            "id_unidad_alta": serv.id_unidad_alta,
                            "id_unidad_baja": serv.id_unidad_baja,
                            "id_grado": serv.id_grado,
                            "id_motivo_baja": serv.id_motivo_baja,
                            "referencia_documento_origen": serv.referencia_documento_origen,
                            "clase": serv.clase,
                            "libro": serv.libro,
                            "folio": serv.folio,
                            "fecha_alta": _fmt_date(serv.fecha_alta),
                            "fecha_baja": _fmt_date(serv.fecha_baja),
                        }
                    for d in _fetch_documents(selected.id_ciudadano):
                        snap_docs.append({
                            "id_documento": d.id_documento,
                            "nombre_archivo": d.nombre_archivo,
                            "ruta_almacenamiento": d.ruta_almacenamiento,
                        })
                    # Enlaces documento-servicio si hubiera servicio
                    ds_links = []
                    if serv:
                        dsl = session.execute(
                            select(models.DocumentoServicio).where(models.DocumentoServicio.id_servicio == serv.id_servicio)
                        ).scalars().all()
                        ds_links = [{"id_documento": x.id_documento} for x in dsl]
                    snapshot = {"ciudadano": snap_c, "servicio": snap_serv, "documentos": snap_docs, "doc_servicio": ds_links}
                except Exception:
                    snapshot = {}
                # 1) Eliminar vínculos ciudadano-documento y recolectar documentos relacionados
                links = session.execute(
                    select(models.CiudadanoDocumento).where(models.CiudadanoDocumento.id_ciudadano == selected.id_ciudadano)
                ).scalars().all()
                doc_ids = [ln.id_documento for ln in links]
                for ln in links:
                    session.delete(ln)

                # 2) Eliminar servicio militar y sus vínculos con documentos
                serv = session.execute(
                    select(models.DatosServicioMilitar).where(models.DatosServicioMilitar.id_ciudadano == selected.id_ciudadano)
                ).scalar_one_or_none()
                if serv:
                    ds_links = session.execute(
                        select(models.DocumentoServicio).where(models.DocumentoServicio.id_servicio == serv.id_servicio)
                    ).scalars().all()
                    for dsl in ds_links:
                        session.delete(dsl)
                    session.delete(serv)

                # 3) Para cada Documento, si ya no está vinculado a ningún ciudadano, eliminar registro y programar borrado físico
                session.flush()  # que las eliminaciones previas afecten a consultas siguientes
                for did in set(doc_ids):
                    other_link = session.execute(
                        select(models.CiudadanoDocumento).where(models.CiudadanoDocumento.id_documento == did)
                    ).first()
                    if not other_link:
                        # limpiar vínculos del documento con servicios (si existieran)
                        dserv = session.execute(
                            select(models.DocumentoServicio).where(models.DocumentoServicio.id_documento == did)
                        ).scalars().all()
                        for r in dserv:
                            session.delete(r)

                        doc = session.get(models.Documento, did)
                        if doc:
                            path = doc.ruta_almacenamiento or ""
                            session.delete(doc)
                            removed_docs += 1
                            if path and os.path.exists(path):
                                files_to_trash.append(path)

                # 4) Eliminar ciudadano
                db_c = session.get(models.Ciudadano, selected.id_ciudadano)
                if db_c:
                    session.delete(db_c)

                session.commit()

                # 5) Mover a Papelera archivos ya sin referencias (si el usuario lo pidió)
                traslados = []
                if delete_files_chk.value:
                    for p in files_to_trash:
                        ok, dst = _trash_move(p)
                        if ok:
                            removed_files += 1
                            traslados.append({"from": p, "to": dst})

                # 6) Limpiar selección y refrescar UI
                selected = None
                docs = []
                populate_detail()
                populate_docs()
                load_citizens()
                # Auditoría
                _log_eliminacion({
                    "accion": "eliminacion_ciudadano",
                    "id_usuario": (user_data or {}).get("id_usuario"),
                    "usuario": (user_data or {}).get("username") or (user_data or {}).get("nombre_usuario"),
                    "rol": (user_data or {}).get("rol") or (user_data or {}).get("rol_nombre"),
                    "id_ciudadano": snapshot.get("ciudadano", {}).get("id_ciudadano"),
                    "removed_docs": removed_docs,
                    "removed_files": removed_files,
                    "files_moved": traslados,
                    "snapshot": snapshot,
                })

                # Confirmación explícita (modal cerrable)
                msg = f"Se eliminó el ciudadano. Documentos eliminados: {removed_docs}. Archivos físicos borrados: {removed_files}."
                ok_dlg = ft.AlertDialog(
                    title=ft.Text("Eliminación completa", weight=ft.FontWeight.BOLD),
                    content=ft.Column([
                        ft.Text(msg),
                        ft.Text("Acción registrada en auditoría.", size=11, color=ft.Colors.BLUE_GREY_600),
                    ], spacing=8),
                    actions=[ft.TextButton("OK", on_click=lambda ev: page.close(ok_dlg))],
                    actions_alignment=ft.MainAxisAlignment.END,
                    modal=True,
                )
                page.open(ok_dlg)

                # 7) Notificar a Inicio (estadísticas)
                try:
                    if hasattr(page, "pubsub") and hasattr(page.pubsub, "send_all"):
                        page.pubsub.send_all({"type": "stats_changed"})
                except Exception:
                    pass
            except Exception as ex:
                session.rollback()
                page.dialog = ft.AlertDialog(title=ft.Text("Error"), content=ft.Text(str(ex)), modal=True)
                page.dialog.open = True
            finally:
                page.update()
                session.close()

        dlg = ft.AlertDialog(
            title=ft.Text("Eliminar Ciudadano", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                info_prev,
                ft.Divider(height=8),
                ft.Row([
                    delete_files_chk,
                    ft.Text("(moverá archivos sin vínculos a .trash)", size=11, color=ft.Colors.BLUE_GREY_600),
                ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=10, tight=True),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.FilledButton(
                    "Eliminar",
                    icon=ft.Icons.DELETE_FOREVER,
                    bgcolor=ft.Colors.RED_700,
                    on_click=lambda e: (page.close(dlg), confirm(e)),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )
        page.open(dlg)

    delete_btn.on_click = on_delete

    # Reporte: asunto, fecha, oficio, resultado (positivo/negativo) y datos del ciudadano
    def open_report_dialog(e=None):
        # Diálogo que permite generar reporte aun sin ciudadano seleccionado
        today = datetime.now().strftime("%Y-%m-%d")
        asunto_tf = ft.TextField(label="Asunto*", value="Informe de búsqueda", expand=True)
        fecha_tf = ft.TextField(label="Fecha (YYYY-MM-DD)*", value=today, width=180)
        oficio_tf = ft.TextField(label="Oficio", width=200)
        # Si no hay seleccionado, sugerir NEGATIVO
        resultado_tf = ft.Dropdown(label="Resultado*", options=[ft.dropdown.Option("POSITIVO"), ft.dropdown.Option("NEGATIVO")], value=("POSITIVO" if selected else "NEGATIVO"), width=150)
        formato_dd = ft.Dropdown(label="Formato", options=[ft.dropdown.Option("PDF"), ft.dropdown.Option("TXT")], value="PDF", width=120)
        tipo_dd = ft.Dropdown(label="Tipo", options=[ft.dropdown.Option("BÚSQUEDA"), ft.dropdown.Option("OFICIO")], value="BÚSQUEDA", width=140)
        institucion_tf = ft.TextField(label="Institución (encabezado)", value="INSTITUCIÓN MILITAR", expand=True)
        watermark_chk = ft.Checkbox(label="Marca de agua (logo grande y tenue)", value=True)
        # Campos manuales para casos sin coincidencia
        dni_manual_tf = ft.TextField(label="DNI consultado", width=160)
        ap_manual_tf = ft.TextField(label="Apellidos consultados", expand=True)
        no_manual_tf = ft.TextField(label="Nombres consultados", expand=True)
        fn_manual_tf = ft.TextField(label="Fecha nacimiento (DD/MM/AAAA)", width=220)
        lm_manual_tf = ft.TextField(label="Libreta Militar", width=180)
        # Campos de OFICIO
        nro_oficio_tf = ft.TextField(label="N° Oficio* (ej. 495/ ORMD-55-A/SEC REG MIL/S-6. f.1)", expand=True)
        destinatario_tf = ft.TextField(label="Destinatario*", expand=True)
        cargo_dest_tf = ft.TextField(label="Cargo del destinatario", expand=True)
        entidad_dest_tf = ft.TextField(label="Entidad / Unidad", expand=True)
        ciudad_tf = ft.TextField(label="Ciudad*", width=160)
        referencia_tf = ft.TextField(label="Referencia (RENIEC)", expand=True)
        firmante_nombre_tf = ft.TextField(label="Nombre del firmante", expand=True)
        firmante_cargo_tf = ft.TextField(label="Cargo del firmante", expand=True)
        err = ft.Text(value="", color="red")
        # Autocompletar ciudades del Perú, por defecto Arequipa
        ciudades_peru = [
            "Arequipa", "Lima", "Cusco", "Trujillo", "Piura", "Tacna", "Ica", "Puno", "Huancayo", "Chiclayo", "Cajamarca", "Ayacucho", "Tarapoto", "Tumbes", "Moquegua", "Chimbote", "Huánuco", "Sullana", "Juliaca", "Huaraz", "Iquitos", "Abancay", "Puerto Maldonado", "Ucayali", "Madre de Dios", "Pasco", "San Martín", "Loreto", "Apurímac", "Amazonas", "Callao"
        ]
        ciudad_tf.value = "Arequipa"
        def autocompletar_ciudad(e):
            val = (ciudad_tf.value or "").strip().capitalize()
            if val:
                pass  # FIN autocompletar_ciudad

        def generate(is_preview: bool = False):
            try:
                import textwrap
                asunto = (asunto_tf.value or "").strip()
                fecha = (fecha_tf.value or "").strip()
                oficio = (oficio_tf.value or "").strip()
                resultado = (resultado_tf.value or "").strip()
                formato = (formato_dd.value or "PDF").strip().upper()
                tipo = (tipo_dd.value or "BÚSQUEDA").strip().upper()
                # Si destinatario/entidad contiene RENIEC, el asunto es fijo
                try:
                    _entidad_upper = (entidad_dest_tf.value or "").upper()
                except Exception:
                    _entidad_upper = ""
                if "RENIEC" in _entidad_upper:
                    asunto = "Remite información solicitada del ciudadano"
                # Resetear mensajes de error por campo
                for fld in [asunto_tf, fecha_tf, resultado_tf, nro_oficio_tf, destinatario_tf, ciudad_tf, referencia_tf]:
                    try:
                        fld.error_text = None
                    except Exception:
                        pass
                missing = []
                if not asunto:
                    missing.append("Asunto"); asunto_tf.error_text = "Requerido"
                if not fecha:
                    missing.append("Fecha"); fecha_tf.error_text = "Requerido"
                # Validar formato fecha nacimiento solo si NO hay ciudadano seleccionado
                if not selected and fecha_nac_field.value:
                    import re
                    val = fecha_nac_field.value.strip()
                    # Permitir solo números y formatear
                    if re.match(r"^\d{8}$", val):
                        val_fmt = f"{val[:2]}/{val[2:4]}/{val[4:]}"
                        fecha_nac_field.value = val_fmt
                        fecha_nac_field.error_text = None
                        fecha_nac_field.update()
                    elif not re.match(r"^\d{2}/\d{2}/\d{4}$", val):
                        err.value = "La fecha de nacimiento debe tener formato DD/MM/AAAA o solo números. Ejemplo: 11031998 → 11/03/1998"
                        fecha_nac_field.error_text = "Formato inválido"
                        fecha_nac_field.update()
                        err.update()
                        return
                if not resultado:
                    missing.append("Resultado"); resultado_tf.error_text = "Requerido"
                if tipo == "OFICIO":
                    if not (nro_oficio_tf.value or "").strip():
                        missing.append("N° Oficio"); nro_oficio_tf.error_text = "Requerido"
                    if not (destinatario_tf.value or "").strip():
                        missing.append("Destinatario"); destinatario_tf.error_text = "Requerido"
                    if not (ciudad_tf.value or "").strip():
                        missing.append("Ciudad"); ciudad_tf.error_text = "Requerido"
                    if "RENIEC" in _entidad_upper and not (referencia_tf.value or "").strip():
                        missing.append("Referencia (RENIEC)"); referencia_tf.error_text = "Requerido si es RENIEC"
                if missing:
                    err.value = "No se puede generar el PDF. Faltan campos obligatorios: " + ", ".join(missing) + ". Marque los campos con * y complete todos los datos requeridos."
                    for campo in missing:
                        if campo == "Asunto": asunto_tf.error_text = "Requerido"
                        if campo == "Fecha": fecha_tf.error_text = "Requerido"
                        if campo == "Resultado": resultado_tf.error_text = "Requerido"
                        if campo == "N° Oficio": nro_oficio_tf.error_text = "Requerido"
                        if campo == "Destinatario": destinatario_tf.error_text = "Requerido"
                        if campo == "Ciudad": ciudad_tf.error_text = "Requerido"
                        if campo == "Referencia (RENIEC)": referencia_tf.error_text = "Requerido si es RENIEC"
                    for fld in [asunto_tf, fecha_tf, resultado_tf, nro_oficio_tf, destinatario_tf, ciudad_tf, referencia_tf]:
                        try:
                            fld.update()
                        except Exception:
                            pass
                    err.update();
                    return
                lines = []
                lines.append(f"ASUNTO: {asunto}")
                lines.append(f"FECHA: {fecha}")
                if oficio:
                    lines.append(f"OFICIO: {oficio}")
                lines.append(f"RESULTADO: {resultado}")
                lines.append("")
                # Contexto de búsqueda
                lines.append("CONTEXTO DE BÚSQUEDA")
                lines.append(f"- Consulta: '{last_search_query}'")
                lines.append(f"- Coincidencias: {last_search_count}")
                lines.append("")
                if selected and resultado == "POSITIVO":
                    lines.append("DATOS DEL CIUDADANO")
                    lines.append(f"- ID: {selected.id_ciudadano}")
                    lines.append(f"- DNI: {selected.dni or '-'}")
                    lines.append(f"- LM: {selected.lm or '-'}")
                    lines.append(f"- NOMBRE: {(selected.apellidos or '').upper()}, {(selected.nombres or '').upper()}")
                    if selected.presto_servicio is not None:
                        lines.append(f"- PRESTÓ SERVICIO: {'SI' if selected.presto_servicio else 'NO'}")
                    try:
                        doc_list = docs if docs and selected else _fetch_documents(selected.id_ciudadano)
                    except Exception:
                        doc_list = []
                    lines.append("")
                    lines.append(f"DOCUMENTOS ({len(doc_list)}):")
                    for d in (doc_list or [])[:50]:
                        lines.append(f"  • #{d.id_documento} - {d.nombre_archivo or ''}")
                    try:
                        session_r = SessionLocal()
                        serv = session_r.execute(select(models.DatosServicioMilitar).where(models.DatosServicioMilitar.id_ciudadano == selected.id_ciudadano)).scalar_one_or_none()
                    finally:
                        try: session_r.close()
                        except Exception: pass
                    if serv:
                        lines.append("")
                        lines.append("SERVICIO MILITAR:")
                        lines.append(f"  Clase: {serv.clase or '-'}  •  Libro: {serv.libro or '-'}  •  Folio: {serv.folio or '-'}")
                        lines.append(f"  Ref. Origen: {serv.referencia_documento_origen or '-'}")
                        if serv.fecha_alta or serv.fecha_baja:
                            fa = serv.fecha_alta.strftime('%Y-%m-%d') if serv.fecha_alta else '-'
                            fb = serv.fecha_baja.strftime('%Y-%m-%d') if serv.fecha_baja else '-'
                            lines.append(f"  Fechas: Alta {fa}  •  Baja {fb}")
                else:
                    lines.append("RESULTADO SIN COINCIDENCIAS / CARGA MANUAL")
                    dni_m = (dni_manual_tf.value or '').upper()
                    ap_m = (ap_manual_tf.value or '').upper()
                    no_m = (no_manual_tf.value or '').upper()
                    if dni_m:
                        lines.append(f"- DNI consultado: {dni_m}")
                    if ap_m or no_m:
                        lines.append(f"- Nombre consultado: {ap_m} {no_m}".strip())
                    if not dni_m and not ap_m and not no_m:
                        lines.append("- (Sin datos manuales proporcionados)")

                out_dir = os.path.join("storage", "data", "reports")
                os.makedirs(out_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                if tipo == "OFICIO" and formato == "PDF":
                    usuario_actual = (user_data or {}).get("username") or (user_data or {}).get("nombre_usuario") or "(usuario)"
                    rol_actual = (user_data or {}).get("rol") or (user_data or {}).get("rol_nombre") or "(rol)"
                    institucion_nombre = (institucion_tf.value or "INSTITUCIÓN MILITAR").upper()
                    logo_path = Config.LOGO_PATH
                    banner_path = Config.HEADER_BANNER_PATH
                    motto_text = getattr(Config, "ANNUAL_MOTTO", None) or ""
                    # Construir línea ciudadano
                    if selected and resultado.upper() == "POSITIVO":
                        fn_raw = getattr(selected, 'fecha_nacimiento', None)
                        try:
                            fn_fmt = fn_raw.strftime('%d/%m/%Y') if fn_raw else '-'
                        except Exception:
                            fn_fmt = '-'
                        ciudadano_line = build_ciudadano_line(
                            (selected.apellidos or '').upper(),
                            (selected.nombres or '').upper(),
                            fn_fmt,
                            (selected.lm or '-'),
                            resultado.upper(),
                        )
                    else:
                        ciudadano_line = build_ciudadano_line(
                            (ap_manual_tf.value or '').upper(),
                            (no_manual_tf.value or '').upper(),
                            (fn_manual_tf.value or '-').upper(),
                            (lm_manual_tf.value or '-').upper(),
                            resultado.upper(),
                        )
                    firm_nom = (firmante_nombre_tf.value or usuario_actual)
                    firm_car = (firmante_cargo_tf.value or rol_actual)
                    num_of = (nro_oficio_tf.value or oficio or "").strip()
                    dest = (destinatario_tf.value or '').strip()
                    cargo_d = (cargo_dest_tf.value or '').strip()
                    ent = (entidad_dest_tf.value or '').strip()
                    referencia_val = (referencia_tf.value or '').strip()
                    ciudad_val = (ciudad_tf.value or '').strip()
                    out_path = generate_oficio_pdf_vs2(
                        out_dir=out_dir,
                        ciudad=ciudad_val,
                        fecha=fecha,
                        asunto=asunto,
                        referencia=referencia_val,
                        destinatario=dest,
                        cargo_dest=cargo_d,
                        entidad_dest=ent,
                        numero_oficio=num_of,
                        resultado=resultado,
                        institucion_nombre=institucion_nombre,
                        firmante_nombre=firm_nom,
                        firmante_cargo=firm_car,
                        usuario_actual=usuario_actual,
                        rol_actual=rol_actual,
                        ciudadano_line=ciudadano_line,
                    )
                elif formato == "PDF":
                    usuario_actual = (user_data or {}).get("username") or (user_data or {}).get("nombre_usuario") or "(usuario)"
                    rol_actual = (user_data or {}).get("rol") or (user_data or {}).get("rol_nombre") or "(rol)"
                    out_path = generate_busqueda_pdf(
                        out_dir=out_dir,
                        lines=lines,
                        usuario_actual=usuario_actual,
                        rol_actual=rol_actual,
                        institucion="INSTITUCIÓN MILITAR",
                    )
                else:
                    out_path = os.path.join(out_dir, f"reporte_{ts}_busqueda.txt")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines))
                page.snack_bar = ft.SnackBar(content=ft.Text(f"Reporte generado: {out_path}"), open=True)
                # Mostrar visor PDF si es PDF
                if formato == "PDF" and out_path and os.path.exists(out_path):
                    try:
                        import platform
                        if platform.system() == "Windows":
                            os.startfile(out_path)
                        elif platform.system() == "Darwin":
                            import subprocess; subprocess.run(["open", out_path])
                        else:
                            import subprocess; subprocess.run(["xdg-open", out_path])
                    except Exception as ex:
                        err.value = f"No se pudo abrir la vista previa: {ex}"; err.update()
                try:
                    log_dir = os.path.join("storage", "data", "logs")
                    os.makedirs(log_dir, exist_ok=True)
                    log_path = os.path.join(log_dir, "reportes.jsonl")
                    entry = {
                        "ts": datetime.now().isoformat(timespec="seconds"),
                        "usuario": usuario_actual,
                        "tipo": tipo,
                        "formato": formato,
                        "ruta": out_path,
                        "asunto": asunto,
                        "resultado": resultado,
                    }
                    with open(log_path, "a", encoding="utf-8") as lf:
                        lf.write(json.dumps(entry, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                page.update()
            except Exception as ex:
                err.value = f"Error al generar reporte: {ex}"; err.update()
                log_dir = os.path.join("storage", "data")
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, "reportes.jsonl")
                usuario_actual = (user_data or {}).get("username") or (user_data or {}).get("nombre_usuario") or "(usuario)"
                entry = {
                    "ts": datetime.now().isoformat(timespec="seconds"),
                    "usuario": usuario_actual,
                    "tipo": tipo,
                    "formato": formato,
                    "ruta": out_path,
                    "asunto": asunto,
                    "resultado": resultado,
                }
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass
            page.update()

        # Diseño más limpio con ResponsiveRow y secciones
        header_grid = ft.ResponsiveRow([
            ft.Container(asunto_tf, col={"sm": 12, "md": 12}),
            ft.Container(fecha_tf, col={"sm": 6, "md": 3}),
            ft.Container(resultado_tf, col={"sm": 6, "md": 3}),
            ft.Container(formato_dd, col={"sm": 6, "md": 2}),
            ft.Container(tipo_dd, col={"sm": 6, "md": 2}),
        ], columns=12, spacing=10, run_spacing=8)

        oficio_simple_row = ft.ResponsiveRow([
            ft.Container(oficio_tf, col={"sm": 12, "md": 6}),
        ], columns=12, spacing=10, run_spacing=8)

        org_grid = ft.ResponsiveRow([
            ft.Container(institucion_tf, col={"sm": 12, "md": 12}),
            ft.Container(watermark_chk, col={"sm": 12, "md": 12}),
        ], columns=12, spacing=6, run_spacing=6)

        sufijo_oficio_chk = ft.Checkbox(label="Agregar sufijo al número de oficio", value=False)
        oficio_section = ft.Column([
            ft.Text("Campos para OFICIO", size=12, color=ft.Colors.BLUE_GREY_600),
            ft.ResponsiveRow([
                ft.Container(nro_oficio_tf, col={"sm": 12, "md": 12}),
                ft.Container(sufijo_oficio_chk, col={"sm": 12, "md": 12}),
                ft.Container(destinatario_tf, col={"sm": 12, "md": 12}),
                ft.Container(cargo_dest_tf, col={"sm": 12, "md": 12}),
                ft.Container(entidad_dest_tf, col={"sm": 12, "md": 12}),
                ft.Container(ciudad_tf, col={"sm": 12, "md": 12}),
                ft.Container(referencia_tf, col={"sm": 12, "md": 12}),
                ft.Container(firmante_nombre_tf, col={"sm": 12, "md": 12}),
                ft.Container(firmante_cargo_tf, col={"sm": 12, "md": 12}),
            ], columns=12, spacing=6, run_spacing=6),
        ])

        manual_section = ft.Column([
            ft.Text("Datos manuales (si no hubo coincidencias)", size=12, color=ft.Colors.BLUE_GREY_600),
            ft.ResponsiveRow([
                ft.Container(dni_manual_tf, col={"sm": 12, "md": 4}),
                ft.Container(ap_manual_tf, col={"sm": 12, "md": 4}),
                ft.Container(no_manual_tf, col={"sm": 12, "md": 4}),
                ft.Container(fn_manual_tf, col={"sm": 12, "md": 6}),
                ft.Container(lm_manual_tf, col={"sm": 12, "md": 6}),
            ], columns=12, spacing=10, run_spacing=8),
        ], spacing=6, visible=not bool(selected))

        content_col = ft.Column([
            header_grid,
            oficio_simple_row,
            org_grid,
            ft.Divider(),
            oficio_section,
            ft.Divider(),
            manual_section,
            err,
        ], spacing=12, tight=False, scroll=ft.ScrollMode.AUTO)

        # Contenedor ampliado para el diálogo (más ancho/alto)
        content_container = ft.Container(
            content_col,
            width=920,
            height=600,
            padding=10,
        )

        def _update_visibility(initial: bool = False):
            is_oficio = (tipo_dd.value or "BÚSQUEDA").upper() == "OFICIO"
            oficio_section.visible = is_oficio
            oficio_simple_row.visible = not is_oficio
            # Evitar update antes de que el diálogo se haya agregado a la página
            if not initial:
                content_col.update()

        # Botón dinámico (PDF/TXT) y vista previa
        generate_btn = ft.FilledButton("Generar PDF", icon=ft.Icons.DESCRIPTION, on_click=lambda e: generate(False))
        preview_btn = ft.OutlinedButton("Vista previa PDF", icon=ft.Icons.PREVIEW, on_click=lambda e: generate(True))

        def _sync_generate_label(e=None):
            fmt = (formato_dd.value or "PDF").upper()
            if fmt == "PDF":
                generate_btn.text = "Generar PDF"
                preview_btn.visible = True
            elif fmt == "WORD":
                generate_btn.text = "Generar Word"
                preview_btn.visible = False
            else:
                generate_btn.text = "Generar TXT"
                preview_btn.visible = False
            try:
                generate_btn.update(); preview_btn.update()
            except Exception:
                pass

        formato_dd.on_change = _sync_generate_label
        tipo_dd.on_change = lambda e: (_update_visibility(False), _sync_generate_label())

        # Inicializar visibilidad sin llamar update aún (no está montado)
        _update_visibility(initial=True)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Generar reporte", weight=ft.FontWeight.BOLD),
            content=content_container,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                preview_btn,
                generate_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dlg)
        # Ahora sí aplicar visibilidad final con update
        _update_visibility(False)
        _sync_generate_label()

    report_btn.on_click = open_report_dialog

    # Document viewer helpers
    def _is_pdf(path: str) -> bool:
        return path.lower().endswith(".pdf")

    def _is_image(path: str) -> bool:
        return path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))

    def _render_pdf_to_base64(path: str, page_index: int, zoom: float = 1.0) -> str:
        if not fitz:
            raise RuntimeError("PyMuPDF no disponible; instale 'pymupdf'")
        doc = fitz.open(path)
        try:
            page_index = max(0, min(page_index, len(doc) - 1))
            page = doc.load_page(page_index)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            return base64.b64encode(png_bytes).decode("ascii")
        finally:
            doc.close()

    def _print_path(path: str):
        """Impresión directa en Windows.
        - Para imágenes (PNG/JPG/BMP/GIF): usar mspaint /pt para imprimir a la impresora predeterminada.
        - Para PDF: hacer copia temporal con nombre corto y usar startfile("print").
        """
        try:
            if os.name != "nt":
                raise RuntimeError("Impresión directa disponible solo en Windows")

            lower = path.lower()
            # Abrir el archivo en el visor predeterminado para que el usuario decida imprimir
            os.startfile(path)
            return True, "Archivo abierto. Use el visor para imprimir."
        except Exception as ex:
            return False, str(ex)

    def open_viewer(doc: models.Documento):
        path = doc.ruta_almacenamiento or ""
        if not path or not os.path.exists(path):
            page.dialog = ft.AlertDialog(title=ft.Text("Archivo no encontrado"), content=ft.Text(path or "(sin ruta)"), modal=True)
            page.dialog.open = True
            page.update()
            return

        zoom = 1.2
        page_idx = 0
        total_pages = 1
        is_pdf = _is_pdf(path)
        is_img = _is_image(path)

        image = ft.Image(expand=True, fit=ft.ImageFit.CONTAIN)
        scroll = ft.Container(content=image, height=520, bgcolor=ft.Colors.BLACK12)

        def refresh_image():
            try:
                if is_pdf:
                    nonlocal total_pages
                    with fitz.open(path) as d:
                        total_pages = len(d)
                    b64 = _render_pdf_to_base64(path, page_idx, zoom)
                    image.src_base64 = b64
                    image.src = None
                elif is_img:
                    image.src_base64 = None
                    image.src = path
                else:
                    raise RuntimeError("Formato no soportado")
                image.update()
            except Exception as ex:
                page.dialog = ft.AlertDialog(title=ft.Text("Error al renderizar"), content=ft.Text(str(ex)), modal=True)
                page.dialog.open = True
                page.update()

        def do_prev(_):
            nonlocal page_idx
            if not is_pdf:
                return
            page_idx = max(0, page_idx - 1)
            refresh_image()

        def do_next(_):
            nonlocal page_idx, total_pages
            if not is_pdf:
                return
            page_idx = min(total_pages - 1, page_idx + 1)
            refresh_image()

        def do_zoom_in(_):
            nonlocal zoom
            zoom = min(3.0, zoom + 0.2)
            refresh_image()

        def do_zoom_out(_):
            nonlocal zoom
            zoom = max(0.4, zoom - 0.2)
            refresh_image()

        def do_fit(_):
            nonlocal zoom
            zoom = 1.2
            refresh_image()

        def do_print(_):
            if path and os.path.exists(path):
                success, msg = _print_path(path)
                if success:
                    page.snack_bar = ft.SnackBar(content=ft.Text(msg), open=True)
                else:
                    page.dialog = ft.AlertDialog(title=ft.Text("Error al imprimir"), content=ft.Text(msg), modal=True)
                    page.dialog.open = True
                page.update()
            else:
                page.dialog = ft.AlertDialog(title=ft.Text("Archivo no encontrado"), content=ft.Text(path or "(sin ruta)"), modal=True)
                page.dialog.open = True
                page.update()

        toolbar = ft.Row([
            ft.Text(doc.nombre_archivo or os.path.basename(path), weight=ft.FontWeight.W_600),
            ft.Container(expand=True),
            ft.IconButton(icon=ft.Icons.ZOOM_OUT, tooltip="Alejar", on_click=lambda e: do_zoom_out(None)),
            ft.IconButton(icon=ft.Icons.ZOOM_IN, tooltip="Acercar", on_click=lambda e: do_zoom_in(None)),
            ft.IconButton(icon=ft.Icons.FIT_SCREEN, tooltip="Ajustar", on_click=lambda e: do_fit(None)),
            ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip="Anterior", on_click=lambda e: do_prev(None), disabled=not is_pdf),
            ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip="Siguiente", on_click=lambda e: do_next(None), disabled=not is_pdf),
            ft.IconButton(icon=ft.Icons.PRINT, tooltip="Imprimir documento", on_click=lambda e: do_print(None)),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=8)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Visor de Documento", weight=ft.FontWeight.BOLD),
            content=ft.Column([
                toolbar,
                scroll,
            ], spacing=8, tight=True),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.open(dlg)
        refresh_image()

    def print_document(doc: models.Documento):
        path = doc.ruta_almacenamiento or ""
        if not path or not os.path.exists(path):
            page.dialog = ft.AlertDialog(title=ft.Text("Archivo no encontrado"), content=ft.Text(path or "(sin ruta)"), modal=True)
            page.dialog.open = True
            page.update()
            return
        success, msg = _print_path(path)
        if success:
            page.snack_bar = ft.SnackBar(content=ft.Text(msg), open=True)
        else:
            page.dialog = ft.AlertDialog(title=ft.Text("Error al imprimir"), content=ft.Text(msg), modal=True)
            page.dialog.open = True
        page.update()


    def _delete_document_flow(doc: models.Documento):
        path = doc.ruta_almacenamiento or ""
        if not path or not os.path.exists(path):
            page.dialog = ft.AlertDialog(title=ft.Text("Archivo no encontrado"), content=ft.Text(path or "(sin ruta)"), modal=True)
            page.dialog.open = True
            page.update()
            return
        # Confirmación antes de eliminar
        def do_confirm_delete(_):
            try:
                # Eliminar archivo físico si existe
                if os.path.exists(path):
                    os.remove(path)
                # Eliminar de la base de datos si corresponde
                # Aquí deberías agregar la lógica para eliminar el registro del documento en la base de datos
                # Por ejemplo: database.crud.delete_document(doc.id_documento)
                # Eliminar de la lista local y refrescar la tabla
                if doc in docs:
                    docs.remove(doc)
                populate_docs()
                page.snack_bar = ft.SnackBar(content=ft.Text("Documento eliminado"), open=True)
            except Exception as ex:
                page.dialog = ft.AlertDialog(title=ft.Text("Error al eliminar"), content=ft.Text(str(ex)), modal=True)
                page.dialog.open = True
            finally:
                page.update()
        confirm_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar eliminación"),
            content=ft.Text(f"¿Está seguro que desea eliminar el documento '{doc.nombre_archivo}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(confirm_dlg)),
                ft.TextButton("Eliminar", on_click=do_confirm_delete),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(confirm_dlg)

    def populate_docs():
        docs_table.rows.clear()
        for d in docs:
            actions = ft.Row([
                ft.IconButton(icon=ft.Icons.VISIBILITY, tooltip="Ver", on_click=lambda e, d=d: open_viewer(d)),
                ft.IconButton(icon=ft.Icons.PRINT, tooltip="Imprimir", on_click=lambda e, d=d: print_document(d)),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip="Quitar / Eliminar", icon_color=ft.Colors.RED_700, on_click=lambda e, d=d: _delete_document_flow(d)),
            ], spacing=2)
            docs_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(d.id_documento))),
                        ft.DataCell(ft.Text(d.nombre_archivo or "")),
                        ft.DataCell(actions),
                    ],
                )
            )

    # Declarar docs_table antes de usarlo in populate_docs y en el layout
    docs_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Nombre")),
            ft.DataColumn(ft.Text("Acciones")),
        ],
        rows=[],
        expand=True,
    )

    # Wire search
    def do_search(e=None):
        nonlocal last_search_query, last_search_count
        q = (search_field.value or "").strip()
        last_search_query = q
        load_citizens()
        last_search_count = len(citizens)
        # Log de búsqueda para Operador/Consulta
        role_name = (user_data or {}).get("rol") or (user_data or {}).get("rol_nombre") or ""
        rn = _norm_role(role_name)
        if rn in ("operador", "consulta"):
            try:
                _log_busqueda(q, len(citizens))
            except Exception:
                pass

    refresh_btn.on_click = do_search
    search_field.on_submit = do_search

    # Initial load
    load_citizens()
    populate_detail()

    # Layout
    left_panel = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Container(height=4, bgcolor=SECONDARY_COLOR, border_radius=8),
                ft.Row([
                    ft.Icon(ft.Icons.PEOPLE_ALT, color=ACCENT_COLOR),
                    ft.Text("Ciudadanos", size=18, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                    ft.Container(expand=True),
                    report_btn,
                ], spacing=14, alignment=ft.MainAxisAlignment.START),
                ft.Row([search_field, refresh_btn], spacing=12),
                ft.Divider(height=1, thickness=1, color=NEUTRAL_COLOR),
                ft.Container(citizens_list, expand=True),
            ], spacing=14),
            bgcolor=CARD_BG,
            border_radius=12,
            padding=16,
            expand=True,
            border=ft.border.all(1, CARD_BORDER_COLOR),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color=ft.Colors.BLACK12, offset=ft.Offset(0,2)),
        ),
    ], expand=2, scroll=ft.ScrollMode.AUTO)

    right_panel = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Container(height=4, bgcolor=ACCENT_COLOR, border_radius=8),
                detail_title,
                ft.Row([
                    ft.Column([
                        ft.Row([dni_field, lm_field], spacing=12),
                        ft.Row([fecha_nac_field, presto_dd], spacing=12),
                    ], spacing=10, expand=True),
                ], spacing=12),
                ft.Row([apellidos_field], spacing=12),
                ft.Row([nombres_field], spacing=12),
                ft.Text("Servicio Militar", size=14, weight=ft.FontWeight.W_600, color=PRIMARY_COLOR),
                ft.Row([clase_field, libro_field, folio_field], spacing=12),
                ft.Row([ref_doc_field], spacing=12),
                ft.Row([fecha_alta_field, fecha_baja_field], spacing=12),
                ft.Divider(),
                ft.Text("Referencias (unidad / grado / motivo):", size=12, color=ft.Colors.BLUE_GREY_600),
                ft.Row([unidad_alta_field, unidad_baja_field], spacing=12),
                ft.Row([grado_field, motivo_baja_field], spacing=12),
                ft.Divider(),
                ft.Row([save_detail_btn, add_files_btn, delete_btn], spacing=14),
            ], spacing=16),
            bgcolor=CARD_BG,
            border_radius=12,
            padding=18,
            border=ft.border.all(1, CARD_BORDER_COLOR),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color=ft.Colors.BLACK12, offset=ft.Offset(0,2)),
        ),
        ft.Container(height=18),
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.DESCRIPTION, color=ACCENT_COLOR),
                    ft.Text("Documentos asociados", size=16, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                    ft.Container(expand=True),
                ], spacing=14),
                ft.Divider(height=1, thickness=1, color=NEUTRAL_COLOR),
                ft.Column([
                    ft.Text("Archivos adjuntos:", weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.BLUE_GREY_700),
                    *(ft.Text(f"• {d.nombre_archivo}", size=13, color=ft.Colors.BLUE_GREY_600) for d in docs)
                ], spacing=4),
                ft.Container(docs_table, expand=True),
            ], spacing=14),
            bgcolor=CARD_BG,
            border_radius=12,
            padding=18,
            expand=True,
            border=ft.border.all(1, CARD_BORDER_COLOR),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=6, color=ft.Colors.BLACK12, offset=ft.Offset(0,2)),
        ),
    ], expand=3, scroll=ft.ScrollMode.AUTO)

    layout = ft.Row([left_panel, ft.VerticalDivider(), right_panel], expand=True)

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.FOLDER_OPEN, color=ACCENT_COLOR),
                ft.Text("Módulo: Gestión de Datos", size=24, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ], spacing=10),
            ft.Container(height=12),
            layout,
        ], expand=True, spacing=8),
        bgcolor=BG_COLOR,
        padding=12,
        expand=True,
    )

