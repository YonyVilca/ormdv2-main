# -*- coding: utf-8 -*-
import os
import sys
from typing import Any, Callable, Dict, List, Optional

import flet as ft

from utils.extractors import extract_pdf
from utils.nav_guard import register_guard, unregister_guard
from database.connection import get_db
from database.crud import create_full_digital_record
from database.models import Documento, Usuario
from sqlalchemy import select


class Colors:
    """Paleta verde moderna reutilizada en el módulo."""

    PRIMARY = "#16A34A"
    PRIMARY_LIGHT = "#22C55E"
    PRIMARY_DARK = "#15803D"
    SECONDARY = "#059669"
    SECONDARY_LIGHT = "#10B981"
    WARNING = "#F59E0B"
    DANGER = "#EF4444"
    SUCCESS = "#047857"
    SURFACE = "#F0FDF4"
    SURFACE_VARIANT = "#DCFCE7"
    ON_SURFACE = "#14532D"
    ON_SURFACE_VARIANT = "#166534"
    BORDER = "#BBF7D0"
    WHITE = "#FFFFFF"
    BLACK = "#000000"


def create_card(content: ft.Control, title: Optional[str] = None, padding: int = 20) -> ft.Container:
    """Tarjeta reutilizable con borde suave y sombra ligera."""

    children = [content] if not title else [
        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ft.Divider(height=1, color=Colors.BORDER),
        content,
    ]

    return ft.Container(
        content=ft.Column(children, spacing=12),
        padding=padding,
        bgcolor=Colors.WHITE,
        border_radius=12,
        border=ft.border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color="#10000000", offset=ft.Offset(0, 2)),
    )


def create_status_chip(status: str) -> ft.Container:
    """Chip compacto con esquema de colores compartido."""

    lookup = {
        "Pendiente": {"color": "#7C3AED", "bg": "#F3F4F6", "icon": ft.Icons.SCHEDULE, "text": "Pendiente"},
        "Procesando": {"color": "#059669", "bg": "#ECFDF5", "icon": ft.Icons.AUTORENEW, "text": "OCR"},
        "Procesado": {"color": "#10B981", "bg": "#ECFDF5", "icon": ft.Icons.CHECK_CIRCLE_OUTLINE, "text": "Procesado"},
        "Validado": {"color": "#059669", "bg": "#DCFCE7", "icon": ft.Icons.VERIFIED, "text": "Validado"},
        "Editado": {"color": "#8B5CF6", "bg": "#F5F3FF", "icon": ft.Icons.EDIT, "text": "Editado"},
        "Error": {"color": "#DC2626", "bg": "#FEF2F2", "icon": ft.Icons.INFO_OUTLINE, "text": "Error"},
        "Guardado": {"color": "#16A34A", "bg": "#DCFCE7", "icon": ft.Icons.CHECK, "text": "Guardado"},
    }

    config = lookup.get(status, {"color": Colors.PRIMARY, "bg": Colors.SURFACE_VARIANT, "icon": ft.Icons.INFO, "text": status})

    return ft.Container(
        content=ft.Row([
            ft.Icon(config["icon"], size=12, color=config["color"]),
            ft.Text(config["text"], size=10, color=config["color"], weight=ft.FontWeight.W_600),
        ], spacing=3, tight=True),
        bgcolor=config["bg"],
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=12,
        width=100,
        border=ft.border.all(1, config["color"] + "30"),
    )


def create_button(
    text: str,
    icon: str,
    style: str = "filled",
    on_click: Optional[Callable[[ft.ControlEvent], None]] = None,
    color: Optional[str] = None,
) -> ft.Control:
    """Crea botones coherentes con el resto de vistas."""

    if style == "filled":
        return ft.ElevatedButton(
            text=text,
            icon=icon,
            on_click=on_click,
            style=ft.ButtonStyle(
                bgcolor=color or Colors.PRIMARY,
                color=Colors.WHITE,
                elevation=2,
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
            ),
        )

    if style == "outlined":
        return ft.OutlinedButton(
            text=text,
            icon=icon,
            on_click=on_click,
            style=ft.ButtonStyle(
                color=color or Colors.PRIMARY,
                side=ft.BorderSide(1, color or Colors.PRIMARY),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
            ),
        )

    return ft.TextButton(
        text=text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=color or Colors.PRIMARY,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
        ),
    )


def create_digitalizacion_pdf_view(
    page: ft.Page,
    user_data: Optional[Dict[str, Any]] = None,
    has_docs_ref: Optional[ft.Ref[bool]] = None,
) -> ft.Container:
    """Construye la UX de digitalización para archivos PDF."""

    files: List[Dict[str, Any]] = []
    selected_index: Optional[int] = None
    last_result: Optional[Dict[str, Any]] = None

    preview_ref: ft.Ref[ft.Container] = ft.Ref[ft.Container]()
    pdf_view_cls = None
    for _cls_name in ["PDFView", "PdfView", "PDFViewer", "PdfViewer"]:
        _cand = getattr(ft, _cls_name, None)
        if _cand:
            pdf_view_cls = _cand
            break

    def has_pending_work() -> bool:
        return bool(files) or any(f.get("status") == "Procesando" for f in files)

    register_guard("digitalizacion_pdf", has_pending_work)

    log = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def log_add(message: str, _level: str = "info") -> None:
        """Log deshabilitado a efectos de rendimiento (API compatible)."""
        _ = message, _level

    def update_docs_ref() -> None:
        if has_docs_ref is not None:
            has_docs_ref.current = len(files) > 0

    def safe_control_update(ctrl: Optional[ft.Control]) -> None:
        """Actualiza un control solo si ya está montado en la página."""
        try:
            if ctrl is not None and getattr(ctrl, "page", None) is not None:
                ctrl.update()
        except Exception:
            pass

    def safe_open_dialog(dialog: ft.AlertDialog) -> None:
        """Abre un AlertDialog de forma segura usando page.open (paridad con vista JPG)."""
        try:
            page.open(dialog)
        except Exception:
            try:
                # Fallback al patrón dialog/open por compatibilidad
                page.dialog = dialog
                dialog.open = True
                page.update()
            except Exception:
                pass

    def safe_close_dialog(dialog: ft.AlertDialog) -> None:
        """Cierra un AlertDialog de forma segura (page.close)."""
        try:
            page.close(dialog)
        except Exception:
            try:
                dialog.open = False
                page.update()
            except Exception:
                pass

    def show_modal(title: str, message: str, icon: Optional[str] = None) -> None:
        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(icon or ft.Icons.INFO, color=Colors.PRIMARY),
                ft.Text(title, weight=ft.FontWeight.BOLD),
            ], spacing=8) if icon else ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(message),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: safe_close_dialog(dialog))],
    )
        safe_open_dialog(dialog)

    def open_path(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", path], check=False)
            else:
                import subprocess

                subprocess.run(["xdg-open", path], check=False)
        except Exception as exc:
            log_add(f"❌ No se pudo abrir el archivo: {exc}")

    def reveal_in_folder(path: str) -> None:
        try:
            if sys.platform.startswith("win"):
                import subprocess

                subprocess.run(["explorer", "/select,", path], check=False)
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", "-R", path], check=False)
            else:
                open_path(os.path.dirname(path))
        except Exception as exc:
            log_add(f"❌ No se pudo mostrar en carpeta: {exc}")

    def copy_to_clipboard(value: str) -> None:
        try:
            page.set_clipboard(value)
        except Exception:
            log_add("ℹ️ Portapapeles no disponible")

    def open_pdf_viewer_for(file_item: Dict[str, Any], pos_idx: Optional[int] = None) -> None:
        path = file_item.get("path")
        if not path:
            show_modal("Ruta inválida", "El archivo seleccionado no tiene ruta.", ft.Icons.ERROR)
            return
        if not os.path.exists(path):
            show_modal("Archivo no encontrado", path, ft.Icons.ERROR)
            return

        # Forzamos renderizado por imágenes (evita WebView no soportado)
        viewer: ft.Control
        try:
                import base64
                import fitz  # type: ignore

                doc = fitz.open(path)
                total = doc.page_count
                state = {"page": 0, "zoom": 1.2}

                # Para mejorar la sensación de zoom: mantenemos un caché de render (pix)
                # y re-renderizamos sólo cuando el cambio de zoom es suficientemente grande
                # o para página distinta.
                _cache = {"page": -1, "zoom": 0.0, "b64": None, "w": 0, "h": 0}

                img_ref: ft.Ref[ft.Image] = ft.Ref[ft.Image]()
                page_label = ft.Text("", size=11, color=Colors.ON_SURFACE_VARIANT)

                def render_current() -> None:
                    try:
                        p = max(0, min(state["page"], total - 1))
                        page = doc.load_page(p)
                        # decidir si re-renderizar (calidad) o sólo ajustar tamaño
                        zoom = state["zoom"]
                        need_rerender = (
                            _cache["page"] != p or _cache["b64"] is None or abs(zoom - float(_cache["zoom"])) > 0.15
                        )
                        if need_rerender:
                            mat = fitz.Matrix(zoom, zoom)
                            pix = page.get_pixmap(matrix=mat, alpha=False)
                            data = pix.tobytes("png")
                            b64 = base64.b64encode(data).decode("ascii")
                            _cache.update({"page": p, "zoom": zoom, "b64": b64, "w": pix.width, "h": pix.height})
                        # Aplica la imagen desde caché
                        if img_ref.current is not None and _cache["b64"] is not None:
                            img_ref.current.src_base64 = _cache["b64"]  # type: ignore
                            # Ajusta tamaño visual de acuerdo al último render de calidad
                            img_ref.current.width = _cache["w"]
                            img_ref.current.height = _cache["h"]
                        page_label.value = f"Página {p+1} / {total}  •  Zoom {state['zoom']:.1f}x"
                        safe_control_update(img_ref.current)
                        safe_control_update(page_label)
                    except Exception:
                        pass

                def go_prev(_: ft.ControlEvent) -> None:
                    if state["page"] > 0:
                        state["page"] -= 1
                        render_current()

                def go_next(_: ft.ControlEvent) -> None:
                    if state["page"] < total - 1:
                        state["page"] += 1
                        render_current()

                def on_zoom_change(e: ft.ControlEvent) -> None:
                    try:
                        val = float(e.control.value)
                        state["zoom"] = max(0.6, min(val, 3.0))
                        render_current()
                    except Exception:
                        pass

                slider_ref: ft.Ref[ft.Slider] = ft.Ref[ft.Slider]()

                def zoom_delta(delta: float) -> None:
                    new_val = max(0.6, min(state["zoom"] + delta, 3.0))
                    state["zoom"] = new_val
                    if slider_ref.current is not None:
                        slider_ref.current.value = new_val
                    render_current()

                btn_prev = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=go_prev, tooltip="Anterior")
                btn_next = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=go_next, tooltip="Siguiente")
                btn_zoom_out = ft.IconButton(icon=ft.Icons.REMOVE, tooltip="Zoom -", on_click=lambda e: zoom_delta(-0.1))
                btn_zoom_in = ft.IconButton(icon=ft.Icons.ADD, tooltip="Zoom +", on_click=lambda e: zoom_delta(0.1))
                slider = ft.Slider(
                    ref=slider_ref,
                    min=0.6,
                    max=3.0,
                    divisions=24,
                    value=state["zoom"],
                    on_change=on_zoom_change,
                    on_change_end=on_zoom_change,
                    width=220,
                )
                zoom_percent = ft.Text(f"{int(state['zoom']*100)}%", size=11, color=Colors.ON_SURFACE_VARIANT)

                def fit_width(_: ft.ControlEvent) -> None:
                    try:
                        p = doc.load_page(state["page"])
                        page_width_pts = p.rect.width  # puntos
                        # Determina el ancho disponible del viewer si es posible
                        target = 660
                        try:
                            if viewer_container_ref.current is not None and viewer_container_ref.current.width:
                                target = max(480, int(viewer_container_ref.current.width) - 40)
                        except Exception:
                            pass
                        # Aproximación: pix width ≈ page_width_pts * zoom
                        new_zoom = max(0.4, min(target / page_width_pts, 3.0))
                        state["zoom"] = new_zoom
                        if slider_ref.current is not None:
                            slider_ref.current.value = new_zoom
                        render_current()
                    except Exception:
                        pass

                def reset_zoom(_: ft.ControlEvent) -> None:
                    state["zoom"] = 1.2
                    if slider_ref.current is not None:
                        slider_ref.current.value = 1.2
                    render_current()

                # Actualizar porcentaje después de cada render
                _old_render_current = render_current
                def _wrapped_render():
                    _old_render_current()
                    zoom_percent.value = f"{int(state['zoom']*100)}%"
                    safe_control_update(zoom_percent)
                render_current = _wrapped_render  # type: ignore

                nav = ft.Row([
                    btn_prev,
                    page_label,
                    btn_next,
                    ft.Container(width=12),
                    btn_zoom_out,
                    slider,
                    btn_zoom_in,
                    zoom_percent,
                    ft.IconButton(icon=ft.Icons.FIT_SCREEN, tooltip="Ajustar ancho", on_click=fit_width),
                    ft.IconButton(icon=ft.Icons.RESTORE, tooltip="Reset zoom", on_click=reset_zoom),
                ], alignment=ft.MainAxisAlignment.START, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

                # Imagen y envoltorio con scroll en ambas direcciones.
                img = ft.Image(ref=img_ref, border_radius=4, gapless_playback=True)
                # Gestos simples: doble clic para acercar y Ctrl+doble clic para alejar
                def on_double_tap(_: ft.ControlEvent) -> None:
                    zoom_delta(0.2)

                img_gesture = ft.GestureDetector(
                    content=img,
                    on_double_tap=on_double_tap,
                )

                # Scroll horizontal + vertical combinados
                scroller = ft.Row([
                    ft.Column([img_gesture], scroll=ft.ScrollMode.ALWAYS, expand=True),
                ], scroll=ft.ScrollMode.ALWAYS, expand=True)
                viewer = ft.Container(
                    content=ft.Column([
                        nav,
                        ft.Container(content=scroller, expand=True, bgcolor=Colors.BLACK+"08", border_radius=8, padding=4),
                    ], expand=True, spacing=8),
                    width=720,
                    height=540,
                    bgcolor=Colors.SURFACE,
                    border_radius=12,
                    border=ft.border.all(1, Colors.BORDER),
                )

                # Render inicial
                render_current()

                def cleanup_doc() -> None:
                    try:
                        doc.close()
                    except Exception:
                        pass

                # Adjunta cleanup del doc cuando se cierre root (paridad con cleanup general)
                try:
                    old_cleanup = getattr(root, "cleanup", None)
                    def combined():
                        cleanup_doc()
                        if callable(old_cleanup):
                            old_cleanup()
                    root.cleanup = combined  # type: ignore
                except Exception:
                    pass

        except Exception as render_exc:
                # Fallback informativo final
                viewer = ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.PICTURE_AS_PDF, size=64, color=Colors.PRIMARY),
                        ft.Text("No se pudo mostrar el PDF", weight=ft.FontWeight.BOLD),
                        ft.Text("Instala PyMuPDF (fitz) o usa 'Abrir PDF'."),
                        ft.Text(str(render_exc)[:140], size=10, color=Colors.ON_SURFACE_VARIANT),
                    ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=720,
                    height=540,
                    bgcolor=Colors.SURFACE,
                    border_radius=12,
                    border=ft.border.all(1, Colors.BORDER),
                    alignment=ft.alignment.center,
                )

    # Panel de comparación y corrección (lado derecho del modal)
        current_data = (file_item.get("result") or {}).copy()
        ocr_data = (file_item.get("ocr_raw") or current_data).copy()

        field_labels = {
            "dni": "DNI (11 dígitos)",
            "lm": "LM",
            "or": "OR (DDD[L])",
            "clase": "Clase (4)",
            "libro": "Libro",
            "folio": "Folio",
            "apellidos": "Apellidos",
            "nombres": "Nombres",
            "fecha_nacimiento": "Fecha Nac. (DD/MM/AAAA)",
            "presto_servicio": "¿Prestó servicio? (SI/NO)",
            "gran_unidad": "Gran Unidad",
            "unidad_alta": "Unidad Alta",
            "unidad_baja": "Unidad Baja",
            "fecha_alta": "Fecha Alta",
            "fecha_baja": "Fecha Baja",
            "grado": "Grado",
            "motivo_baja": "Motivo de Baja",
        }

        inputs: Dict[str, ft.Ref[ft.TextField]] = {k: ft.Ref[ft.TextField]() for k in field_labels.keys()}

        def row_for_field(key: str) -> ft.Control:
            ocr_val = str(ocr_data.get(key) or "")
            cur_val = str(current_data.get(key) or "")
            differs_initial = (ocr_val or "") != (cur_val or "") and (ocr_val != "")

            def compute_diff(v: str) -> bool:
                return (ocr_val or "") != (v or "") and (ocr_val != "")

            # Campo editable sin label (colocamos label arriba común)
            tf = ft.TextField(
                ref=inputs[key],
                value=cur_val,
                dense=True,
                expand=1,
                border_color=("#F59E0B" if differs_initial else Colors.BORDER),
                focused_border_color=("#D97706" if differs_initial else Colors.PRIMARY),
                on_change=lambda e: update_field_style(key),
                tooltip=cur_val or "",
            )

            def use_ocr(_: ft.ControlEvent) -> None:
                if inputs[key].current is not None:
                    inputs[key].current.value = ocr_val
                    update_field_style(key)
                    safe_control_update(inputs[key].current)

            def swap_values(_: ft.ControlEvent) -> None:
                nonlocal ocr_val
                if inputs[key].current is not None:
                    new_val = inputs[key].current.value
                    inputs[key].current.value = ocr_val
                    ocr_val = new_val
                    update_field_style(key)
                    safe_control_update(inputs[key].current)

            def update_field_style(field_key: str) -> None:
                ref = inputs[field_key].current
                if ref is None:
                    return
                diff_now = compute_diff(ref.value or "")
                ref.border_color = "#F59E0B" if diff_now else Colors.BORDER
                ref.focused_border_color = "#D97706" if diff_now else Colors.PRIMARY
                # Mantener tooltip con el valor completo para visualización rápida
                ref.tooltip = ref.value or ""
                # Actualiza ícono de diferencia
                if diff_icon.current is not None:
                    diff_icon.current.visible = diff_now
                safe_control_update(ref)
                safe_control_update(diff_icon.current)

            diff_icon: ft.Ref[ft.Icon] = ft.Ref[ft.Icon]()
            ocr_display = ft.Text(
                ocr_val or "(vacío)",
                size=12,
                color=Colors.ON_SURFACE,
                selectable=True,
                max_lines=3,
                overflow=ft.TextOverflow.ELLIPSIS,
                tooltip=ocr_val or "",
            )
            ocr_chip = ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Row([
                            ft.Text("OCR", size=10, color=Colors.ON_SURFACE_VARIANT),
                            ft.Icon(ref=diff_icon, name=ft.Icons.WARNING_AMBER, size=14, color="#F59E0B", visible=differs_initial),
                        ], spacing=4),
                        ocr_display,
                    ], spacing=2, expand=True),
                    ft.Column([
                        ft.IconButton(icon=ft.Icons.CONTENT_PASTE_GO, tooltip="Usar OCR", on_click=use_ocr),
                        ft.IconButton(icon=ft.Icons.SWAP_HORIZ, tooltip="Intercambiar", on_click=swap_values),
                    ], spacing=4),
                ], alignment=ft.MainAxisAlignment.START, spacing=8),
                bgcolor=Colors.SURFACE_VARIANT,
                padding=8,
                border=ft.border.all(1, Colors.BORDER),
                border_radius=8,
                width=320,
            )

            return ft.Column([
                ft.Text(field_labels[key], size=12, weight=ft.FontWeight.W_600),
                ft.Row([
                    ocr_chip,
                    tf,
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=6)

        # Column sólo con filas de campos (sin acciones masivas)
        fields_column = ft.Column([
            ft.Text("Campos extraídos (comparación OCR)", size=13, weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
            ft.Divider(height=1, color=Colors.BORDER),
        ] + [row_for_field(k) for k in field_labels.keys()], spacing=8, scroll=ft.ScrollMode.AUTO)

        def apply_and_close(_: Optional[ft.ControlEvent] = None) -> None:
            updated: Dict[str, Any] = {}
            for k in field_labels.keys():
                ref = inputs[k].current
                updated[k] = ref.value if ref is not None else current_data.get(k)
            file_item["result"] = updated
            file_item["status"] = "Editado"
            # Sincroniza con formulario principal si corresponde
            try:
                if selected_index is not None and files[selected_index] is file_item:
                    fill_form(updated)
                refresh_table()
                update_ocr_buttons()
            except Exception:
                pass
            safe_close_dialog(dialog)

        # Barra superior con acciones
        is_max = {"value": False}
        is_wide_form = {"value": True}

        # Refs para ajustar tamaños dinámicamente
        form_container_ref: ft.Ref[ft.Container] = ft.Ref[ft.Container]()
        viewer_container_ref: ft.Ref[ft.Container] = ft.Ref[ft.Container]()

        def toggle_size(_: Optional[ft.ControlEvent] = None) -> None:
            is_max["value"] = not is_max["value"]
            try:
                modal_content.width = 1680 if is_max["value"] else 1280
                modal_content.height = 860 if is_max["value"] else 700
                page.update()
            except Exception:
                pass

        def toggle_form_width(_: Optional[ft.ControlEvent] = None) -> None:
            """Alterna prioridad de espacio para el panel de datos."""
            is_wide_form["value"] = not is_wide_form["value"]
            try:
                # Ajusta anchos relativos
                if form_container_ref.current is not None:
                    form_container_ref.current.width = 820 if is_wide_form["value"] else 600
                if viewer_container_ref.current is not None:
                    viewer_container_ref.current.width = 740 if is_wide_form["value"] else 900
                page.update()
            except Exception:
                pass

        title_row = ft.Row([
            ft.Icon(ft.Icons.PICTURE_AS_PDF, color=Colors.PRIMARY),
            ft.Text(file_item.get("name", os.path.basename(path)), weight=ft.FontWeight.BOLD, expand=True),
        ] + ([ft.Text(f"{(pos_idx or 0) + 1}/{len(files)}", size=11, color=Colors.ON_SURFACE_VARIANT)] if pos_idx is not None else []) + [
            ft.IconButton(icon=ft.Icons.SPLITSCREEN, tooltip="Priorizar datos", on_click=toggle_form_width),
            ft.IconButton(icon=ft.Icons.FULLSCREEN, tooltip="Maximizar", on_click=toggle_size),
        ], spacing=8)

        modal_content = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Container(
                        content=viewer,
                        bgcolor=Colors.WHITE,
                        border=ft.border.all(1, Colors.BORDER),
                        border_radius=8,
                        padding=4,
                        ref=viewer_container_ref,
                        width=900,
                    ),
                    ft.Row([
                        ft.TextButton("📂 Carpeta", on_click=lambda e: reveal_in_folder(path)),
                        ft.FilledButton("Abrir PDF", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e: open_path(path)),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=12, expand=True),
                ft.VerticalDivider(width=1, color=Colors.BORDER),
                ft.Container(
                    content=fields_column,
                    width=820,
                    padding=ft.padding.only(left=8),
                    ref=form_container_ref,
                ),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            width=1280,
            height=700,
        )

        dialog = ft.AlertDialog(
            title=ft.Row([
                title_row
            ], spacing=0),
            content=modal_content,
            actions=[
                ft.OutlinedButton("Cancelar", on_click=lambda e: safe_close_dialog(dialog)),
                ft.FilledButton("Aplicar cambios", icon=ft.Icons.CHECK, on_click=apply_and_close),
            ],
            modal=True,
        )
        safe_open_dialog(dialog)

    def open_pdf_viewer(_: Optional[ft.ControlEvent] = None) -> None:
        if not files:
            show_modal("Sin archivos", "Carga un PDF para visualizarlo.")
            return
        if selected_index is None or selected_index >= len(files):
            show_modal("Sin selección", "Selecciona un PDF de la lista primero.")
            return
        open_pdf_viewer_for(files[selected_index], selected_index)

    def update_preview(path: Optional[str] = None) -> None:
        if preview_ref.current is None:
            return
        if not path:
            preview_ref.current.content = ft.Column([
                ft.Icon(ft.Icons.PICTURE_AS_PDF, size=64, color=Colors.ON_SURFACE_VARIANT),
                ft.Text("Sin PDF seleccionado", color=Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ft.Text(
                    "Selecciona un documento para ver sus detalles.",
                    size=12,
                    color=Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER,
                ),
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            safe_control_update(preview_ref.current)
            return

        if not os.path.exists(path):
            preview_ref.current.content = ft.Column([
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=Colors.DANGER),
                ft.Text("Archivo no encontrado", weight=ft.FontWeight.BOLD, color=Colors.DANGER),
                ft.Text(path, size=10, color=Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            safe_control_update(preview_ref.current)
            log_add(f"❌ Ruta inexistente: {path}")
            return

        # Solo metadatos y accesos rápidos (sin visor embebido)
        size_kb = os.path.getsize(path) / 1024
        preview_ref.current.content = ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.PICTURE_AS_PDF, size=68, color=Colors.PRIMARY),
                    ft.Column([
                        ft.Text(os.path.basename(path), weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(f"📁 {size_kb:.1f} KB", size=12, color=Colors.ON_SURFACE_VARIANT),
                        ft.Text(path, size=10, color=Colors.ON_SURFACE_VARIANT, max_lines=2),
                    ], spacing=4, expand=True),
                ]),
                bgcolor=Colors.SURFACE,
                padding=12,
                border_radius=12,
                border=ft.border.all(1, Colors.BORDER),
            ),
            ft.Row([
                create_button("Abrir carpeta", ft.Icons.FOLDER_OPEN, "outlined", lambda e, p=path: reveal_in_folder(p)),
                create_button("Copiar ruta", ft.Icons.CONTENT_COPY, "text", lambda e, p=path: copy_to_clipboard(p)),
            ], spacing=8, wrap=True),
        ], spacing=12)
        safe_control_update(preview_ref.current)

    current_title = ft.Text("Sin archivo seleccionado", size=18, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE)
    current_meta = ft.Text("Selecciona un PDF de la lista para comenzar", size=14, color=Colors.ON_SURFACE_VARIANT)
    detailed_info_container = ft.Container(
        content=ft.Text(
            "📊 La información detallada aparecerá al seleccionar un PDF",
            size=12,
            color=Colors.ON_SURFACE_VARIANT,
            italic=True,
        )
    )

    file_info_panel = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.PICTURE_AS_PDF, size=20, color=Colors.PRIMARY),
                current_title,
            ], spacing=8),
            current_meta,
            ft.Divider(height=1, color=Colors.BORDER),
            detailed_info_container,
        ], spacing=8),
        padding=16,
        bgcolor=Colors.SURFACE_VARIANT,
        border_radius=12,
        border=ft.border.all(1, Colors.BORDER),
        margin=ft.margin.only(bottom=16),
    )

    files_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

    # Campos del formulario (idénticos a la vista JPG)
    tf_dni = ft.TextField(label="DNI (11 dígitos)", width=260)
    tf_lm = ft.TextField(label="LM", width=200)
    tf_or = ft.TextField(label="OR (DDD[L])", width=200)
    tf_clase = ft.TextField(label="Clase (4)", width=200)
    tf_libro = ft.TextField(label="Libro", width=200)
    tf_folio = ft.TextField(label="Folio", width=200)
    tf_apellidos = ft.TextField(label="Apellidos", width=400)
    tf_nombres = ft.TextField(label="Nombres", width=400)
    tf_fn = ft.TextField(label="Fecha Nac. (DD/MM/AAAA)", width=260)
    dd_presto = ft.Dropdown(
        label="¿Prestó servicio?",
        options=[ft.dropdown.Option("NO"), ft.dropdown.Option("SI")],
        value="NO",
        width=220,
    )
    tf_gran = ft.TextField(label="Gran Unidad", width=260)
    tf_unialta = ft.TextField(label="Unidad Alta", width=260)
    tf_unibaja = ft.TextField(label="Unidad Baja", width=260)
    tf_falta = ft.TextField(label="Fecha Alta", width=220)
    tf_fbaja = ft.TextField(label="Fecha Baja", width=220)
    tf_grado = ft.TextField(label="Grado", width=220)
    tf_motivo = ft.TextField(label="Motivo de Baja", width=600)

    def clear_form() -> None:
        for field in [
            tf_dni,
            tf_lm,
            tf_or,
            tf_clase,
            tf_libro,
            tf_folio,
            tf_apellidos,
            tf_nombres,
            tf_fn,
            tf_gran,
            tf_unialta,
            tf_unibaja,
            tf_falta,
            tf_fbaja,
            tf_grado,
            tf_motivo,
        ]:
            field.value = ""
        dd_presto.value = "NO"
        page.update()

    def pick(data: Dict[str, Any], *keys: str, default: str = "") -> str:
        for key in keys:
            value = data.get(key)
            if value not in (None, "", [], {}):
                return value
        return default

    def fill_form(data: Dict[str, Any]) -> None:
        tf_dni.value = pick(data, "dni")
        tf_lm.value = pick(data, "lm", "dni_o_lm")
        tf_or.value = pick(data, "or")
        tf_clase.value = pick(data, "clase")
        tf_libro.value = pick(data, "libro")
        tf_folio.value = pick(data, "folio")
        tf_apellidos.value = pick(data, "apellidos")
        tf_nombres.value = pick(data, "nombres")
        tf_fn.value = pick(data, "fecha_nacimiento")
        dd_presto.value = "SI" if pick(data, "presto_servicio", default="NO").upper() == "SI" else "NO"
        tf_gran.value = pick(data, "gran_unidad")
        tf_unialta.value = pick(data, "unidad_alta")
        tf_unibaja.value = pick(data, "unidad_baja")
        tf_falta.value = pick(data, "fecha_alta")
        tf_fbaja.value = pick(data, "fecha_baja")
        tf_grado.value = pick(data, "grado")
        tf_motivo.value = pick(data, "motivo_baja")
        page.update()

    def get_form_data() -> Dict[str, Any]:
        return {
            "dni": tf_dni.value,
            "lm": tf_lm.value,
            "or": tf_or.value,
            "clase": tf_clase.value,
            "libro": tf_libro.value,
            "folio": tf_folio.value,
            "apellidos": tf_apellidos.value,
            "nombres": tf_nombres.value,
            "fecha_nacimiento": tf_fn.value,
            "presto_servicio": dd_presto.value,
            "gran_unidad": tf_gran.value,
            "unidad_alta": tf_unialta.value,
            "unidad_baja": tf_unibaja.value,
            "fecha_alta": tf_falta.value,
            "fecha_baja": tf_fbaja.value,
            "grado": tf_grado.value,
            "motivo_baja": tf_motivo.value,
        }

    def select_file(index: int) -> None:
        nonlocal selected_index, last_result
        if index < 0 or index >= len(files):
            return
        if selected_index == index:
            return

        selected_index = index
        file_item = files[index]
        size = file_item.get("size") or 0
        size_mb = round(size / (1024 * 1024), 2)
        size_kb = round(size / 1024, 1)
        status = file_item.get("status", "Pendiente")

        status_text = {
            "Pendiente": "⏳ Listo para procesar",
            "Procesando": "🔄 Procesando con OCR...",
            "Procesado": "✅ OCR completado",
            "Validado": "✅ Validado y listo para guardar",
            "Editado": "📝 Datos editados manualmente",
            "Guardado": "💾 Registro guardado",
            "Error": "❌ Error al procesar",
        }

        current_title.value = f"Editando: {file_item['name']}"
        current_meta.value = (
            f"Tamaño: {size_mb} MB ({size_kb} KB) | Tipo: PDF | {status_text.get(status, status)}"
        )

        info_controls: List[ft.Control] = [
            ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=Colors.PRIMARY),
                ft.Text("Información del Archivo", weight=ft.FontWeight.BOLD, size=12),
            ], spacing=4),
            ft.Row([
                ft.Text("📁 Nombre:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                ft.Text(file_item["name"], size=11, color=Colors.ON_SURFACE_VARIANT, expand=True),
            ]),
            ft.Row([
                ft.Text("📏 Tamaño:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                ft.Text(f"{size_mb} MB ({size_kb} KB)", size=11, color=Colors.ON_SURFACE_VARIANT),
            ]),
            ft.Row([
                ft.Text("⚡ Estado:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                ft.Text(status_text.get(status, status), size=11, color=Colors.ON_SURFACE_VARIANT),
            ]),
        ]

        result = file_item.get("result") or {}
        if result:
            info_controls.extend([
                ft.Divider(height=1, color=Colors.BORDER),
                ft.Row([
                    ft.Icon(ft.Icons.SMART_TOY, size=16, color=Colors.SUCCESS),
                    ft.Text("Resultado OCR", weight=ft.FontWeight.BOLD, size=12),
                ], spacing=4),
                ft.Row([
                    ft.Text("🆔 DNI:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                    ft.Text(result.get("dni", "No detectado"), size=11, color=Colors.ON_SURFACE_VARIANT),
                ]),
                ft.Row([
                    ft.Text("👤 Apellidos:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                    ft.Text(result.get("apellidos", "No detectado"), size=11, color=Colors.ON_SURFACE_VARIANT),
                ]),
                ft.Row([
                    ft.Text("👤 Nombres:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                    ft.Text(result.get("nombres", "No detectado"), size=11, color=Colors.ON_SURFACE_VARIANT),
                ]),
            ])

        detailed_info_container.content = ft.Column(info_controls, spacing=4)

        if result:
            last_result = result
            fill_form(result)
        else:
            last_result = None
            clear_form()

        update_preview(file_item["path"])
        refresh_table()
        update_ocr_buttons()
        page.update()

    def remove_file(idx: int) -> None:
        nonlocal files, selected_index, last_result
        if idx < 0 or idx >= len(files):
            return
        files.pop(idx)
        if selected_index == idx:
            selected_index = None
            last_result = None
            current_title.value = "Sin archivo seleccionado"
            current_meta.value = "Selecciona un PDF de la lista para comenzar"
            detailed_info_container.content = ft.Text(
                "📊 La información detallada aparecerá al seleccionar un PDF",
                size=12,
                color=Colors.ON_SURFACE_VARIANT,
                italic=True,
            )
            clear_form()
            update_preview()
        elif selected_index is not None and selected_index > idx:
            selected_index -= 1
        refresh_table()
        update_ocr_buttons()
        page.update()

    def mark_validated(_: Optional[ft.ControlEvent] = None) -> None:
        if selected_index is None:
            show_modal("Sin selección", "Selecciona un PDF para marcarlo como validado.")
            return
        files[selected_index]["status"] = "Validado"
        refresh_table()
        log_add("✅ Marcado como validado")

    def apply_changes(_: Optional[ft.ControlEvent] = None) -> None:
        nonlocal last_result
        if selected_index is None:
            show_modal("Sin selección", "Selecciona un PDF para aplicar cambios.")
            return
        data = get_form_data()
        files[selected_index]["result"] = data
        files[selected_index]["status"] = "Editado"
        last_result = data
        refresh_table()
        log_add("📝 Cambios aplicados")

    def _resolve_user_id(conn) -> Optional[int]:
        try:
            username = (user_data or {}).get("username")
            row = conn.execute(select(Usuario).where(Usuario.nombre_usuario == username)).scalar_one_or_none() if username else None
            if row:
                return getattr(row, "id_usuario", None)
            # Fallback: primer usuario disponible
            first = conn.execute(select(Usuario)).scalars().first()
            if first:
                return getattr(first, "id_usuario", None)
            return None
        except Exception:
            return None

    async def save_indices(indices: List[int]) -> None:
        try:
            # get_db() devuelve un generador (patrón FastAPI). Extraemos la sesión real.
            sess_gen = get_db()
            try:
                conn = next(sess_gen)  # type: ignore
            except StopIteration:
                conn = None
            if conn is None:
                log_add("🚨 No se pudo conectar a la base de datos")
                return

            saved = 0
            skipped = 0
            user_id = _resolve_user_id(conn)
            if not user_id:
                show_modal("Usuarios no configurados", "No hay usuarios en la base de datos. Crea al menos uno para poder guardar.", ft.Icons.WARNING)
                return

            for idx in indices:
                file_item = files[idx]
                result = file_item.get("result") or {}
                # Validación obligatoria: DNI o LM
                dni_ok = bool((result.get("dni") or "").strip())
                lm_ok = bool((result.get("lm") or "").strip())
                if not (dni_ok or lm_ok):
                    file_item["status"] = "Error"
                    log_add(f"❌ Falta DNI o LM en: {file_item['name']}")
                    continue
                # Si el archivo PDF no está dentro de storage/data, lo copiamos para persistencia
                file_path = file_item["path"]
                stored_path = file_path
                try:
                    import shutil, time
                    from pathlib import Path
                    storage_dir = Path("storage") / "data"
                    storage_dir.mkdir(parents=True, exist_ok=True)
                    is_in_storage = "storage/data" in str(file_path).replace("\\","/").lower()
                    if not is_in_storage and os.path.exists(file_path):
                        ext = os.path.splitext(file_path)[1]
                        base_name = os.path.splitext(file_item['name'])[0][:40].replace(' ','_')
                        new_name = f"{base_name}_{int(time.time())}{ext}"
                        candidate = storage_dir / new_name
                        shutil.copy2(file_path, candidate)
                        stored_path = str(candidate)
                        file_item['stored_path'] = stored_path
                except Exception:
                    stored_path = file_path

                file_info = {"name": file_item["name"], "path": stored_path}
                # Evitar duplicados por ruta exacta del archivo
                try:
                    # Duplicado por ruta original o por ruta copiada
                    existing_doc = conn.execute(
                        select(Documento).where(Documento.ruta_almacenamiento == file_path)  # type: ignore
                    ).scalar_one_or_none()
                    if not existing_doc and stored_path != file_path:
                        existing_doc = conn.execute(
                            select(Documento).where(Documento.ruta_almacenamiento == stored_path)  # type: ignore
                        ).scalar_one_or_none()
                except Exception:
                    existing_doc = None

                if existing_doc:
                    file_item["status"] = "Guardado"
                    skipped += 1
                    log_add(f"ℹ️ Ya existía documento para: {file_item['name']}")
                    continue

                try:
                    ids_map = create_full_digital_record(conn, result, file_info, user_id)
                    file_item["status"] = "Guardado"
                    file_item["db_ids"] = ids_map
                    saved += 1
                    log_add(f"💾 Guardado: {file_item['name']}")
                except Exception as exc:
                    file_item["status"] = "Error"
                    log_add(f"🚨 Error al guardar {file_item['name']}: {exc}")

            try:
                conn.close()
            except Exception:
                pass
            refresh_table()
            update_ocr_buttons()
            show_modal(
                "Resultado de guardado",
                f"Nuevos guardados: {saved}\nYa existentes (omitidos): {skipped}",
                ft.Icons.SAVE,
            )
        except Exception as exc:
            log_add(f"🚨 Error al guardar: {exc}")

    def save_to_db(_: Optional[ft.ControlEvent] = None) -> None:
        """Unificado con lógica avanzada de la vista JPG (selección, estados, confirmaciones)."""
        marked = [i for i, it in enumerate(files) if it.get("selected")]
        candidates: List[int]
        if not marked and selected_index is not None:
            candidates = [selected_index]
        elif marked:
            candidates = marked
        else:
            show_modal(
                "Sin selección",
                "Marca los PDFs con ✅ o selecciona uno para guardarlo.",
                ft.Icons.WARNING,
            )
            return

        missing = [files[i]["name"] for i in candidates if not files[i].get("result")]
        if missing:
            show_modal(
                "PDF(s) sin datos OCR",
                "Procesa OCR antes de guardar:\n" + "\n".join(missing[:6]),
                ft.Icons.ERROR,
            )
            return

        validated = [i for i in candidates if files[i].get("status") == "Validado"]
        non_validated = [i for i in candidates if files[i].get("status") != "Validado"]

        if validated:
            page.run_task(save_indices, validated)
            log_add(f"💾 Guardando {len(validated)} PDF(s) validados")

        if non_validated:
            def confirm(_: ft.ControlEvent) -> None:
                safe_close_dialog(dialog)
                page.run_task(save_indices, non_validated)
                log_add(f"💾 Guardando {len(non_validated)} PDF(s) sin validar")

            def cancel(_: ft.ControlEvent) -> None:
                safe_close_dialog(dialog)

            dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.HELP, color=Colors.WARNING),
                    ft.Text("Guardar sin validar"),
                ], spacing=8),
                content=ft.Column([
                    ft.Text(
                        f"Hay {len(non_validated)} PDF(s) con datos OCR pero sin estado 'Validado'.",
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("¿Deseas continuar?", color=Colors.WARNING),
                ], spacing=8),
                actions=[
                    ft.TextButton("Cancelar", on_click=cancel),
                    ft.FilledButton("Sí, guardar", on_click=confirm, bgcolor=Colors.WARNING),
                ],
            )
            safe_open_dialog(dialog)

    def update_ocr_buttons() -> None:
        btn_ocr.disabled = not files or selected_index is None
        btn_ocr_batch.disabled = not any(f.get("status") in {"Pendiente", "Error"} for f in files)
        page.update()

    def refresh_table() -> None:
        files_list.controls.clear()
        update_docs_ref()

        if not files:
            files_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.PICTURE_AS_PDF, size=48, color=Colors.ON_SURFACE_VARIANT),
                        ft.Text("No hay PDFs cargados", weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE_VARIANT),
                        ft.Text("Usa 'Cargar PDFs' para comenzar", size=12, color=Colors.ON_SURFACE_VARIANT),
                    ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=32,
                    bgcolor=Colors.SURFACE,
                    border_radius=12,
                    border=ft.border.all(1, Colors.BORDER),
                    alignment=ft.alignment.center,
                )
            )
            page.update()
            return

        for idx, file_item in enumerate(files):
            status = file_item.get("status", "Pendiente")
            is_selected = idx == selected_index

            def toggle(event: ft.ControlEvent, index: int = idx) -> None:
                files[index]["selected"] = event.control.value

            def select(_: ft.ControlEvent, index: int = idx) -> None:
                select_file(index)

            def remove(_: ft.ControlEvent, index: int = idx) -> None:
                remove_file(index)

            def view(_: ft.ControlEvent, index: int = idx) -> None:
                # Abre el visor en modal para este archivo, sin depender de la selección
                try:
                    open_pdf_viewer_for(files[index], index)
                except Exception as ex:
                    show_modal("No se pudo abrir el visor", str(ex), ft.Icons.ERROR)

            card_bg = Colors.WHITE
            border_color = Colors.BORDER
            border_width = 1

            if status == "Procesando":
                card_bg = "#ECFDF5"
                border_color = Colors.SECONDARY
                border_width = 2
            elif is_selected:
                card_bg = Colors.SURFACE_VARIANT
                border_color = Colors.PRIMARY
                border_width = 2
            elif status == "Procesado":
                card_bg = "#ECFDF5"
                border_color = "#10B981"
            elif status == "Validado":
                card_bg = "#DCFCE7"
                border_color = "#059669"
            elif status == "Editado":
                card_bg = "#F5F3FF"
                border_color = "#8B5CF6"
            elif status == "Error":
                card_bg = "#FEF2F2"
                border_color = "#DC2626"
            elif status == "Guardado":
                card_bg = "#DCFCE7"
                border_color = Colors.PRIMARY

            status_control: ft.Control
            if status == "Procesando":
                status_control = ft.Container(
                    content=ft.Row([
                        ft.ProgressRing(width=14, height=14, stroke_width=2, color=Colors.SECONDARY),
                        ft.Text("OCR", size=9, color=Colors.SECONDARY, weight=ft.FontWeight.W_600),
                    ], spacing=3, tight=True),
                    bgcolor="#ECFDF5",
                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                    border_radius=12,
                    border=ft.border.all(1, Colors.SECONDARY + "30"),
                )
            else:
                status_control = create_status_chip(status)

            # Área clicable para seleccionar (solo el bloque de nombre / tamaño)
            name_area = ft.Container(
                content=ft.Column([
                    ft.Text(
                        file_item["name"],
                        weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        color=Colors.PRIMARY_DARK if is_selected else Colors.ON_SURFACE,
                        size=11,
                    ),
                    ft.Text(
                        f"{round((file_item.get('size') or 0) / 1024, 1)} KB",
                        size=9,
                        color=Colors.PRIMARY if is_selected else Colors.ON_SURFACE_VARIANT,
                    ),
                ], spacing=0),
                expand=True,
                ink=True,
                on_click=select,
            )

            file_card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Checkbox(
                            value=file_item.get("selected", False),
                            on_change=toggle,
                            active_color=Colors.PRIMARY,
                            scale=0.8,
                        ),
                        width=34,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.PICTURE_AS_PDF,
                            color=Colors.PRIMARY if is_selected else Colors.ON_SURFACE_VARIANT,
                            size=18,
                        ),
                        width=28,
                        alignment=ft.alignment.center,
                    ),
                    name_area,
                    ft.Container(status_control, width=120, alignment=ft.alignment.center),
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY,
                            tooltip="Ver PDF",
                            on_click=view,
                            icon_color=Colors.PRIMARY,
                            style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=4),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Eliminar",
                            on_click=remove,
                            icon_color=Colors.DANGER,
                            style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=4),
                        ),
                    ], spacing=0),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=6,
                margin=ft.margin.only(bottom=2),
                bgcolor=card_bg,
                border_radius=8,
                border=ft.border.all(border_width, border_color),
                ink=False,
            )

            files_list.controls.append(file_card)

        page.update()

    def run_ocr(_: Optional[ft.ControlEvent] = None) -> None:
        nonlocal last_result
        if any(f.get("status") == "Procesando" for f in files):
            show_modal("Procesando", "Espera a que finalice el OCR en curso.")
            return
        if selected_index is None:
            show_modal("Sin selección", "Selecciona un PDF para procesar.")
            return

        file_item = files[selected_index]
        path = file_item["path"]
        if not os.path.exists(path):
            file_item["status"] = "Error"
            refresh_table()
            show_modal("Archivo no encontrado", path, ft.Icons.ERROR)
            return

        try:
            file_item["status"] = "Procesando"
            refresh_table()
            update_ocr_buttons()
            data = extract_pdf(path)
            if isinstance(data, dict) and data.get("error"):
                file_item["status"] = "Error"
                refresh_table()
                update_ocr_buttons()
                show_modal("Error en OCR", data.get("mensaje", "Error desconocido"), ft.Icons.ERROR)
                return
            file_item["result"] = data or {}
            file_item["status"] = "Procesado"
            last_result = data or {}
            fill_form(last_result)
            refresh_table()
            update_ocr_buttons()
            log_add(f"✅ OCR completado: {file_item['name']}")
        except Exception as exc:
            file_item["status"] = "Error"
            refresh_table()
            update_ocr_buttons()
            show_modal("Error en OCR", str(exc), ft.Icons.ERROR)

    def run_ocr_batch(_: Optional[ft.ControlEvent] = None) -> None:
        if any(f.get("status") == "Procesando" for f in files):
            show_modal("Procesando", "Espera a que finalice el OCR en curso.")
            return

        pending = [i for i, it in enumerate(files) if it.get("status") in ("Pendiente", "Error")]
        if not pending:
            show_modal("Sin pendientes", "No hay PDFs pendientes de procesar.")
            return

        def confirm(_: ft.ControlEvent) -> None:
            safe_close_dialog(dialog)
            process_all()

        def cancel(_: ft.ControlEvent) -> None:
            safe_close_dialog(dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("🔄 Procesamiento en Lote (PDF)"),
            content=ft.Text(f"Se procesarán {len(pending)} documento(s). Esto puede tardar."),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel),
                ft.FilledButton("Procesar Todo", on_click=confirm),
            ],
        )
        safe_open_dialog(dialog)

        def process_all() -> None:
            processed = 0
            errors = 0
            for idx in pending:
                try:
                    item = files[idx]
                    path = item["path"]
                    if not os.path.exists(path):
                        item["status"] = "Error"
                        errors += 1
                        log_add(f"❌ No existe: {item['name']}")
                        continue
                    item["status"] = "Procesando"
                    refresh_table()
                    page.update()
                    data = extract_pdf(path)
                    if isinstance(data, dict) and data.get("error"):
                        item["status"] = "Error"
                        errors += 1
                        log_add(f"❌ Error en OCR: {data.get('mensaje', 'desconocido')}")
                        continue
                    item["result"] = data or {}
                    item["status"] = "Procesado"
                    processed += 1
                    if selected_index == idx:
                        fill_form(item["result"])
                    refresh_table()
                    page.update()
                except Exception as ex:
                    files[idx]["status"] = "Error"
                    errors += 1
                    log_add(f"❌ Error en {files[idx]['name']}: {ex}")
            update_ocr_buttons()
            results = ft.AlertDialog(
                title=ft.Text("✅ Procesamiento Completado"),
                content=ft.Text(f"Exitosos: {processed}\nErrores: {errors}"),
                actions=[ft.TextButton("OK", on_click=lambda e: page.close(results))],
            )
            page.open(results)

    def clear_all(_: Optional[ft.ControlEvent] = None) -> None:
        nonlocal files, selected_index, last_result
        files = []
        selected_index = None
        last_result = None
        files_list.controls.clear()
        current_title.value = "Sin archivo seleccionado"
        current_meta.value = "Selecciona un PDF de la lista para comenzar"
        detailed_info_container.content = ft.Text(
            "📊 La información detallada aparecerá al seleccionar un PDF",
            size=12,
            color=Colors.ON_SURFACE_VARIANT,
            italic=True,
        )
        clear_form()
        update_preview()
        update_docs_ref()
        update_ocr_buttons()
        page.update()

    def guess_size(path: str) -> int:
        if os.path.exists(path):
            try:
                return os.path.getsize(path)
            except Exception:
                return 0
        return 0

    def on_pick(event: ft.FilePickerResultEvent) -> None:
        nonlocal files, selected_index
        if not event or not event.files:
            return
            
        # Detección de modo WEB
        if os.getenv("FLET_MODE") == "web":
            log_add("🌐 Modo Web: Iniciando subida de archivos...")
            uploads = []
            for f in event.files:
                uploads.append(
                    ft.FilePickerUploadFile(
                        f.name,
                        upload_url=page.get_upload_url(f.name, 600),
                    )
                )
            file_picker.upload(uploads)
            return
        added = 0
        for entry in event.files:
            path = entry.path
            if not path:
                log_add(f"❌ Ruta no disponible: {entry.name}")
                continue
            if not os.path.exists(path):
                log_add(f"❌ Archivo inexistente: {entry.name}")
                continue
            if not path.lower().endswith(".pdf"):
                log_add(f"❌ Formato no soportado (se requiere .pdf): {entry.name}")
                continue
            if any(it["path"] == path for it in files):
                log_add(f"⚠️ Duplicado omitido: {entry.name}")
                continue
            files.append({
                "name": entry.name,
                "path": path,
                "mime": "application/pdf",
                "size": getattr(entry, "size", 0) or guess_size(path),
                "status": "Pendiente",
            })
            added += 1
        if not added:
            show_modal("Sin PDFs válidos", "No se agregó ningún PDF.", ft.Icons.WARNING)
            return
        selected_index = len(files) - 1
        refresh_table()
        select_file(selected_index)
        update_ocr_buttons()


    def on_upload_handler(e: ft.FilePickerUploadEvent):
        nonlocal files, selected_index
        if e.error:
            log_add(f"❌ Error al subir {e.file_name}: {e.error}")
            return
            
        log_add(f"✅ Archivo subido: {e.file_name}")
        
        # En modo web, los archivos se suben a 'uploads/<filename>'
        path = os.path.join("uploads", e.file_name)
        
        # Verificar si existe
        if not os.path.exists(path):
             log_add(f"⚠️ Archivo no encontrado tras subida: {path}")
             return

        # Verificar duplicados
        if any(it["path"] == path for it in files):
             log_add(f"⚠️ Duplicado omitido: {e.file_name}")
             return

        files.append({
            "name": e.file_name,
            "path": path,
            "mime": "application/pdf",
            "size": guess_size(path),
            "status": "Pendiente",
        })
        
        # Actualizar UI
        selected_index = len(files) - 1
        refresh_table()
        select_file(selected_index)
        update_ocr_buttons()

    # Lazy FilePicker: se agrega al overlay en el momento de uso
    file_picker: Optional[ft.FilePicker] = None

    def ensure_file_picker() -> ft.FilePicker:
        nonlocal file_picker
        if file_picker is None:
            file_picker = ft.FilePicker(on_result=on_pick, on_upload=on_upload_handler)
            try:
                if file_picker not in page.overlay:
                    page.overlay.append(file_picker)
                page.update()
            except Exception:
                pass
        return file_picker

    btn_pick = create_button(
        "Cargar PDFs",
        ft.Icons.UPLOAD_FILE,
        "filled",
        lambda e: ensure_file_picker().pick_files(allow_multiple=True, allowed_extensions=["pdf"]),
    )
    btn_ocr = create_button("Procesar OCR", ft.Icons.SMART_TOY, "filled", run_ocr, Colors.SECONDARY)
    btn_ocr_batch = create_button("OCR Todo", ft.Icons.AUTO_AWESOME, "outlined", run_ocr_batch, Colors.SECONDARY)
    btn_clear = create_button("Limpiar Todo", ft.Icons.CLEAR_ALL, "outlined", clear_all, Colors.WARNING)
    btn_save = create_button("Guardar en BD", ft.Icons.SAVE, "filled", save_to_db, Colors.SECONDARY)
    btn_apply = create_button("Aplicar cambios", ft.Icons.CHECK, "outlined", apply_changes, Colors.PRIMARY)
    btn_validate = create_button("Marcar validado", ft.Icons.VERIFIED, "text", mark_validated, Colors.SECONDARY)

    # Contenido por defecto para la vista previa (evita actualizar antes de montar)
    default_preview = ft.Container(
        ref=preview_ref,
        content=ft.Column([
            ft.Icon(ft.Icons.PICTURE_AS_PDF, size=64, color=Colors.ON_SURFACE_VARIANT),
            ft.Text("Sin PDF seleccionado", color=Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
            ft.Text(
                "Selecciona un documento para ver sus detalles.",
                size=12,
                color=Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
    )

    # Panel izquierdo con botones + lista (sin visor ni detalle embebido)
    left_column = ft.Column([
        create_card(
            ft.Column([
                ft.Row([
                    btn_pick,
                    btn_ocr,
                    btn_ocr_batch,
                    btn_clear,
                ], spacing=8, wrap=True),
                ft.Container(files_list, expand=True),
            ], spacing=12, expand=True),
            title="Gestión de PDFs",
            padding=16,
        ),
    ], spacing=16, expand=True)

    form_grid = ft.ResponsiveRow([
        ft.Container(tf_dni, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_lm, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_or, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_clase, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_libro, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_folio, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_apellidos, col={"xs": 12, "lg": 6}),
        ft.Container(tf_nombres, col={"xs": 12, "lg": 6}),
        ft.Container(tf_fn, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(dd_presto, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_gran, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_unialta, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_unibaja, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_falta, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_fbaja, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_grado, col={"xs": 12, "md": 6, "lg": 4}),
        ft.Container(tf_motivo, col={"xs": 12}),
    ], run_spacing=8)

    # Sección derecha: Info + Form + Botonera inferior (sin visor embebido permanente)
    right_column = ft.Column([
        file_info_panel,
        create_card(form_grid, title="Datos extraídos / Edición"),
        ft.Row([
            create_button("Aplicar Cambios", ft.Icons.CHECK_CIRCLE, "filled", apply_changes),
            create_button("Marcar Validado", ft.Icons.VERIFIED, "outlined", mark_validated, Colors.SUCCESS),
            create_button("Guardar en BD", ft.Icons.SAVE, "filled", save_to_db, Colors.SECONDARY),
        ], spacing=10, wrap=True),
    ], spacing=16, expand=True)

    main_content = ft.ResponsiveRow([
        ft.Container(left_column, col={"xs": 12, "md": 5, "lg": 4, "xl": 4}, padding=ft.padding.only(right=8)),
        ft.Container(right_column, col={"xs": 12, "md": 7, "lg": 8, "xl": 8}, padding=ft.padding.only(left=8)),
    ], expand=True, spacing=0)

    header = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.PICTURE_AS_PDF, size=28, color=Colors.PRIMARY),
            ft.Text("Digitalización de PDFs", size=20, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.only(bottom=12),
    )

    root = ft.Container(
        content=ft.Column([
            header,
            ft.Container(main_content, expand=True),
        ], expand=True, scroll=ft.ScrollMode.AUTO),
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        expand=True,
        bgcolor=Colors.SURFACE,
    )

    def cleanup() -> None:
        unregister_guard("digitalizacion_pdf")

    root.cleanup = cleanup  # type: ignore[attr-defined]

    # Inicialización visual sin forzar updates prematuros
    # (los botones y preview se actualizarán en las acciones del usuario)

    return root
