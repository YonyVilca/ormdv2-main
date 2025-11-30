# -*- coding: utf-8 -*-
import os
import shutil
"""Digitalización de Imágenes (JPG/PNG) - Vista completa restaurada.

Esta versión corrige la corrupción previa donde `_save_indices` quedó fuera del scope
de la función principal y provocó errores `nonlocal` y fallos en `page.run_task`.

Funcionalidades:
 - Carga múltiple con verificación de duplicados
 - Previsualización y visor ampliado con zoom
 - OCR individual y en lote (`extract_image`)
 - Edición de formulario y marcado de validación
 - Guardado en BD (detección de duplicados por ruta) con resumen modal
 - `_save_indices` async para uso seguro con `page.run_task`
"""

import os
import sys
import asyncio
import flet as ft
from PIL import Image as PILImage
from utils.extractors import extract_image
from utils.nav_guard import register_guard, unregister_guard
from database.connection import get_db
from database.crud import create_full_digital_record


class Colors:
    PRIMARY = "#16A34A"           # Verde principal semi-oscuro
    PRIMARY_LIGHT = "#22C55E"     # Verde claro
    PRIMARY_DARK = "#15803D"      # Verde oscuro
    SECONDARY = "#059669"         # Verde secundario
    SECONDARY_LIGHT = "#10B981"   # Verde claro secundario
    WARNING = "#F59E0B"           # Naranja (mantener para alertas)
    DANGER = "#EF4444"            # Rojo (mantener para errores)
    SUCCESS = "#047857"           # Verde éxito oscuro
    SURFACE = "#F0FDF4"           # Fondo verde muy claro
    SURFACE_VARIANT = "#DCFCE7"   # Verde claro para variantes
    ON_SURFACE = "#14532D"        # Texto verde oscuro
    ON_SURFACE_VARIANT = "#166534" # Texto verde medio
    BORDER = "#BBF7D0"            # Borde verde claro
    WHITE = "#FFFFFF"
    BLACK = "#000000"

# Componentes UI reutilizables (iguales que PDF)
def create_card(content, title=None, padding=20):
    card_content = [content] if not title else [
        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ft.Divider(color=Colors.BORDER, height=1),
        content
    ]
    return ft.Container(
        content=ft.Column(card_content, spacing=12),
        padding=padding,
        bgcolor=Colors.WHITE,
        border_radius=12,
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=8, color="#10000000", offset=ft.Offset(0, 2)),
        border=ft.border.all(1, Colors.BORDER)
    )

def create_status_chip(status):
    cfg = {
        "Pendiente": {"c": "#7C3AED", "bg": "#F3F4F6", "icon": ft.Icons.SCHEDULE, "tx": "Pendiente"},
        "Procesando": {"c": "#059669", "bg": "#ECFDF5", "icon": ft.Icons.AUTORENEW, "tx": "OCR"},
        "Procesado": {"c": "#10B981", "bg": "#ECFDF5", "icon": ft.Icons.CHECK_CIRCLE_OUTLINE, "tx": "Procesado"},
        "Validado": {"c": "#059669", "bg": "#DCFCE7", "icon": ft.Icons.VERIFIED, "tx": "Validado"},
        "Editado": {"c": "#8B5CF6", "bg": "#F5F3FF", "icon": ft.Icons.EDIT, "tx": "Editado"},
        "Guardado": {"c": "#047857", "bg": "#ECFDF5", "icon": ft.Icons.SAVE, "tx": "Guardado"},
        "Error": {"c": "#DC2626", "bg": "#FEF2F2", "icon": ft.Icons.INFO, "tx": "Error"},
    }.get(status, None)
    if not cfg:
        return ft.Container()
    return ft.Container(
        content=ft.Row([
            ft.Icon(cfg["icon"], size=12, color=cfg["c"]),
            ft.Text(cfg["tx"], size=10, color=cfg["c"], weight=ft.FontWeight.W_600),
        ], spacing=3, tight=True),
        bgcolor=cfg["bg"],
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=12,
        width=100,
        border=ft.border.all(1, cfg["c"]+"30")
    )

def create_button(text, icon, style="filled", on_click=None, color=None):
    style_cfg = ft.ButtonStyle(
        bgcolor=color or Colors.PRIMARY if style == "filled" else None,
        color= Colors.WHITE if style == "filled" else (color or Colors.PRIMARY),
        side= ft.BorderSide(1, color or Colors.PRIMARY) if style == "outlined" else None,
        padding=ft.padding.symmetric(horizontal=16, vertical=12)
    )
    btn_cls = {"filled": ft.ElevatedButton, "outlined": ft.OutlinedButton}.get(style, ft.TextButton)
    return btn_cls(text=text, icon=icon, on_click=on_click, style=style_cfg)

def create_digitalizacion_jpg_view(page: ft.Page, user_data=None):
    files: list[dict] = []
    selected_index: int | None = None
    last_result: dict | None = None

    def has_pending_work():
        return bool(files) or last_result is not None or any(f.get("status") == "Procesando" for f in files)
    register_guard("digitalizacion_jpg", has_pending_work)

    log = ft.ListView(expand=True, spacing=2, auto_scroll=True)
    def log_add(msg: str, level="info"):  # silenciado
        pass

    preview_container = ft.Ref[ft.Container]()

    # --- Utilidades ---
    def update_ocr_button():
        if selected_index is not None and selected_index < len(files):
            st = files[selected_index].get("status", "Pendiente")
            if st == "Procesando":
                btn_ocr.disabled = True; btn_ocr.text = "Procesando..."
            elif st == "Procesado":
                btn_ocr.disabled = False; btn_ocr.text = "Reprocesar OCR"
            else:
                btn_ocr.disabled = False; btn_ocr.text = "Procesar OCR"
        else:
            btn_ocr.disabled = True; btn_ocr.text = "Procesar OCR"
        page.update()

    def clear_form():
        for f in [tf_dni, tf_lm, tf_or, tf_clase, tf_libro, tf_folio, tf_apellidos, tf_nombres, tf_fn,
                  tf_gran, tf_unialta, tf_unibaja, tf_falta, tf_fbaja, tf_grado, tf_motivo]:
            f.value = ""
        dd_presto.value = "NO"
        page.update()

    def fill_form(d: dict):
        def pick(*keys, default=""):
            for k in keys:
                v = d.get(k)
                if v not in (None, "", [], {}):
                    return v
            return default
        tf_dni.value = pick("dni"); tf_lm.value = pick("lm","dni_o_lm"); tf_or.value = pick("or")
        tf_clase.value = pick("clase"); tf_libro.value = pick("libro"); tf_folio.value = pick("folio")
        tf_apellidos.value = pick("apellidos"); tf_nombres.value = pick("nombres")
        tf_fn.value = pick("fecha_nacimiento"); ps = pick("presto_servicio", default="NO").strip().upper()
        dd_presto.value = "SI" if ps == "SI" else "NO"
        tf_gran.value = pick("gran_unidad"); tf_unialta.value = pick("unidad_alta"); tf_unibaja.value = pick("unidad_baja")
        tf_falta.value = pick("fecha_alta"); tf_fbaja.value = pick("fecha_baja"); tf_grado.value = pick("grado")
        tf_motivo.value = pick("motivo_baja"); page.update()

    def refresh_table():
        files_list.controls.clear()
        if not files:
            files_list.controls.append(ft.Container(content=ft.Column([
                ft.Icon(ft.Icons.UPLOAD_FILE, size=48, color=Colors.ON_SURFACE_VARIANT),
                ft.Text("No hay imágenes cargadas", color=Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.BOLD),
                ft.Text("Usa 'Cargar Imágenes' para comenzar", size=12, color=Colors.ON_SURFACE_VARIANT)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8), padding=40, alignment=ft.alignment.center,
                bgcolor=Colors.SURFACE, border_radius=8, border=ft.border.all(1, Colors.BORDER)))
            page.update(); return
        for i, it in enumerate(files):
            def on_toggle(ch, idx=i): files[idx]["selected"] = ch.control.value
            def on_select(e, idx=i):
                nonlocal selected_index, last_result
                if selected_index == idx: return
                selected_index = idx
                fi = files[idx]
                current_title.value = f"Editando: {fi['name']}"
                size_kb = round((fi.get('size') or 0)/1024,1)
                current_meta.value = f"{size_kb} KB | {fi.get('mime','image/*')} | {fi.get('status','Pendiente')}"
                if fi.get("result"): last_result = fi["result"]; fill_form(last_result)
                else: last_result=None; clear_form()
                update_ocr_button(); refresh_table()
            def on_remove(e, idx=i):
                nonlocal selected_index, last_result
                files.pop(idx)
                if selected_index == idx:
                    selected_index=None; last_result=None; current_title.value="Sin archivo"; current_meta.value="Seleccione..."; clear_form()
                elif selected_index and selected_index>idx: selected_index-=1
                refresh_table(); update_ocr_button()
            status = it.get("status","Pendiente"); is_sel = i==selected_index
            chip = create_status_chip(status) if status!="Procesando" else ft.Container(
                content=ft.Row([ft.ProgressRing(width=14,height=14,stroke_width=2,color="#059669"), ft.Text("OCR", size=9,color="#059669")],spacing=3,tight=True),
                bgcolor="#ECFDF5", padding=ft.padding.symmetric(horizontal=6, vertical=3), border_radius=12,
                border=ft.border.all(1,"#05966930"))
            files_list.controls.append(ft.Container(
                content=ft.Row([
                    ft.Checkbox(value=it.get("selected",False), on_change=on_toggle, scale=0.8),
                    ft.Icon(ft.Icons.PHOTO,size=16,color=Colors.PRIMARY if is_sel else Colors.ON_SURFACE_VARIANT),
                    ft.Column([ft.Text(it['name'], size=11, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.NORMAL, overflow=ft.TextOverflow.ELLIPSIS),
                               ft.Text(f"{round((it.get('size') or 0)/1024,1)} KB", size=9, color=Colors.ON_SURFACE_VARIANT)],spacing=0, expand=True),
                    ft.Container(content=chip,width=120),
                    ft.Row([
                        ft.IconButton(icon=ft.Icons.VISIBILITY, icon_color=Colors.PRIMARY, tooltip="Ver", on_click=lambda e, idx=i: on_view(idx)),
                        ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=Colors.DANGER, tooltip="Eliminar", on_click=on_remove)
                    ],spacing=0)
                ],alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor="#ECFDF5" if status=="Procesando" else (Colors.SURFACE_VARIANT if is_sel else Colors.WHITE),
                border=ft.border.all(2 if is_sel or status=="Procesando" else 1, Colors.PRIMARY if is_sel else ("#059669" if status=="Procesando" else Colors.BORDER)),
                border_radius=8, padding=6, margin=ft.margin.only(bottom=4), on_click=on_select
            ))
        page.update()

    def on_view(idx:int):
        if idx<0 or idx>=len(files):
            return
        open_image_viewer_for(files[idx], idx)

    def open_image_viewer_for(file_item: dict, pos_idx: int | None = None):
        path = file_item.get("path")
        if not path or not os.path.exists(path):
            dlg = ft.AlertDialog(title=ft.Text("Archivo no encontrado"), content=ft.Text(path or "(sin ruta)"))
            page.open(dlg)
            return

        def open_path(p: str):
            try:
                if os.name == "nt":
                    os.startfile(p)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    import subprocess; subprocess.run(["open", p], check=False)
                else:
                    import subprocess; subprocess.run(["xdg-open", p], check=False)
            except Exception:
                pass

        def reveal_in_folder(p: str):
            try:
                if os.name == "nt":
                    import subprocess; subprocess.run(["explorer", "/select,", p], check=False)
                elif sys.platform == "darwin":
                    import subprocess; subprocess.run(["open", "-R", p], check=False)
                else:
                    open_path(os.path.dirname(p))
            except Exception:
                pass

        try:
            orig_w, orig_h = PILImage.open(path).size
        except Exception:
            orig_w, orig_h = (1200, 800)

        state = {"zoom": 1.0}
        img_ref: ft.Ref[ft.Image] = ft.Ref[ft.Image]()
        zoom_percent = ft.Text("100%", size=11, color=Colors.ON_SURFACE_VARIANT)

        def render_current():
            if img_ref.current is not None:
                img_ref.current.width = int(orig_w * state["zoom"])
                img_ref.current.height = int(orig_h * state["zoom"])
            zoom_percent.value = f"{int(state['zoom']*100)}%"
            try:
                if img_ref.current is not None:
                    img_ref.current.update()
            except Exception:
                pass

        slider_ref: ft.Ref[ft.Slider] = ft.Ref[ft.Slider]()

        def on_zoom_change(e: ft.ControlEvent):
            try:
                val = float(e.control.value)
                state["zoom"] = max(0.2, min(val, 5.0))
                render_current()
            except Exception:
                pass

        def zoom_delta(delta: float):
            z = max(0.2, min(state["zoom"] + delta, 5.0))
            state["zoom"] = z
            if slider_ref.current is not None:
                slider_ref.current.value = z
            render_current()

        form_container_ref: ft.Ref[ft.Container] = ft.Ref[ft.Container]()
        viewer_container_ref: ft.Ref[ft.Container] = ft.Ref[ft.Container]()

        def fit_width(_: ft.ControlEvent):
            try:
                target = 660
                if viewer_container_ref.current is not None and viewer_container_ref.current.width:
                    target = max(320, int(viewer_container_ref.current.width) - 40)
                new_zoom = max(0.2, min(target / float(orig_w), 5.0))
                state["zoom"] = new_zoom
                if slider_ref.current is not None:
                    slider_ref.current.value = new_zoom
                render_current()
            except Exception:
                pass

        def reset_zoom(_: ft.ControlEvent):
            state["zoom"] = 1.0
            if slider_ref.current is not None:
                slider_ref.current.value = 1.0
            render_current()

        btn_zoom_out = ft.IconButton(icon=ft.Icons.REMOVE, tooltip="Zoom -", on_click=lambda e: zoom_delta(-0.1))
        btn_zoom_in = ft.IconButton(icon=ft.Icons.ADD, tooltip="Zoom +", on_click=lambda e: zoom_delta(0.1))
        slider = ft.Slider(ref=slider_ref, min=0.2, max=5.0, divisions=48, value=state["zoom"], on_change=on_zoom_change, on_change_end=on_zoom_change, width=220)

        is_max = {"value": False}
        is_wide_form = {"value": True}

        def toggle_size(_: ft.ControlEvent | None = None):
            is_max["value"] = not is_max["value"]
            try:
                modal_content.width = 1680 if is_max["value"] else 1280
                modal_content.height = 860 if is_max["value"] else 700
                page.update()
            except Exception:
                pass

        def toggle_form_width(_: ft.ControlEvent | None = None):
            is_wide_form["value"] = not is_wide_form["value"]
            try:
                if form_container_ref.current is not None:
                    form_container_ref.current.width = 820 if is_wide_form["value"] else 600
                if viewer_container_ref.current is not None:
                    viewer_container_ref.current.width = 740 if is_wide_form["value"] else 900
                page.update()
            except Exception:
                pass

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
        current_data = (file_item.get("result") or {}).copy()
        ocr_data = (file_item.get("ocr_raw") or current_data).copy()
        inputs: dict[str, ft.Ref[ft.TextField]] = {k: ft.Ref[ft.TextField]() for k in field_labels.keys()}

        def row_for_field(key: str) -> ft.Control:
            ocr_val = str(ocr_data.get(key) or "")
            cur_val = str(current_data.get(key) or "")
            differs_initial = (ocr_val or "") != (cur_val or "") and (ocr_val != "")

            def compute_diff(v: str) -> bool:
                return (ocr_val or "") != (v or "") and (ocr_val != "")

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
                    inputs[key].current.update()

            def swap_values(_: ft.ControlEvent) -> None:
                nonlocal ocr_val
                if inputs[key].current is not None:
                    new_val = inputs[key].current.value
                    inputs[key].current.value = ocr_val
                    ocr_val = new_val
                    update_field_style(key)
                    inputs[key].current.update()

            diff_icon: ft.Ref[ft.Icon] = ft.Ref[ft.Icon]()

            def update_field_style(field_key: str) -> None:
                ref = inputs[field_key].current
                if ref is None:
                    return
                diff_now = compute_diff(ref.value or "")
                ref.border_color = "#F59E0B" if diff_now else Colors.BORDER
                ref.focused_border_color = "#D97706" if diff_now else Colors.PRIMARY
                ref.tooltip = ref.value or ""
                if diff_icon.current is not None:
                    diff_icon.current.visible = diff_now
                try:
                    ref.update(); diff_icon.current.update()
                except Exception:
                    pass

            ocr_display = ft.Text(
                ocr_val or "(vacío)", size=12, color=Colors.ON_SURFACE, selectable=True,
                max_lines=3, overflow=ft.TextOverflow.ELLIPSIS, tooltip=ocr_val or "",
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
                ft.Row([ocr_chip, tf], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=6)

        fields_column = ft.Column([
            ft.Text("Campos extraídos (comparación OCR)", size=13, weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
            ft.Divider(height=1, color=Colors.BORDER),
        ] + [row_for_field(k) for k in field_labels.keys()], spacing=8, scroll=ft.ScrollMode.AUTO)

        def apply_and_close(_: ft.ControlEvent | None = None):
            updated: dict = {}
            for k in field_labels.keys():
                ref = inputs[k].current
                updated[k] = ref.value if ref is not None else current_data.get(k)
            file_item["result"] = updated
            file_item["status"] = "Editado"
            try:
                if selected_index is not None and files[selected_index] is file_item:
                    fill_form(updated)
                refresh_table(); update_ocr_button()
            except Exception:
                pass
            page.close(dialog)

        # Viewer elements
        img = ft.Image(ref=img_ref, src=path, fit=ft.ImageFit.CONTAIN, border_radius=4, gapless_playback=True)
        def on_double_tap(_: ft.ControlEvent):
            zoom_delta(0.2)
        img_gesture = ft.GestureDetector(content=img, on_double_tap=on_double_tap)
        scroller = ft.Row([ft.Column([img_gesture], scroll=ft.ScrollMode.ALWAYS, expand=True)], scroll=ft.ScrollMode.ALWAYS, expand=True)

        nav = ft.Row([
            btn_zoom_out,
            slider,
            btn_zoom_in,
            zoom_percent,
            ft.IconButton(icon=ft.Icons.FIT_SCREEN, tooltip="Ajustar ancho", on_click=fit_width),
            ft.IconButton(icon=ft.Icons.RESTORE, tooltip="Reset zoom", on_click=reset_zoom),
        ], alignment=ft.MainAxisAlignment.START, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        title_row = ft.Row([
            ft.Icon(ft.Icons.IMAGE, color=Colors.PRIMARY),
            ft.Text(file_item.get("name", os.path.basename(path)), weight=ft.FontWeight.BOLD, expand=True),
        ] + ([ft.Text(f"{(pos_idx or 0) + 1}/{len(files)}", size=11, color=Colors.ON_SURFACE_VARIANT)] if pos_idx is not None else []) + [
            ft.IconButton(icon=ft.Icons.SPLITSCREEN, tooltip="Priorizar datos", on_click=toggle_form_width),
            ft.IconButton(icon=ft.Icons.FULLSCREEN, tooltip="Maximizar", on_click=toggle_size),
        ], spacing=8)

        viewer = ft.Container(
            content=ft.Column([
                nav,
                ft.Container(content=scroller, expand=True, bgcolor=Colors.BLACK+"08", border_radius=8, padding=4),
            ], expand=True, spacing=8),
            width=720, height=540, bgcolor=Colors.SURFACE, border_radius=12, border=ft.border.all(1, Colors.BORDER)
        )

        modal_content = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Container(content=viewer, bgcolor=Colors.WHITE, border=ft.border.all(1, Colors.BORDER), border_radius=8, padding=4, ref=viewer_container_ref, width=900),
                    ft.Row([
                        ft.TextButton("📂 Carpeta", on_click=lambda e: reveal_in_folder(path)),
                        ft.FilledButton("Abrir imagen", icon=ft.Icons.OPEN_IN_NEW, on_click=lambda e: open_path(path)),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ], spacing=12, expand=True),
                ft.VerticalDivider(width=1, color=Colors.BORDER),
                ft.Container(content=fields_column, width=820, padding=ft.padding.only(left=8), ref=form_container_ref),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
            width=1280, height=700,
        )

        dialog = ft.AlertDialog(
            title=ft.Row([title_row], spacing=0),
            content=modal_content,
            actions=[ft.OutlinedButton("Cancelar", on_click=lambda e: page.close(dialog)), ft.FilledButton("Aplicar cambios", icon=ft.Icons.CHECK, on_click=apply_and_close)],
            modal=True,
        )
        page.open(dialog)
        render_current()

    # --- Picker ---
    def guess_mime(path:str)->str:
        ext=os.path.splitext(path.lower())[1]; return {".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png"}.get(ext,"image/jpeg")
    def on_upload_handler(e: ft.FilePickerUploadEvent):
        nonlocal selected_index
        if e.error: return
        
        path = os.path.join("uploads", e.file_name)
        if not os.path.exists(path): return
        if any(it['path']==path for it in files): return

        try: size=os.path.getsize(path)
        except Exception: size=0

        files.append({
            "name": e.file_name,
            "path": path,
            "mime": guess_mime(path),
            "size": size,
            "status": "Pendiente"
        })
        
        selected_index = len(files) - 1
        refresh_table()
        update_ocr_button()

    def on_pick(e: ft.FilePickerResultEvent):
        nonlocal selected_index
        if not e or not e.files: return

        if os.getenv("FLET_MODE") == "web":
            uploads = []
            for f in e.files:
                uploads.append(
                    ft.FilePickerUploadFile(
                        f.name,
                        upload_url=page.get_upload_url(f.name, 600),
                    )
                )
            fp.upload(uploads)
            return
        added=0
        for f in e.files:
            p=f.path or f.name
            if not p or not os.path.exists(p): continue
            if not p.lower().endswith(('.jpg','.jpeg','.png','.gif','.bmp','.webp')): continue
            if any(it['path']==p for it in files): continue
            try: size=os.path.getsize(p)
            except Exception: size=0
            files.append({"name":f.name,"path":p,"mime":guess_mime(p),"size":size,"status":"Pendiente"}); added+=1
        if added:
            selected_index=len(files)-1
            refresh_table()
            update_ocr_button()
    fp=ft.FilePicker(on_result=on_pick, on_upload=on_upload_handler); page.overlay.append(fp)

    # --- OCR ---
    def run_ocr_single():
        nonlocal last_result
        if selected_index is None or selected_index>=len(files):
            dlg = ft.AlertDialog(title=ft.Text("Advertencia"), content=ft.Text("No hay imagen seleccionada para procesar OCR."), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))], modal=True)
            page.open(dlg)
            return
        it=files[selected_index]
        if it.get("status") == "Procesando": return
        path=it['path']
        if not os.path.exists(path): it['status']="Error"; refresh_table(); return
        it['status']="Procesando"; refresh_table(); update_ocr_button()
        try:
            data=extract_image(path) or {}
            if isinstance(data, dict) and data.get("error"):
                it['status']="Error"
            else:
                it['status']="Procesado"; it['result']=data; last_result=data; fill_form(data)
        except Exception:
            it['status']="Error"
        refresh_table(); update_ocr_button()

    def run_ocr_batch():
        targets=[i for i,f in enumerate(files) if f.get('status') in ("Pendiente","Error")]
        if not targets: return
        for idx in targets:
            it=files[idx]; path=it['path']
            if not os.path.exists(path): it['status']="Error"; continue
            it['status']="Procesando"; refresh_table()
            try:
                data=extract_image(path) or {}
                if isinstance(data, dict) and data.get("error"):
                    it['status']="Error"
                else:
                    it['status']="Procesado"; it['result']=data
            except Exception:
                it['status']="Error"
        refresh_table(); update_ocr_button()

    # --- Form helpers ---
    def get_form_data():
        return {"dni":tf_dni.value,"lm":tf_lm.value,"or":tf_or.value,"clase":tf_clase.value,"libro":tf_libro.value,
                "folio":tf_folio.value,"apellidos":tf_apellidos.value,"nombres":tf_nombres.value,"fecha_nacimiento":tf_fn.value,
                "presto_servicio":dd_presto.value,"gran_unidad":tf_gran.value,"unidad_alta":tf_unialta.value,
                "unidad_baja":tf_unibaja.value,"fecha_alta":tf_falta.value,"fecha_baja":tf_fbaja.value,
                "grado":tf_grado.value,"motivo_baja":tf_motivo.value}

    def apply_changes():
        nonlocal last_result
        if selected_index is None:
            dlg = ft.AlertDialog(title=ft.Text("Advertencia"), content=ft.Text("No hay imagen seleccionada para aplicar cambios."), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))], modal=True)
            page.open(dlg)
            return
        data=get_form_data(); last_result=data; files[selected_index]['result']=data; files[selected_index]['status']='Editado'; refresh_table()

    def mark_validated():
        if selected_index is None:
            dlg = ft.AlertDialog(title=ft.Text("Advertencia"), content=ft.Text("No hay imagen seleccionada para marcar como validada."), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))], modal=True)
            page.open(dlg)
            return
        files[selected_index]['status']='Validado'; refresh_table()

    async def _save_indices(indices:list[int]):
        try:
            sess_gen=get_db()
            try: db=next(sess_gen)
            except StopIteration: db=None
            if db is None: return
            from database.models import Documento, Usuario
            from sqlalchemy import select
            try:
                username=(user_data or {}).get("username")
                user_row = db.execute(select(Usuario).where(Usuario.nombre_usuario==username)).scalar_one_or_none() if username else None
                if user_row is not None:
                    user_id = getattr(user_row, "id_usuario", None) or 1
                else:
                    first_user = db.execute(select(Usuario)).scalars().first()
                    if first_user:
                        user_id = getattr(first_user, "id_usuario", 1)
                    else:
                        user_id = 1
            except Exception:
                user_id=1
            saved=0; skipped=0
            invalid=0
            import shutil, time
            from pathlib import Path
            storage_dir = Path("storage") / "data"
            try:
                storage_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            for idx in indices:
                if idx>=len(files): continue
                it=files[idx]; res=it.get('result') or {}
                if not res:
                    continue
                # Validación mínima: se requiere DNI o LM para crear el ciudadano
                dni_ok = bool((res.get("dni") or "").strip())
                lm_ok = bool((res.get("lm") or "").strip())
                if not (dni_ok or lm_ok):
                    it['status'] = 'Error'
                    invalid += 1
                    continue
                path=it['path']
                original_path = path  # conservar para verificación de duplicado
                # Si el archivo no está ya dentro de storage/data lo copiamos para persistencia
                stored_path = path
                try:
                    if storage_dir.exists() and (not str(path).lower().replace("\\","/").endswith("/storage/data") and "storage/data" not in str(path).replace("\\","/").lower()):
                        ext = os.path.splitext(path)[1]
                        base_name = os.path.splitext(it['name'])[0][:40].replace(' ','_')
                        new_name = f"{base_name}_{int(time.time())}{ext}"
                        candidate = storage_dir / new_name
                        shutil.copy2(path, candidate)
                        stored_path = str(candidate)
                        it['stored_path'] = stored_path
                except Exception:
                    # Si falla la copia seguimos guardando con la ruta original
                    stored_path = path
                try:
                    from database.models import Documento
                    from sqlalchemy import select as _sel
                    # Verifica duplicado por ruta original o por ruta ya copiada
                    existing=db.execute(_sel(Documento).where(Documento.ruta_almacenamiento==original_path)).scalar_one_or_none()
                    if not existing and stored_path != original_path:
                        existing=db.execute(_sel(Documento).where(Documento.ruta_almacenamiento==stored_path)).scalar_one_or_none()
                except Exception:
                    existing=None
                if existing:
                    skipped+=1; it['status']='Guardado'; continue
                try:
                    ids=create_full_digital_record(db,res,{"name":it['name'],"path":stored_path},user_id)
                    it['db_ids']=ids; it['status']='Guardado'; saved+=1
                except Exception:
                    it['status']='Error'
            try: db.close()
            except Exception: pass
            refresh_table(); update_ocr_button()
            details = f"Nuevos: {saved}\nDuplicados: {skipped}"
            if invalid:
                details += f"\nInválidos (sin DNI/LM): {invalid}"
            dlg=ft.AlertDialog(title=ft.Text("Resultado de guardado"), content=ft.Text(details),
                               actions=[ft.FilledButton("Cerrar", on_click=lambda e: page.close(dlg))])
            page.open(dlg)
        finally:
            await asyncio.sleep(0)

    def save_to_db(_=None):
        targets=[i for i,it in enumerate(files) if it.get('selected')] or ([selected_index] if selected_index is not None else [])
        if not targets:
            dlg = ft.AlertDialog(title=ft.Text("Advertencia"), content=ft.Text("No hay imágenes seleccionadas para guardar en la base de datos."), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))], modal=True)
            page.open(dlg)
            return
        with_data=[i for i in targets if files[i].get('result')]
        if not with_data:
            dlg = ft.AlertDialog(title=ft.Text("Advertencia"), content=ft.Text("No hay datos extraídos para guardar en la base de datos."), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))], modal=True)
            page.open(dlg)
            return
        validated=[i for i in with_data if files[i].get('status')=='Validado']
        pending=[i for i in with_data if files[i].get('status')!='Validado']
        if validated:
            page.run_task(_save_indices, validated)
        if pending:
            def confirm(e): page.close(confirm_dlg); page.run_task(_save_indices, pending)
            def cancel(e): page.close(confirm_dlg)
            confirm_dlg=ft.AlertDialog(title=ft.Text("Archivos sin validar"), content=ft.Text(f"Se guardarán {len(pending)} sin validar. ¿Continuar?"),
                                       actions=[ft.TextButton("Cancelar", on_click=cancel), ft.FilledButton("Guardar", on_click=confirm)])
            page.open(confirm_dlg)

    def clear_all():
        nonlocal files, selected_index, last_result
        if not files:
            dlg = ft.AlertDialog(title=ft.Text("Advertencia"), content=ft.Text("No hay archivos cargados para limpiar."), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))], modal=True)
            page.open(dlg)
            return
        files.clear(); selected_index=None; last_result=None; clear_form(); refresh_table(); update_ocr_button()

    # --- Campos formulario ---
    tf_dni=ft.TextField(label="DNI (11 dígitos)",width=260); tf_lm=ft.TextField(label="LM",width=200); tf_or=ft.TextField(label="OR",width=200)
    tf_clase=ft.TextField(label="Clase",width=200); tf_libro=ft.TextField(label="Libro",width=200); tf_folio=ft.TextField(label="Folio",width=200)
    tf_apellidos=ft.TextField(label="Apellidos",width=400); tf_nombres=ft.TextField(label="Nombres",width=400)
    tf_fn=ft.TextField(label="Fecha Nac. (DD/MM/AAAA)",width=260)
    dd_presto=ft.Dropdown(label="¿Prestó servicio?",options=[ft.dropdown.Option("NO"),ft.dropdown.Option("SI")],value="NO",width=220)
    tf_gran=ft.TextField(label="Gran Unidad",width=260); tf_unialta=ft.TextField(label="Unidad Alta",width=260); tf_unibaja=ft.TextField(label="Unidad Baja",width=260)
    tf_falta=ft.TextField(label="Fecha Alta",width=220); tf_fbaja=ft.TextField(label="Fecha Baja",width=220); tf_grado=ft.TextField(label="Grado",width=220)
    tf_motivo=ft.TextField(label="Motivo de Baja",width=600)

    current_title=ft.Text("Sin archivo", size=18, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE)
    current_meta=ft.Text("Seleccione un archivo para comenzar", size=14, color=Colors.ON_SURFACE_VARIANT)
    detailed_info_container=ft.Container(content=ft.Text("📊 Info aparecerá al seleccionar", size=12, color=Colors.ON_SURFACE_VARIANT, italic=True))
    file_info_panel=ft.Container(content=ft.Column([
        ft.Row([ft.Icon(ft.Icons.IMAGE,color=Colors.PRIMARY,size=20), current_title],spacing=8),
        current_meta, ft.Divider(height=1,color=Colors.BORDER), detailed_info_container
    ],spacing=8), padding=16, bgcolor=Colors.SURFACE_VARIANT, border_radius=12, border=ft.border.all(1,Colors.BORDER), margin=ft.margin.only(bottom=16))

    files_list=ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

    # --- Botones ---
    btn_pick=create_button("Cargar Imágenes", ft.Icons.UPLOAD_FILE, "filled", lambda e: fp.pick_files(allow_multiple=True))
    btn_ocr=create_button("Procesar OCR", ft.Icons.SMART_TOY, "filled", lambda e: run_ocr_single(), Colors.SECONDARY)
    btn_ocr_batch=create_button("OCR Todo", ft.Icons.AUTO_AWESOME, "outlined", lambda e: run_ocr_batch(), Colors.SECONDARY)
    btn_clear=create_button("Limpiar Todo", ft.Icons.CLEAR_ALL, "outlined", lambda e: clear_all(), Colors.WARNING)
    btn_apply=create_button("Aplicar Cambios", ft.Icons.CHECK_CIRCLE, "filled", lambda e: apply_changes())
    btn_mark=create_button("Marcar Validado", ft.Icons.VERIFIED, "outlined", lambda e: mark_validated(), Colors.SUCCESS)
    btn_save=create_button("Guardar en BD", ft.Icons.SAVE, "filled", save_to_db, Colors.SECONDARY)

    # --- Layout ---
    left_panel=create_card(ft.Column([
        ft.Row([btn_pick, btn_ocr, btn_ocr_batch, btn_clear], spacing=8, wrap=True),
        ft.Container(files_list, expand=True)
    ],spacing=16,expand=True),"Archivos de Imagen",16)
    form_content=ft.Column([
        file_info_panel,
        ft.Text("📋 Identificación", size=16, weight=ft.FontWeight.BOLD), ft.Row([tf_dni, tf_lm], wrap=True, spacing=12), ft.Row([tf_or], wrap=True),
        ft.Text("📄 Documento", size=16, weight=ft.FontWeight.BOLD), ft.Row([tf_clase, tf_libro], wrap=True, spacing=12), ft.Row([tf_folio], wrap=True),
        ft.Text("👤 Datos Personales", size=16, weight=ft.FontWeight.BOLD), ft.Row([tf_apellidos], wrap=True), ft.Row([tf_nombres], wrap=True),
        ft.Row([tf_fn, dd_presto], wrap=True, spacing=12),
        ft.Text("⚔️ Servicio Militar", size=16, weight=ft.FontWeight.BOLD), ft.Row([tf_gran], wrap=True), ft.Row([tf_unialta, tf_unibaja], wrap=True),
        ft.Row([tf_falta, tf_fbaja], wrap=True), ft.Row([tf_grado], wrap=True), tf_motivo,
        ft.Divider(), ft.Row([btn_apply, btn_mark], spacing=12, wrap=True), ft.Row([btn_save], spacing=12, wrap=True)
    ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    right_panel=create_card(form_content, "Datos Extraídos", 20)

    main_content=ft.ResponsiveRow([
        ft.Container(content=left_panel, col={"xs":12,"sm":12,"md":5,"lg":4,"xl":4}, padding=ft.padding.only(right=8)),
        ft.Container(content=right_panel, col={"xs":12,"sm":12,"md":7,"lg":8,"xl":8}, padding=ft.padding.only(left=8)),
    ], expand=True, spacing=0)
    header=ft.Container(content=ft.Row([ft.Icon(ft.Icons.IMAGE,size=28,color=Colors.PRIMARY), ft.Text("Digitalización de Imágenes", size=20, weight=ft.FontWeight.BOLD)],spacing=10), padding=ft.padding.only(bottom=12))
    root=ft.Container(content=ft.Column([header, ft.Container(main_content, expand=True)], expand=True, spacing=0), padding=ft.padding.symmetric(horizontal=16, vertical=12), expand=True, bgcolor=Colors.SURFACE)

    def cleanup(): unregister_guard("digitalizacion_jpg")
    root.cleanup=cleanup
    return root


    def show_processing_warning():
        """Muestra modal si hay archivos siendo procesados"""
        processing_files = [f for f in files if f.get("status") == "Procesando"]
        if not processing_files:
            return False
            
        def close_modal(e):
            page.close(processing_modal)
            
        processing_modal = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.HOURGLASS_EMPTY, color=Colors.WARNING),
                ft.Text("Procesamiento en curso", weight=ft.FontWeight.BOLD)
            ], spacing=8),
            content=ft.Column([
                ft.Text(
                    f"Hay {len(processing_files)} archivo(s) siendo procesados con OCR:",
                    size=14
                ),
                ft.Container(height=8),
                *[ft.Text(f"• {f['name']}", size=12, color=Colors.ON_SURFACE_VARIANT) 
                  for f in processing_files[:3]],  # Mostrar max 3
                ft.Text("Por favor espera a que termine el procesamiento antes de salir.", 
                       size=14, weight=ft.FontWeight.W_500),
            ], tight=True),
            actions=[
                ft.TextButton("Entendido", on_click=close_modal)
            ],
            modal=True
        )
        
        page.open(processing_modal)
        return True

    # Registrar guardia cuando se monta el componente
    register_guard("digitalizacion_jpg", has_pending_work)

    # ---------- Sistema de Logging mejorado ----------
    log = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def log_add(msg: str, level="info"):
        """Añade un mensaje al log con iconos y colores según el nivel - DESHABILITADO"""
        pass  # Log deshabilitado para mejorar rendimiento

    # ---------- Previsualizador de imágenes ----------
    
    def show_in_folder(file_path):
        """Abre la carpeta que contiene el archivo"""
        try:
            import subprocess
            import os
            
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', '/select,', file_path])
            elif os.name == 'posix':  # macOS y Linux
                subprocess.run(['open', '-R', file_path])
            else:
                # Fallback: abrir carpeta parent
                folder_path = os.path.dirname(file_path)
                subprocess.run(['xdg-open', folder_path])
                
            log_add(f"📂 Carpeta abierta para: {os.path.basename(file_path)}")
        except Exception as e:
            log_add(f"❌ No se pudo abrir carpeta: {e}")
    
    def open_image_viewer():
        """Visor simple sin controles de zoom (zoom eliminado según requerimiento)."""
        try:
            # Verificar si hay archivos cargados
            if not files:
                log_add("❌ No has cargado ninguna imagen")
                page.open(ft.AlertDialog(
                    title=ft.Text("Sin imágenes"),
                    content=ft.Text("No has subido ninguna imagen.\n\nPor favor usa el botón 'Cargar Imágenes' primero."),
                    actions=[ft.TextButton("OK", on_click=lambda e: page.close(e.control.parent))]
                ))
                return
                
            # Verificar si hay archivo seleccionado
            if selected_index is None or selected_index >= len(files):
                log_add("❌ No hay imagen seleccionada de la lista")
                page.open(ft.AlertDialog(
                    title=ft.Text("Sin selección"),
                    content=ft.Text("Por favor selecciona una imagen de la lista haciendo clic en ella."),
                    actions=[ft.TextButton("OK", on_click=lambda e: page.close(e.control.parent))]
                ))
                return
                
            file_item = files[selected_index]
            file_path = file_item["path"]
            
            # Verificar si existe el archivo
            if not os.path.exists(file_path):
                log_add(f"❌ Archivo no encontrado: {file_path}")
                page.open(ft.AlertDialog(
                    title=ft.Text("Archivo no encontrado"),
                    content=ft.Text(f"No se puede encontrar el archivo:\n{file_item['name']}\n\nRuta: {file_path}"),
                    actions=[ft.TextButton("OK", on_click=lambda e: page.close(e.control.parent))]
                ))
                return
                
            def cerrar_modal(e):
                page.close(image_dialog)
                log_add("🔒 Visor de imagen cerrado")
            
            # Modal con zoom avanzado
            image_dialog = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.IMAGE, color=Colors.PRIMARY, size=20),
                    ft.Text(f"📸 {file_item['name']}", weight=ft.FontWeight.BOLD, size=14, expand=True),
                    ft.Text(f"({selected_index + 1}/{len(files)})", size=11, color=Colors.ON_SURFACE_VARIANT)
                ], spacing=6),
                content=ft.Container(
                    content=ft.Image(
                        src=file_path,
                        width=600,
                        height=450,
                        fit=ft.ImageFit.CONTAIN,
                        error_content=ft.Container(
                            content=ft.Column([
                                ft.Icon(ft.Icons.ERROR, size=48, color=Colors.DANGER),
                                ft.Text("❌ Error al cargar imagen", color=Colors.DANGER)
                            ], alignment=ft.MainAxisAlignment.CENTER),
                            alignment=ft.alignment.center
                        )
                    ),
                    width=620,
                    height=470,
                    alignment=ft.alignment.center
                ),
                actions=[
                    ft.Row([
                        ft.TextButton("📂 Carpeta", icon=ft.Icons.FOLDER_OPEN, on_click=lambda e: show_in_folder(file_path)),
                        ft.FilledButton("Cerrar", icon=ft.Icons.CLOSE, on_click=cerrar_modal)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ],
                modal=True,
                on_dismiss=cerrar_modal
            )
            
            page.open(image_dialog)
            log_add(f"🖼️ Imagen abierta con zoom: {file_item['name']}")
            
        except Exception as e:
            log_add(f"❌ Error al abrir imagen: {e}")

    def update_preview(file_path=None):
        """Actualiza la previsualización de la imagen"""
        try:
            if not file_path:
                # Mostrar placeholder
                preview_container.current.content = ft.Column([
                    ft.Icon(ft.Icons.IMAGE, size=64, color=Colors.ON_SURFACE_VARIANT),
                    ft.Text("Sin imagen seleccionada", 
                           text_align=ft.TextAlign.CENTER, color=Colors.ON_SURFACE_VARIANT, size=14),
                    ft.Text("Selecciona un archivo de la lista", 
                           text_align=ft.TextAlign.CENTER, color=Colors.ON_SURFACE_VARIANT, size=12)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                preview_container.current.update()
                return

            if not os.path.exists(file_path):
                # Archivo no encontrado
                preview_container.current.content = ft.Column([
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=64, color=Colors.DANGER),
                    ft.Text("Archivo no encontrado", 
                           text_align=ft.TextAlign.CENTER, color=Colors.DANGER, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Ruta: {file_path}", 
                           text_align=ft.TextAlign.CENTER, color=Colors.ON_SURFACE_VARIANT, size=10)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                preview_container.current.update()
                log_add(f"❌ Archivo no encontrado: {file_path}")
                return

            # Verificar que el archivo es realmente una imagen
            valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
            if not file_path.lower().endswith(valid_extensions):
                preview_container.current.content = ft.Column([
                    ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED, size=64, color=Colors.WARNING),
                    ft.Text("Formato no soportado", 
                           text_align=ft.TextAlign.CENTER, color=Colors.WARNING, weight=ft.FontWeight.BOLD),
                    ft.Text("Formatos válidos: JPG, PNG, GIF, BMP, WEBP", 
                           text_align=ft.TextAlign.CENTER, color=Colors.ON_SURFACE_VARIANT, size=10)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                preview_container.current.update()
                log_add(f"❌ Formato no soportado: {os.path.basename(file_path)}")
                return

            # Para imágenes, mostrar la imagen real con más opciones
            def open_image_modal(e):
                """Abre la imagen en un modal más grande"""
                def close_modal(e):
                    page.close(modal)
                
                modal = ft.AlertDialog(
                    title=ft.Text("🖼️ Vista Completa", weight=ft.FontWeight.BOLD),
                    content=ft.Container(
                        content=ft.Image(
                            src=file_path,
                            width=700,
                            height=500,
                            fit=ft.ImageFit.CONTAIN,
                            error_content=ft.Container(
                                content=ft.Column([
                                    ft.Icon(ft.Icons.BROKEN_IMAGE, size=48, color=Colors.DANGER),
                                    ft.Text("Error al cargar imagen", color=Colors.DANGER)
                                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                alignment=ft.alignment.center,
                                height=500
                            )
                        ),
                        width=750,
                        height=550,
                        alignment=ft.alignment.center
                    ),
                    actions=[
                        ft.TextButton("Cerrar", on_click=close_modal)
                    ]
                )
                
                page.open(modal)

            # Crear la vista previa
            preview_container.current.content = ft.Column([
                ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Image(
                                src=file_path,
                                width=280,
                                height=180,
                                fit=ft.ImageFit.CONTAIN,
                                border_radius=8,
                                error_content=ft.Container(
                                    content=ft.Column([
                                        ft.Icon(ft.Icons.BROKEN_IMAGE, size=40, color=Colors.DANGER),
                                        ft.Text("Error al cargar", size=12, color=Colors.DANGER),
                                        ft.Text("imagen", size=12, color=Colors.DANGER)
                                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                                    alignment=ft.alignment.center,
                                    height=180,
                                    bgcolor=Colors.ERROR_CONTAINER,
                                    border_radius=8
                                )
                            ),
                            bgcolor=Colors.WHITE,
                            border_radius=8,
                            padding=8
                        ),
               ft.Text("Clic para ver", 
                   size=11, color=Colors.PRIMARY, italic=True, text_align=ft.TextAlign.CENTER)
                    ], spacing=8),
                    border=ft.border.all(2, Colors.PRIMARY),
                    border_radius=12,
                    bgcolor=Colors.SURFACE,
                    padding=12,
                    on_click=lambda e: open_image_viewer(),
                    tooltip="Clic para ver en grande",
                    ink=True
                ),
                ft.Container(height=8),
                ft.Column([
                    ft.Text(os.path.basename(file_path), 
                           weight=ft.FontWeight.BOLD, 
                           text_align=ft.TextAlign.CENTER,
                           max_lines=2,
                           size=13,
                           color=Colors.ON_SURFACE,
                           overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"📁 {os.path.getsize(file_path) / 1024:.1f} KB", 
                           size=12, color=Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                ft.Divider(color=Colors.BORDER, height=1),
                ft.Column([
                    create_button("�️ Ver", ft.Icons.VISIBILITY, "filled", 
                                lambda _: open_image_viewer()),
                    create_button("📂 Abrir Carpeta", ft.Icons.FOLDER_OPEN, "outlined", 
                                lambda _: show_in_folder(file_path)),
                    create_button("📋 Copiar Ruta", ft.Icons.COPY, "text", 
                                lambda _: copy_to_clipboard(file_path))
                ], spacing=8)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
            
            log_add(f"✅ Vista previa cargada: {os.path.basename(file_path)}")
            
        except Exception as e:
            log_add(f"❌ Error en vista previa: {e}")
            preview_container.current.content = ft.Column([
                ft.Icon(ft.Icons.ERROR, size=64, color=Colors.DANGER),
                ft.Text("Error inesperado", color=Colors.DANGER, weight=ft.FontWeight.BOLD, size=16),
                ft.Text(f"Archivo: {os.path.basename(file_path) if file_path else 'N/A'}", 
                       size=12, color=Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ft.Text(f"Error: {str(e)}", size=10, color=Colors.DANGER, text_align=ft.TextAlign.CENTER),
                ft.Text("Intenta cargar otra imagen", size=10, color=Colors.ON_SURFACE_VARIANT, italic=True)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
        
        finally:
            preview_container.current.update()

    def copy_to_clipboard(text):
        """Copia texto al portapapeles"""
        try:
            page.set_clipboard(text)
            # log_add("Ruta copiada al portapapeles", "success")
        except Exception as e:
            # log_add(f"Error al copiar: {e}", "error")
            pass

    def show_in_folder(file_path):
        """Muestra el archivo en el explorador de archivos"""
        try:
            import subprocess
            subprocess.run(f'explorer /select,"{os.path.abspath(file_path)}"', shell=True)
            log_add("Archivo mostrado en explorador", "success")
        except Exception as e:
            log_add(f"Error al abrir explorador: {e}", "error")

    # ---------- UI básicos mejorados ----------
    current_title = ft.Text("Sin archivo seleccionado", 
                           size=18, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE)
    current_meta = ft.Text("Selecciona una imagen de la lista para comenzar", 
                          size=14, color=Colors.ON_SURFACE_VARIANT)
    
    # Panel de información detallada del archivo seleccionado
    detailed_info_container = ft.Container(
        content=ft.Text("📊 Información detallada aparecerá al seleccionar un archivo", 
                       size=12, color=Colors.ON_SURFACE_VARIANT, italic=True)
    )
    
    file_info_panel = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.IMAGE, size=20, color=Colors.PRIMARY),
                current_title
            ], spacing=8),
            current_meta,
            ft.Divider(height=1, color=Colors.BORDER),
            detailed_info_container
        ], spacing=8),
        padding=16,
        bgcolor=Colors.SURFACE_VARIANT,
        border_radius=12,
        border=ft.border.all(1, Colors.BORDER),
        margin=ft.margin.only(bottom=16)
    )
    
    files_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

    def refresh_table():
        """Actualiza la lista de archivos con diseño mejorado"""
        files_list.controls.clear()
        
        if not files:
            files_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.UPLOAD_FILE, size=48, color=Colors.ON_SURFACE_VARIANT),
                        ft.Text("No hay imágenes cargadas", color=Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.BOLD),
                        ft.Text("Usa el botón 'Cargar Imágenes' para comenzar", 
                               size=12, color=Colors.ON_SURFACE_VARIANT)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    padding=40,
                    alignment=ft.alignment.center,
                    bgcolor=Colors.SURFACE,
                    border_radius=8,
                    border=ft.border.all(1, Colors.BORDER)
                )
            )
            page.update()
            return

        for i, file_item in enumerate(files):
            def on_toggle_item(ch_event, idx=i):
                files[idx]["selected"] = ch_event.control.value

            def on_select(e, idx=i):
                # Hacer más visible la selección y actualizar información
                select_file(idx)
                # Refrescar tabla para mostrar selección visual
                refresh_table()
                # Forzar actualización completa de la interfaz
                page.update()

            def on_remove(e, idx=i):
                remove_file(idx)

            def on_view_image(e, idx=i):
                """Visor simple sin zoom (zoom eliminado)."""
                file_item = files[idx]
                file_path = file_item["path"]
                if not os.path.exists(file_path):
                    page.open(ft.AlertDialog(title=ft.Text("Archivo no encontrado"), content=ft.Text(file_path), actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))]))
                    return
                def close_modal(e):
                    page.close(modal)
                modal = ft.AlertDialog(
                    title=ft.Row([
                        ft.Icon(ft.Icons.IMAGE, color=Colors.PRIMARY),
                        ft.Text(file_item['name'], expand=True, weight=ft.FontWeight.BOLD),
                        ft.Text(f"({idx + 1}/{len(files)})", color=Colors.ON_SURFACE_VARIANT)
                    ], spacing=8),
                    content=ft.Container(
                        content=ft.Image(src=file_path, width=600, height=450, fit=ft.ImageFit.CONTAIN,
                                         error_content=ft.Container(content=ft.Column([
                                             ft.Icon(ft.Icons.ERROR, size=48, color=Colors.DANGER),
                                             ft.Text("Error al cargar imagen", color=Colors.DANGER)
                                         ], alignment=ft.MainAxisAlignment.CENTER), alignment=ft.alignment.center)),
                        width=620, height=470, alignment=ft.alignment.center
                    ),
                    actions=[ft.FilledButton("Cerrar", icon=ft.Icons.CLOSE, on_click=close_modal)],
                    modal=True,
                    on_dismiss=close_modal
                )
                page.open(modal)
                log_add(f"👁️ Viendo: {file_item['name']}")

            # Crear la tarjeta de archivo
            is_selected = i == selected_index
            status = file_item.get("status", "Pendiente")
            
            # Icono según el tipo de imagen
            icon = ft.Icons.IMAGE
            if file_item.get("mime", "").lower().endswith("jpeg") or file_item.get("name", "").lower().endswith((".jpg", ".jpeg")):
                icon = ft.Icons.PHOTO
            elif file_item.get("name", "").lower().endswith(".png"):
                icon = ft.Icons.PHOTO_LIBRARY
            
            # Color de fondo más visible para selección y estados - Paleta coherente VERDE
            if status == "Procesando":
                card_bgcolor = "#ECFDF5"  # Verde claro coherente con el sistema
                border_color = "#059669"  # Verde del sistema
                border_width = 2
            elif is_selected:
                card_bgcolor = Colors.SURFACE_VARIANT
                border_color = Colors.PRIMARY
                border_width = 2
            elif status == "Procesado":
                card_bgcolor = "#ECFDF5"  # Verde muy claro y sutil
                border_color = "#10B981"  # Verde moderno
                border_width = 1
            elif status == "Validado":
                card_bgcolor = "#DCFCE7"  # Verde validado claro
                border_color = "#059669"  # Verde más fuerte
                border_width = 1
            elif status == "Pendiente":
                card_bgcolor = "#F9FAFB"  # Gris muy claro y profesional
                border_color = "#7C3AED"  # Violeta suave
                border_width = 1
            elif status == "Editado":
                card_bgcolor = "#F5F3FF"  # Violeta muy claro
                border_color = "#8B5CF6"  # Violeta
                border_width = 1
            elif status == "Error":
                card_bgcolor = "#FEF2F2"  # Rojo muy suave solo para errores reales
                border_color = "#DC2626"  # Rojo suave
                border_width = 1
            else:
                card_bgcolor = Colors.WHITE
                border_color = Colors.BORDER
                border_width = 1
                
            file_card = ft.Container(
                content=ft.Row([
                    # Checkbox más compacto con indicador de validación
                    ft.Container(
                        content=ft.Row([
                            ft.Checkbox(
                                value=file_item.get("selected", False), 
                                on_change=on_toggle_item,
                                active_color=Colors.PRIMARY,
                                scale=0.8  # Más pequeño
                            ),
                            # Indicador de validación al lado
                            ft.Icon(
                                ft.Icons.VERIFIED,
                                size=10,
                                color=Colors.SUCCESS
                            ) if status == "Validado" else ft.Container(width=0, height=0)
                        ], spacing=0, tight=True),
                        width=28,  # Reducido
                        alignment=ft.alignment.center
                    ),
                    
                    # Icono del archivo más pequeño
                    ft.Container(
                        content=ft.Icon(icon, color=Colors.PRIMARY if is_selected else Colors.ON_SURFACE_VARIANT, size=16),  # Reducido
                        width=24,  # Reducido
                        alignment=ft.alignment.center
                    ),
                    
                    # Información del archivo más compacta
                    ft.Container(
                        content=ft.Column([
                            ft.Text(file_item["name"], 
                                   weight=ft.FontWeight.BOLD if is_selected else ft.FontWeight.W_500, 
                                   max_lines=1, 
                                   overflow=ft.TextOverflow.ELLIPSIS,
                                   color=Colors.PRIMARY_DARK if is_selected else Colors.ON_SURFACE,
                                   size=11),  # Reducido
                            ft.Text(f"{round((file_item.get('size') or 0) / 1024, 1)} KB", 
                                   size=9,  # Reducido
                                   color=Colors.PRIMARY if is_selected else Colors.ON_SURFACE_VARIANT)
                        ], spacing=0),  # Sin espaciado
                        expand=True
                    ),
                    
                    # Estado más compacto
                    ft.Container(
                        content=ft.Row([
                            create_status_chip(status) if status != "Procesando" else ft.Container(
                                content=ft.Row([
                                    ft.ProgressRing(width=14, height=14, stroke_width=2, color="#059669"),  # Verde del sistema
                                    ft.Text("OCR", size=9, color="#059669", weight=ft.FontWeight.W_600)  # Verde del sistema
                                ], spacing=3, tight=True),
                                bgcolor="#ECFDF5",  # Fondo verde claro del sistema
                                padding=ft.padding.symmetric(horizontal=6, vertical=3),
                                border_radius=12,
                                border=ft.border.all(1, "#05966930")  # Borde verde sutil
                            ),
                        ], spacing=4),
                        width=120  # Más ancho para texto completo
                    ),
                    
                    # Botones más pequeños
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY,
                            tooltip="Ver",
                            on_click=on_view_image,
                            icon_color=Colors.PRIMARY,
                            style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=4)  # Reducido
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Eliminar",
                            on_click=on_remove,
                            icon_color=Colors.DANGER,
                            style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=4)  # Reducido
                        )
                    ], spacing=0)  # Sin espaciado
                ], 
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4),  # Reducido
                
                padding=6,  # Reducido
                margin=ft.margin.only(bottom=2),  # Reducido
                bgcolor=card_bgcolor,
                border_radius=8,  # Reducido
                border=ft.border.all(border_width, border_color),
                on_click=on_select,
                ink=True,
                shadow=ft.BoxShadow(
                    spread_radius=1 if status == "Procesando" else 0,
                    blur_radius=4 if status == "Procesando" else (2 if is_selected else 1),
                    color=Colors.WARNING + "40" if status == "Procesando" else 
                          ("#15000000" if is_selected else "#08000000"),  # Sombras más suaves
                    offset=ft.Offset(0, 2 if status == "Procesando" else (1 if is_selected else 0.5))
                )
            )
            
            files_list.controls.append(file_card)
        
        page.update()

    def remove_file(idx: int):
        """Elimina un archivo de la lista"""
        nonlocal files, selected_index, last_result
        if 0 <= idx < len(files):
            removed_file = files.pop(idx)
            log_add(f"Archivo eliminado: {removed_file['name']}", "warning")
            
            # Ajustar índice seleccionado
            async def _save_indices(indices: list[int]):
                """Versión async para usar con page.run_task: guarda registros y muestra resumen."""
                try:
                    sess_gen = get_db()
                    try:
                        db_sess = next(sess_gen)  # type: ignore
                    except StopIteration:
                        db_sess = None
                    if db_sess is None:
                        log_add("� No se pudo crear sesión de base de datos.")
                        return
                    from database.models import Documento, Usuario
                    from sqlalchemy import select
                    try:
                        username = (user_data or {}).get("username")
                        if username:
                            user_row = db_sess.execute(select(Usuario).where(Usuario.nombre_usuario == username)).scalar_one_or_none()
                            user_id = getattr(user_row, "id_usuario", 1) if user_row else 1
                        else:
                            user_id = 1
                    except Exception:
                        user_id = 1
                    saved = 0
                    skipped = 0
                    for idx in indices:
                        if idx >= len(files):
                            continue
                        it = files[idx]
                        result = it.get("result") or {}
                        if not result:
                            log_add(f"⚠️ {it['name']} sin datos OCR, omitido.")
                            continue
                        file_info = {"name": it["name"], "path": it["path"]}
                        try:
                            existing = db_sess.execute(select(Documento).where(Documento.ruta_almacenamiento == file_info["path"])).scalar_one_or_none()
                        except Exception:
                            existing = None
                        if existing:
                            it["status"] = "Guardado"  # Consideramos duplicado como ya guardado
                            skipped += 1
                            log_add(f"ℹ️ Duplicado omitido: {it['name']}")
                            continue
                        try:
                            ids_map = create_full_digital_record(db_sess, result, file_info, user_id)
                            it["status"] = "Guardado"; it["db_ids"] = ids_map; saved += 1
                            log_add(f"💾 Guardado: {it['name']}")
                        except Exception as ex:
                            it["status"] = "Error"; log_add(f"🚨 Error al guardar {it['name']}: {ex}")
                    try:
                        db_sess.close()
                    except Exception:
                        pass
                    refresh_table(); update_ocr_button()
                    summary_modal = ft.AlertDialog(
                        title=ft.Row([
                            ft.Icon(ft.Icons.SAVE, color=Colors.PRIMARY),
                            ft.Text("Resultado de guardado", weight=ft.FontWeight.BOLD)
                        ], spacing=8),
                        content=ft.Column([
                            ft.Text(f"Nuevos guardados: {saved}"),
                            ft.Text(f"Duplicados (omitidos): {skipped}"),
                            ft.Text(f"Errores: {len([f for f in files if f.get('status')=='Error'])}"),
                        ], spacing=4),
                        actions=[ft.FilledButton("Cerrar", on_click=lambda e: page.close(summary_modal))]
                    )
                    page.open(summary_modal)
                finally:
                    await asyncio.sleep(0)
                ft.Divider(height=1, color=Colors.BORDER),
                ft.Row([
                    ft.Icon(ft.Icons.SMART_TOY, size=16, color=Colors.SUCCESS),
                    ft.Text("Resultado OCR", weight=ft.FontWeight.BOLD, size=12)
                ], spacing=4),
                ft.Row([
                    ft.Text("🆔 DNI:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                    ft.Text(result.get('dni', 'No detectado'), size=11, color=Colors.ON_SURFACE_VARIANT)
                ]),
                ft.Row([
                    ft.Text("👤 Apellidos:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                    ft.Text(result.get('apellidos', 'No detectado')[:25] + ('...' if len(result.get('apellidos', '')) > 25 else ''), 
                           size=11, color=Colors.ON_SURFACE_VARIANT)
                ]),
                ft.Row([
                    ft.Text("👤 Nombres:", size=11, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
                    ft.Text(result.get('nombres', 'No detectado')[:25] + ('...' if len(result.get('nombres', '')) > 25 else ''), 
                           size=11, color=Colors.ON_SURFACE_VARIANT)
                ])
        
        
        # Actualizar el contenedor de información detallada
        detailed_info_container.content = detailed_info_content
        
        # Actualizar formulario con los datos del archivo seleccionado
        if file_item.get("result"):
            last_result = file_item["result"]
            fill_form(last_result)
            log_add(f"📝 Datos cargados en formulario")
        else:
            clear_form()
            last_result = None
            log_add(f"🆕 Formulario limpio - sin datos OCR")
            
        # Refrescar tabla SOLO una vez y actualizar interfaz
        update_ocr_button()
        page.update()

    # -------- Formulario --------
    tf_dni       = ft.TextField(label="DNI (11 dígitos)", width=260)
    tf_lm        = ft.TextField(label="LM", width=200)
    tf_or        = ft.TextField(label="OR (DDD[L])", width=200)
    tf_clase     = ft.TextField(label="Clase (4)", width=200)
    tf_libro     = ft.TextField(label="Libro", width=200)
    tf_folio     = ft.TextField(label="Folio", width=200)
    tf_apellidos = ft.TextField(label="Apellidos", width=400)
    tf_nombres   = ft.TextField(label="Nombres", width=400)
    tf_fn        = ft.TextField(label="Fecha Nac. (DD/MM/AAAA)", width=260)
    dd_presto    = ft.Dropdown(
        label="¿Prestó servicio?",
        options=[ft.dropdown.Option("NO"), ft.dropdown.Option("SI")],
        value="NO",
        width=220,
    )
    tf_gran      = ft.TextField(label="Gran Unidad", width=260)
    tf_unialta   = ft.TextField(label="Unidad Alta", width=260)
    tf_unibaja   = ft.TextField(label="Unidad Baja", width=260)
    tf_falta     = ft.TextField(label="Fecha Alta", width=220)
    tf_fbaja     = ft.TextField(label="Fecha Baja", width=220)
    tf_grado     = ft.TextField(label="Grado", width=220)
    tf_motivo    = ft.TextField(label="Motivo de Baja", width=600)

    def clear_form():
        """Limpia todos los campos del formulario"""
        for field in [tf_dni, tf_lm, tf_or, tf_clase, tf_libro, tf_folio, 
                     tf_apellidos, tf_nombres, tf_fn, tf_gran, tf_unialta, 
                     tf_unibaja, tf_falta, tf_fbaja, tf_grado, tf_motivo]:
            field.value = ""
        dd_presto.value = "NO"
        page.update()

    def fill_form(d: dict):
        # helper para aceptar claves alternativas sin tocar tu OCR
        def pick(*keys, default=""):
            for k in keys:
                v = d.get(k)
                if v not in (None, "", [], {}):
                    return v
            return default

        tf_dni.value        = pick("dni")
        tf_lm.value         = pick("lm", "dni_o_lm")
        tf_or.value         = pick("or")
        tf_clase.value      = pick("clase")
        tf_libro.value      = pick("libro")
        tf_folio.value      = pick("folio")
        tf_apellidos.value  = pick("apellidos")
        tf_nombres.value    = pick("nombres")
        tf_fn.value         = pick("fecha_nacimiento")

        ps = (pick("presto_servicio", default="NO") or "NO").strip().upper()
        dd_presto.value     = "SI" if ps == "SI" else "NO"

        tf_gran.value       = pick("gran_unidad")
        tf_unialta.value    = pick("unidad_alta")
        tf_unibaja.value    = pick("unidad_baja")
        tf_falta.value      = pick("fecha_alta")
        tf_fbaja.value      = pick("fecha_baja")
        tf_grado.value      = pick("grado")
        tf_motivo.value     = pick("motivo_baja")
        page.update()

    # -------- JSON Modal --------
    json_dialog = ft.AlertDialog(modal=True)

    def show_json_modal(obj: dict):
        txt = json.dumps(obj or {}, ensure_ascii=False, indent=2)
        json_dialog.title = ft.Text("Resultado JSON")
        json_dialog.content = ft.Container(content=ft.Text(txt, selectable=True, size=13), width=680, height=420, padding=10)
        json_dialog.actions = [ft.TextButton("Cerrar", on_click=lambda e: setattr(json_dialog, "open", False))]
        json_dialog.open = True
        page.dialog = json_dialog
        page.update()

    # -------- Picker --------
    fp = ft.FilePicker(on_result=lambda e: on_pick(e))
    page.overlay.append(fp)

    def guess_mime(path: str) -> str:
        ext = os.path.splitext(path.lower())[1]
        return {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png"
        }.get(ext, "application/octet-stream")

    def on_pick(e: ft.FilePickerResultEvent):
        nonlocal selected_index
        if not e or not e.files:
            return
        for f in e.files:
            path = f.path or f.name
            mime = guess_mime(path)
            if not mime.startswith("image/"):  # ignora NO-imagen
                continue
            size = getattr(f, "size", None)
            if size is None and os.path.exists(path):
                try:
                    size = os.path.getsize(path)
                except Exception:
                    size = 0
            files.append({"name": f.name, "path": path, "mime": mime, "size": size or 0, "status": "Pendiente"})
        if not files:
            log_add("No se seleccionaron imágenes válidas.")
            return
        selected_index = len(files) - 1
        refresh_table()
        select_file(selected_index)

    # -------- Selección --------
    def select_file(idx: int):
        nonlocal selected_index
        selected_index = idx
        it = files[idx]
        current_title.value = f"Editando: {it['name']}"
        size_kb = round((it.get('size') or 0) / 1024, 1)
        current_meta.value  = f"{it['mime']} • {size_kb} KB • {it.get('status','Pendiente')}"
        page.update()

    # -------- Acciones --------
    def run_ocr_jpg():
        nonlocal last_result
        
        # Verificar si hay archivos en procesamiento
        if any(f.get("status") == "Procesando" for f in files):
            show_processing_warning()
            return
            
        if selected_index is None:
            log_add("Seleccione una imagen de la lista.")
            return
            
        it = files[selected_index]
        if not it["mime"].startswith("image/"):
            log_add("⚠️ El archivo seleccionado no es imagen.")
            return
            
        path = it["path"]
        if not os.path.exists(path):
            log_add(f"❌ Ruta no existe: {path}")
            it["status"] = "Error"
            refresh_table()
            return
            
        try:
            # Cambiar estado a procesando
            it["status"] = "Procesando"
            refresh_table()
            update_ocr_button()
            log_add(f"🔄 Iniciando OCR para: {it['name']}")
            page.update()
            
            # Procesar OCR
            data = extract_image(path)  # 👈 llama a tu jpg.py
            
            # Verificar si hay errores de conectividad
            if isinstance(data, dict) and data.get("error"):
                error_type = data.get("error")
                error_msg = data.get("mensaje", "Error desconocido")
                
                if error_type == "sin_conexion":
                    log_add(f"🌐 Sin conexión: {it['name']}")
                    it["status"] = "Error"
                    # Modal específico para errores de conectividad
                    connectivity_modal = ft.AlertDialog(
                        title=ft.Row([
                            ft.Icon(ft.Icons.WIFI_OFF, color=Colors.WARNING, size=24),
                            ft.Text("Sin Conexión a Internet")
                        ], spacing=8),
                        content=ft.Column([
                            ft.Text("No se puede conectar a Vertex AI:", weight=ft.FontWeight.BOLD),
                            ft.Text("• Verifica tu conexión a internet"),
                            ft.Text("• Revisa configuración de proxy/firewall"),
                            ft.Text("• Intenta nuevamente en unos minutos"),
                            ft.Divider(),
                            ft.Text(f"Archivo: {it['name']}", size=12, color=Colors.ON_SURFACE_VARIANT)
                        ], spacing=4, tight=True),
                        actions=[
                            ft.TextButton("Reintentar", on_click=lambda e: [page.close(connectivity_modal), run_ocr_jpg()]),
                            ft.FilledButton("Cerrar", on_click=lambda e: page.close(connectivity_modal))
                        ]
                    )
                    page.open(connectivity_modal)
                else:
                    log_add(f"❌ Error en {it['name']}: {error_msg}")
                    it["status"] = "Error"
                    error_modal = ft.AlertDialog(
                        title=ft.Text("Error en OCR"),
                        content=ft.Text(error_msg),
                        actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(error_modal))]
                    )
                    page.open(error_modal)
                    
                refresh_table()
                update_ocr_button()
                return
            
            last_result = data or {}
            
            # Actualizar UI con resultados
            fill_form(last_result)
            it["status"] = "Procesado"
            it["result"] = last_result  # Guardar resultado
            refresh_table()
            update_ocr_button()
            log_add(f"✅ OCR completado: {it['name']}")
            
        except Exception as ex:
            it["status"] = "Error"
            refresh_table()
            update_ocr_button()
            log_add(f"❌ OCR falló: {ex}")
            # Mostrar error en modal
            error_modal = ft.AlertDialog(
                title=ft.Text("Error en OCR"),
                content=ft.Text(f"No se pudo procesar la imagen:\n{str(ex)}"),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(error_modal))]
            )
            page.open(error_modal)

    def run_ocr_batch():
        """Procesa OCR en lote para todos los archivos pendientes"""
        nonlocal last_result
        
        # Verificar si hay archivos en procesamiento
        if any(f.get("status") == "Procesando" for f in files):
            show_processing_warning()
            return
            
        # Filtrar archivos pendientes o con error
        pending_files = [i for i, f in enumerate(files) 
                        if f.get("status") in ["Pendiente", "Error"] and f["mime"].startswith("image/")]
        
        if not pending_files:
            log_add("ℹ️ No hay archivos pendientes para procesar")
            return
            
        # Confirmación para procesamiento en lote
        def confirm_batch(e):
            page.close(confirm_dialog)
            process_batch_files()
            
        def cancel_batch(e):
            page.close(confirm_dialog)
            
        confirm_dialog = ft.AlertDialog(
            title=ft.Text("🔄 Procesamiento en Lote"),
            content=ft.Text(f"¿Deseas procesar {len(pending_files)} archivos con OCR?\n\nEsto puede tomar varios minutos dependiendo del número de archivos."),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel_batch),
                ft.FilledButton("Procesar Todo", on_click=confirm_batch)
            ]
        )
        page.open(confirm_dialog)
        
        def process_batch_files():
            """Procesa todos los archivos pendientes"""
            processed_count = 0
            error_count = 0
            
            for i in pending_files:
                try:
                    file_item = files[i]
                    path = file_item["path"]
                    
                    if not os.path.exists(path):
                        log_add(f"❌ Archivo no encontrado: {file_item['name']}")
                        file_item["status"] = "Error"
                        error_count += 1
                        continue
                    
                    # Cambiar estado a procesando
                    file_item["status"] = "Procesando"
                    log_add(f"🔄 Procesando {processed_count + 1}/{len(pending_files)}: {file_item['name']}")
                    refresh_table()
                    page.update()
                    
                    # Procesar OCR
                    data = extract_image(path)
                    
                    # Verificar errores de conectividad en lote
                    if isinstance(data, dict) and data.get("error"):
                        error_type = data.get("error")
                        if error_type == "sin_conexion":
                            # Si hay error de conectividad, marcar todos los restantes como error y salir
                            log_add(f"🌐 Error de conectividad detectado. Deteniendo procesamiento en lote.")
                            for remaining_i in pending_files[pending_files.index(i):]:
                                files[remaining_i]["status"] = "Error"
                            error_count += len(pending_files) - processed_count - 1
                            
                            # Modal específico para lote sin conexión
                            connectivity_batch_modal = ft.AlertDialog(
                                title=ft.Row([
                                    ft.Icon(ft.Icons.WIFI_OFF, color=Colors.WARNING, size=24),
                                    ft.Text("Error de Conectividad en Lote")
                                ], spacing=8),
                                content=ft.Column([
                                    ft.Text(f"Se procesaron {processed_count} archivos antes del error."),
                                    ft.Text("Error de conectividad detectado:", weight=ft.FontWeight.BOLD),
                                    ft.Text("• Sin conexión a Vertex AI"),
                                    ft.Text("• Verifica tu conexión a internet"),
                                    ft.Text("• Intenta el lote nuevamente cuando tengas conexión"),
                                ], spacing=4, tight=True),
                                actions=[ft.FilledButton("Entendido", on_click=lambda e: page.close(connectivity_batch_modal))]
                            )
                            page.open(connectivity_batch_modal)
                            refresh_table()
                            update_ocr_button()
                            return
                        else:
                            file_item["status"] = "Error"
                            error_count += 1
                            log_add(f"❌ Error en {file_item['name']}: {data.get('mensaje', 'Error desconocido')}")
                            continue
                    
                    result = data or {}
                    
                    # Actualizar archivo con resultados
                    file_item["status"] = "Procesado"
                    file_item["result"] = result
                    processed_count += 1
                    
                    # Si es el archivo seleccionado, actualizar formulario
                    if selected_index == i:
                        last_result = result
                        fill_form(result)
                        
                    log_add(f"✅ Completado {processed_count}/{len(pending_files)}: {file_item['name']}")
                    refresh_table()
                    page.update()
                    
                except Exception as ex:
                    file_item["status"] = "Error"
                    error_count += 1
                    log_add(f"❌ Error en {file_item['name']}: {str(ex)}")
                    refresh_table()
                    page.update()
            
            # Resumen final
            log_add(f"🎯 Procesamiento completado: {processed_count} exitosos, {error_count} errores")
            update_ocr_button()
            
            # Modal de resultados
            results_dialog = ft.AlertDialog(
                title=ft.Text("✅ Procesamiento Completado"),
                content=ft.Text(f"Archivos procesados exitosamente: {processed_count}\nArchivos con errores: {error_count}\n\nRevisa los registros para más detalles."),
                actions=[ft.TextButton("OK", on_click=lambda e: page.close(results_dialog))]
            )
            page.open(results_dialog)

    def clear_all():
        nonlocal files, selected_index, last_result
        files, selected_index, last_result = [], None, None
        files_list.controls.clear()
        current_title.value = "Sin archivo seleccionado"
        current_meta.value = "Selecciona una imagen de la lista para comenzar"
        clear_form()
        log.controls.clear()
        update_ocr_button()
        page.update()

    def get_form_data() -> dict:
        return {
            "dni": tf_dni.value, "lm": tf_lm.value, "or": tf_or.value, "clase": tf_clase.value,
            "libro": tf_libro.value, "folio": tf_folio.value, "apellidos": tf_apellidos.value,
            "nombres": tf_nombres.value, "fecha_nacimiento": tf_fn.value, "presto_servicio": dd_presto.value,
            "gran_unidad": tf_gran.value, "unidad_alta": tf_unialta.value, "unidad_baja": tf_unibaja.value,
            "fecha_alta": tf_falta.value, "fecha_baja": tf_fbaja.value, "grado": tf_grado.value,
            "motivo_baja": tf_motivo.value,
        }

    # ---- Acciones del formulario ----
    def apply_changes():
        nonlocal last_result
        if selected_index is None:
            log_add("Seleccione una imagen para aplicar cambios.")
            return
        current_data = get_form_data()
        last_result = current_data
        files[selected_index]["result"] = current_data
        files[selected_index]["status"] = "Editado"
        refresh_table()
        log_add("✅ Cambios del formulario aplicados.")

    def on_mark_validated():
        if selected_index is None:
            log_add("Seleccione una imagen para marcar validación.")
            return
        files[selected_index]["status"] = "Validado"
        refresh_table()
        log_add("✅ Marcado como validado.")

    def _save_indices(indices: list[int]):
        """Unifica lógica con módulo PDF (manejo de sesión, duplicados y modal resumen)."""
        try:
            # get_db() devuelve generador; extraer sesión real
            sess_gen = get_db()
            try:
                db_sess = next(sess_gen)  # type: ignore
            except StopIteration:
                db_sess = None
            if db_sess is None:
                log_add("🚨 No se pudo crear sesión de base de datos.")
                return

            from database.models import Documento, Usuario  # import local para evitar overhead arriba
            from sqlalchemy import select

            # Resolver usuario
            try:
                username = (user_data or {}).get("username")
                if username:
                    user_row = db_sess.execute(select(Usuario).where(Usuario.nombre_usuario == username)).scalar_one_or_none()
                    user_id = getattr(user_row, "id_usuario", 1) if user_row else 1
                else:
                    user_id = 1
            except Exception:
                user_id = 1

            saved = 0
            skipped = 0
            for idx in indices:
                it = files[idx]
                result = it.get("result") or {}
                if not result:
                    log_add(f"⚠️ {it['name']} sin datos OCR, omitido.")
                    continue
                file_info = {"name": it["name"], "path": it["path"]}
                # Duplicado por ruta
                try:
                    existing = db_sess.execute(select(Documento).where(Documento.ruta_almacenamiento == file_info["path"])).scalar_one_or_none()
                except Exception:
                    existing = None
                if existing:
                    it["status"] = "Guardado"
                    skipped += 1
                    log_add(f"ℹ️ Ya existía documento: {it['name']}")
                    continue
                try:
                    ids_map = create_full_digital_record(db_sess, result, file_info, user_id)
                    it["status"] = "Guardado"
                    it["db_ids"] = ids_map
                    saved += 1
                    log_add(f"💾 Guardado: {it['name']}")
                except Exception as ex:
                    it["status"] = "Error"
                    log_add(f"🚨 Error al guardar {it['name']}: {ex}")

            try:
                db_sess.close()
            except Exception:
                pass

            refresh_table()
            update_ocr_button()
            # Modal resumen
            summary_modal = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.SAVE, color=Colors.PRIMARY),
                    ft.Text("Resultado de guardado", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Column([
                    ft.Text(f"Nuevos guardados: {saved}"),
                    ft.Text(f"Duplicados omitidos: {skipped}"),
                ], spacing=4),
                actions=[ft.FilledButton("Cerrar", on_click=lambda e: page.close(summary_modal))],
            )
            page.open(summary_modal)
        except Exception as ex:
            log_add(f"🚨 Error global de guardado: {ex}")

    def save_to_db_auto(_=None):
        """Guarda en BD con validaciones de estado"""
        log_add("🔄 Iniciando proceso de guardado...")
        
        # Verificar archivos marcados
        marked = [i for i, it in enumerate(files) if it.get("selected")]
        log_add(f"📋 Archivos marcados: {len(marked)}")
        log_add(f"📁 Archivo seleccionado: {selected_index}")
        
        # Si no hay archivos marcados, usar el archivo actualmente seleccionado
        if not marked and selected_index is not None:
            files_to_save = [selected_index]
            log_add(f"🎯 Usando archivo seleccionado: {files[selected_index]['name']}")
        elif marked:
            files_to_save = marked
            log_add(f"✅ Usando archivos marcados: {[files[i]['name'] for i in marked]}")
        else:
            # Modal de control cuando no hay archivos marcados ni seleccionados
            log_add("⚠️ No hay archivos para procesar")
            control_modal = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.WARNING, color=Colors.WARNING, size=24),
                    ft.Text("Sin selección")
                ], spacing=8),
                content=ft.Column([
                    ft.Text("No hay archivos seleccionados para guardar.", weight=ft.FontWeight.BOLD),
                    ft.Text("• Marca los archivos con ✅ para guardar múltiples"),
                    ft.Text("• O selecciona un archivo haciendo clic en él"),
                    ft.Text("• Los archivos deben tener datos OCR procesados")
                ], spacing=4, tight=True),
                actions=[ft.FilledButton("Entendido", on_click=lambda e: page.close(control_modal))]
            )
            page.open(control_modal)
            return
            
        # Verificar que todos los archivos tengan datos OCR
        sin_datos = []
        archivos_con_datos = []
        
        for idx in files_to_save:
            file_item = files[idx]
            has_ocr = bool(file_item.get("result"))
            log_add(f"🔍 {file_item['name']}: OCR={has_ocr}, Status={file_item.get('status', 'Sin estado')}")
            
            if not has_ocr:
                sin_datos.append(file_item["name"])
            else:
                archivos_con_datos.append(idx)
        
        log_add(f"📊 Archivos con datos OCR: {len(archivos_con_datos)}")
        log_add(f"📊 Archivos sin datos OCR: {len(sin_datos)}")
        
        # Si hay archivos sin datos, mostrar error
        if sin_datos:
            log_add(f"❌ Error: Archivos sin OCR: {sin_datos}")
            sin_datos_modal = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.ERROR, color=Colors.DANGER, size=24),
                    ft.Text("Archivos sin datos OCR")
                ], spacing=8),
                content=ft.Column([
                    ft.Text("Los siguientes archivos no tienen datos OCR:", weight=ft.FontWeight.BOLD),
                    ft.Text("\n".join([f"• {name}" for name in sin_datos[:5]]), size=12),
                    ft.Text(f"... y {len(sin_datos)-5} más" if len(sin_datos) > 5 else "", size=12, italic=True),
                    ft.Divider(),
                    ft.Text("Procesa OCR primero antes de guardar.")
                ], spacing=4, tight=True),
                actions=[ft.FilledButton("Entendido", on_click=lambda e: page.close(sin_datos_modal))]
            )
            page.open(sin_datos_modal)
            return
            
        # Si no hay archivos válidos para guardar
        if not archivos_con_datos:
            log_add("❌ No hay archivos válidos para guardar")
            return
            
        # Separar por estados de validación
        validados = []
        marcados_sin_validar = []
        
        for idx in archivos_con_datos:
            file_item = files[idx]
            status = file_item.get("status", "")
            is_marked = file_item.get("selected", False)
            is_current = idx == selected_index
            
            log_add(f"📝 {file_item['name']}: Status='{status}', Marcado={is_marked}, Actual={is_current}")
            
            if status == "Validado":
                validados.append(idx)
            else:
                # Si el archivo está marcado O es el seleccionado actualmente
                if is_marked or is_current:
                    marcados_sin_validar.append(idx)
        
        log_add(f"✅ Archivos validados: {len(validados)}")
        log_add(f"⏳ Archivos sin validar: {len(marcados_sin_validar)}")
        
        # Si hay archivos validados, guardarlos directamente
        if validados:
            page.run_task(_save_indices, validados)
            log_add(f"💾 Guardando {len(validados)} archivo(s) validado(s)")
            
        # Si hay archivos marcados/seleccionados pero no validados, pedir confirmación
        if marcados_sin_validar:
            def confirmar_guardado(e):
                page.close(confirmacion_modal)
                page.run_task(_save_indices, marcados_sin_validar)
                log_add(f"💾 Guardando {len(marcados_sin_validar)} archivo(s) sin validar")
                
            def cancelar_guardado(e):
                page.close(confirmacion_modal)
                log_add("❌ Guardado cancelado")
                
            confirmacion_modal = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.HELP, color=Colors.WARNING, size=24),
                    ft.Text("Archivos sin validar")
                ], spacing=8),
                content=ft.Column([
                    ft.Text(f"Hay {len(marcados_sin_validar)} archivo(s) con datos OCR pero sin validar:", weight=ft.FontWeight.BOLD),
                    ft.Text("\n".join([f"• {files[idx]['name']}" for idx in marcados_sin_validar[:3]]), size=12),
                    ft.Text(f"... y {len(marcados_sin_validar)-3} más" if len(marcados_sin_validar) > 3 else "", size=12, italic=True),
                    ft.Divider(),
                    ft.Text("¿Estás seguro de guardar sin validar?", color=Colors.WARNING, weight=ft.FontWeight.BOLD)
                ], spacing=4, tight=True),
                actions=[
                    ft.TextButton("Cancelar", on_click=cancelar_guardado),
                    ft.FilledButton("Sí, guardar", on_click=confirmar_guardado, bgcolor=Colors.WARNING)
                ]
            )
            page.open(confirmacion_modal)

    # -------- File Picker --------
    fp = ft.FilePicker(on_result=lambda e: on_pick(e))
    page.overlay.append(fp)

    def on_pick(e: ft.FilePickerResultEvent):
        if not e or not e.files:
            log_add("❌ No se seleccionaron archivos", "warning")
            return
            
        for f in e.files:
            # Asegurar que tenemos una ruta válida
            if not f.path:
                log_add(f"❌ No se pudo obtener la ruta de: {f.name}", "error")
                continue
                
            path = f.path
            
            # Verificar que el archivo existe
            if not os.path.exists(path):
                log_add(f"❌ Archivo no encontrado: {f.name}", "error")
                continue
                
            # Verificar formato de imagen
            if not any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']):
                log_add(f"❌ Formato no soportado: {f.name}", "warning")
                continue
                
            # Verificar duplicados
            if any(it["path"] == path for it in files):
                log_add(f"⚠️ Archivo ya cargado: {f.name}", "warning")
                continue

            # Determinar MIME type
            ext = path.lower()
            if ext.endswith(('.jpg', '.jpeg')):
                mime = "image/jpeg"
            elif ext.endswith('.png'):
                mime = "image/png"
            elif ext.endswith('.gif'):
                mime = "image/gif"
            elif ext.endswith('.bmp'):
                mime = "image/bmp"
            elif ext.endswith('.webp'):
                mime = "image/webp"
            else:
                mime = "image/jpeg"  # fallback

            files.append({
                "name": f.name, 
                "path": path, 
                "mime": mime, 
                "size": getattr(f, "size", 0), 
                "status": "Pendiente"
            })
            log_add(f"✅ Archivo añadido: {f.name}", "success")
            
        refresh_table()
        
        # Auto-seleccionar el primer archivo si no hay ninguno seleccionado
        if files and selected_index is None:
            select_file(0)

    def update_ocr_button():
        """Actualiza el estado del botón OCR según el archivo seleccionado"""
        if selected_index is not None and selected_index < len(files):
            file_item = files[selected_index]
            status = file_item.get("status", "Pendiente")
            
            if status == "Procesando":
                btn_ocr.disabled = True
                btn_ocr.text = "Procesando..."
            elif status == "Procesado":
                btn_ocr.disabled = False
                btn_ocr.text = "Reprocesar OCR"
            else:
                btn_ocr.disabled = False
                btn_ocr.text = "Procesar OCR"
        else:
            btn_ocr.disabled = True
            btn_ocr.text = "Procesar OCR"
        
        page.update()

    # -------- Crear botones con nuevo diseño --------
    btn_pick = create_button("Cargar Imágenes", ft.Icons.UPLOAD_FILE, "filled", lambda e: fp.pick_files(allow_multiple=True))
    btn_ocr = create_button("Procesar OCR", ft.Icons.SMART_TOY, "filled", lambda e: run_ocr_jpg(), Colors.SECONDARY)
    btn_ocr_batch = create_button("OCR Todo", ft.Icons.AUTO_AWESOME, "outlined", lambda e: run_ocr_batch(), Colors.SECONDARY)
    btn_clear = create_button("Limpiar Todo", ft.Icons.CLEAR_ALL, "outlined", lambda e: clear_all(), Colors.WARNING)

    btn_apply = create_button("Aplicar Cambios", ft.Icons.CHECK_CIRCLE, "filled", lambda e: apply_changes())
    btn_mark = create_button("Marcar Validado", ft.Icons.VERIFIED, "outlined", lambda e: on_mark_validated(), Colors.SUCCESS)
    btn_save = create_button("Guardar en BD", ft.Icons.SAVE, "filled", save_to_db_auto, Colors.SECONDARY)

    # -------- Layout moderno y responsivo --------
    # Panel izquierdo: Lista de archivos
    files_panel = create_card(
        ft.Column([
            ft.Row([btn_pick, btn_ocr, btn_ocr_batch, btn_clear], spacing=8, wrap=True),
            ft.Container(files_list, expand=True)
        ], spacing=16, expand=True),
        "Archivos de Imagen",
        16
    )

    # Columna izquierda - Solo archivos
    left_column = ft.Container(
        content=files_panel,
        expand=True  # Cambiar a expandible para responsividad
    )

    # Panel de formulario mejorado y responsivo  
    form_header = file_info_panel  # Usar el nuevo panel de información detallada

    # Campos organizados en filas más pequeñas para mejor adaptabilidad
    form_content = ft.Column([
        form_header,
        
        # Sección: Identificación
        ft.Text("📋 Identificación", size=16, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ft.Row([tf_dni, tf_lm], wrap=True, spacing=12),
        ft.Row([tf_or], wrap=True, spacing=12),
        
        # Sección: Documento
        ft.Text("📄 Documento", size=16, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ft.Row([tf_clase, tf_libro], wrap=True, spacing=12),
        ft.Row([tf_folio], wrap=True, spacing=12),
        
        # Sección: Datos Personales  
        ft.Text("👤 Datos Personales", size=16, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ft.Row([tf_apellidos], wrap=True, spacing=12),
        ft.Row([tf_nombres], wrap=True, spacing=12),
        ft.Row([tf_fn, dd_presto], wrap=True, spacing=12),
        
        # Sección: Servicio Militar
        ft.Text("⚔️ Servicio Militar", size=16, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE),
        ft.Row([tf_gran], wrap=True, spacing=12),
        ft.Row([tf_unialta, tf_unibaja], wrap=True, spacing=12),
        ft.Row([tf_falta, tf_fbaja], wrap=True, spacing=12),
        ft.Row([tf_grado], wrap=True, spacing=12),
        tf_motivo,
        
        # Acciones
        ft.Divider(color=Colors.BORDER),
        ft.Row([btn_apply, btn_mark], spacing=12, wrap=True),
        ft.Row([btn_save], spacing=12, wrap=True)
    ], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)

    form_panel = create_card(form_content, "Datos Extraídos", 20)

    # Columna derecha - Expandible
    right_column = ft.Container(
        content=form_panel,
        expand=True
    )

    # Layout principal completamente responsivo
    main_content = ft.ResponsiveRow([
        ft.Container(
            content=left_column,
            col={"xs": 12, "sm": 12, "md": 5, "lg": 4, "xl": 4},  # Responsive columns
            padding=ft.padding.only(right=8)
        ),
        ft.Container(
            content=right_column,
            col={"xs": 12, "sm": 12, "md": 7, "lg": 8, "xl": 8},  # Responsive columns
            padding=ft.padding.only(left=8)
        )
    ], expand=True, spacing=0)

    # Título principal responsivo
    header = ft.Container(
        content=ft.ResponsiveRow([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.IMAGE, size=28, color=Colors.PRIMARY),
                    ft.Text("Digitalización de Imágenes", size=20, weight=ft.FontWeight.BOLD, color=Colors.ON_SURFACE, expand=True)
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                col=12
            )
        ]),
        padding=ft.padding.only(bottom=12)
    )

    content = ft.Column([
        header,
        ft.Container(main_content, expand=True)
    ], expand=True, spacing=0)

    container = ft.Container(
        content=content,
        padding=ft.padding.symmetric(horizontal=16, vertical=12),  # Padding responsivo
        expand=True,
        bgcolor=Colors.SURFACE
    )

    # Función de limpieza para desregistrar guardia
    def cleanup():
        unregister_guard("digitalizacion_jpg")

    # Agregar función de limpieza al contenedor
    container.cleanup = cleanup
    
    return container
