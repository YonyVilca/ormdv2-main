# modules/digitalizacion/digitalizacion_view.py
# -*- coding: utf-8 -*-
import os
import json
import flet as ft
from utils import extractors  # debe exponer extract_pdf(path) y extract_image(path)

def create_digitalizacion_view(page: ft.Page, user_data=None) -> ft.Control:
    """
    Vista de Digitalización sin visor de archivos (ni PNG/PDF en preview).
    Separa OCR JPG vs OCR PDF con botones específicos.
    """

    files: list[dict] = []     # [{"name","path","mime","size","status"}]
    selected_index: int | None = None
    last_result: dict | None = None

    # ---- Log
    log = ft.ListView(expand=True, spacing=4, height=130)
    def log_add(msg: str):
        log.controls.append(ft.Text(msg, size=12))
        page.update()

    # ---- Tabla de archivos (sin preview)
    rows = ft.Column(scroll=ft.ScrollMode.ALWAYS)
    def guess_mime(path: str) -> str:
        ext = os.path.splitext(path.lower())[1]
        return {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png"
        }.get(ext, "application/octet-stream")

    def refresh_table():
        rows.controls.clear()
        for i, it in enumerate(files):
            open_btn = ft.IconButton(
                icon=ft.Icons.VISIBILITY,
                tooltip="Seleccionar",
                on_click=(lambda idx=i: (lambda e: select_file(idx)))(i),
            )
            status_color = ft.Colors.GREEN if it.get("status") == "Procesado" else ft.Colors.GREY
            rows.controls.append(
                ft.Row(
                    [
                        ft.Text(it["name"]),
                        ft.Text(f'{round((it.get("size") or 0)/1024,1)} KB', width=80),
                        ft.Text(it["mime"], width=130),
                        ft.Text(it.get("status", "Pendiente"), color=status_color),
                        open_btn,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )
        page.update()

    # ---- Selección
    current_title = ft.Text("Sin archivo seleccionado")
    def select_file(idx: int):
        nonlocal selected_index
        selected_index = idx
        current_title.value = f"Seleccionado: {files[idx]['name']}"
        page.update()

    # ---- FilePicker (sin usar f.mime_type; no todas las versiones lo traen)
    def on_pick(e: ft.FilePickerResultEvent):
        nonlocal selected_index
        if not e or not e.files:
            return
        for f in e.files:
            path = f.path or f.name
            mime = guess_mime(path)
            size = getattr(f, "size", None)
            if size is None and os.path.exists(path):
                size = os.path.getsize(path)
            files.append({
                "name": f.name, "path": path, "mime": mime, "size": size or 0, "status": "Pendiente"
            })
        selected_index = len(files) - 1
        refresh_table()
        if selected_index is not None:
            select_file(selected_index)

    fp = ft.FilePicker(on_result=on_pick)
    page.overlay.append(fp)

    # ---- OCR
    def run_ocr_jpg(e):
        run_ocr(kind="jpg")

    def run_ocr_pdf(e):
        run_ocr(kind="pdf")

    def run_ocr(kind: str):
        nonlocal last_result
        if selected_index is None:
            log_add("Seleccione un archivo de la lista.")
            return
        it = files[selected_index]
        path = it["path"]
        if not os.path.exists(path):
            log_add(f"Ruta no existe: {path}")
            return
        try:
            if kind == "jpg":
                if not it["mime"].startswith("image/"):
                    log_add("El archivo seleccionado no es una imagen.")
                    return
                data = extractors.extract_image(path)
            else:
                if not it["mime"].endswith("pdf"):
                    log_add("El archivo seleccionado no es PDF.")
                    return
                data = extractors.extract_pdf(path)

            last_result = data or {}
            show_json_modal(last_result)
            it["status"] = "Procesado"
            refresh_table()
            log_add(f"OCR {kind.upper()} OK → {it['name']}")
        except Exception as ex:
            log_add(f"OCR {kind.upper()} falló: {ex}")

    # ---- JSON modal
    json_dialog = ft.AlertDialog(modal=True)
    def show_json_modal(obj: dict):
        txt = json.dumps(obj or {}, ensure_ascii=False, indent=2)
        json_dialog.title = ft.Text("Resultado JSON")
        json_dialog.content = ft.Container(
            content=ft.Text(txt, selectable=True, size=13),
            width=680, height=420, padding=10
        )
        json_dialog.actions = [ft.TextButton("Cerrar", on_click=lambda e: _close_json())]
        json_dialog.open = True
        page.dialog = json_dialog
        page.update()

    def _close_json():
        json_dialog.open = False
        page.update()

    # ---- Acciones formulario (stubs)
    def clear_all(e=None):
        nonlocal files, selected_index, last_result
        files = []
        selected_index = None
        last_result = None
        rows.controls.clear()
        current_title.value = "Sin archivo seleccionado"
        log.controls.clear()
        page.update()

    def save_to_db(e=None):
        if not last_result:
            log_add("No hay datos para guardar.")
            return
        # TODO: inserta en tu BD aquí
        log_add("Guardado en BD (stub).")

    # ---- Botones
    btn_pick   = ft.FilledButton("Seleccionar archivos", icon=ft.Icons.FOLDER_OPEN, on_click=lambda e: fp.pick_files(allow_multiple=True))
    btn_ocr_jp = ft.FilledButton("OCR JPG", icon=ft.Icons.IMAGE, on_click=run_ocr_jpg)
    btn_ocr_pf = ft.FilledButton("OCR PDF", icon=getattr(ft.Icons, "PICTURE_AS_PDF", ft.Icons.DESCRIPTION), on_click=run_ocr_pdf)
    btn_clear  = ft.OutlinedButton("Limpiar", icon=ft.Icons.CLEAR, on_click=clear_all)
    btn_save   = ft.FilledButton("Guardar en BD", icon=ft.Icons.SAVE, on_click=save_to_db)
    btn_json   = ft.OutlinedButton("Ver JSON", icon=ft.Icons.CODE, on_click=lambda e: show_json_modal(last_result or {}))

    # ---- Layout (sin viewer)
    left_panel = ft.Container(
        content=ft.Column([
            ft.Text("Lote de documentos", weight=ft.FontWeight.BOLD),
            rows,
            ft.Text("Log:"),
            log,
        ], spacing=12),
        width=440, padding=10
    )

    right_panel = ft.Container(
        content=ft.Column([
            current_title,
            ft.Row([btn_ocr_jp, btn_ocr_pf, btn_json], spacing=10),
            ft.Row([btn_save, btn_clear], spacing=10),
        ], spacing=12),
        expand=True, padding=10
    )

    content = ft.Column([
        ft.Text("Digitalización de Documentos", size=22, weight=ft.FontWeight.BOLD),
        ft.Row([btn_pick], spacing=12),
        ft.Row([left_panel, ft.VerticalDivider(), right_panel], expand=True),
    ], expand=True, spacing=8)

    # Devuelve un Control (Column). El dashboard lo incrusta en su layout.
    return content
