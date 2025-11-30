# modules/dashboard/backups.py
# -*- coding: utf-8 -*-
import os
import json
import shutil
import flet as ft
from datetime import datetime
import asyncio
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker

from .layout import PRIMARY_COLOR, ACCENT_COLOR, CARD_BG
from database.connection import SessionLocal
from database import models


def build(page: ft.Page, user_data):
    # Permisos: Solo Administrador debe operar aquí
    def _norm_role(name: str) -> str:
        n = (name or "").strip().lower()
        mapping = {
            "administrador": "administrador",
            "admin": "administrador",
            "acceso 1": "administrador",
        }
        return mapping.get(n, n)

    def is_admin() -> bool:
        return _norm_role((user_data or {}).get("rol", "")) == "administrador"

    if not is_admin():
        return ft.Column([
            ft.Text("🛡️ Módulo: Backups y Administración", size=26, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ft.Container(height=10),
            ft.Text("Acceso restringido. Solo el Administrador puede usar estas funciones.", size=14),
        ])

    # ---------- Auditoría (lado izquierdo, ancho grande) ----------
    list_ref = ft.Ref[ft.ListView]()
    filter_tf = ft.TextField(hint_text="Filtrar por texto", width=320)
    date_from_tf = ft.TextField(hint_text="Desde (YYYY-MM-DD)", width=160)
    date_to_tf = ft.TextField(hint_text="Hasta (YYYY-MM-DD)", width=160)
    type_dd = ft.Dropdown(width=180, value="todo", options=[
        ft.dropdown.Option("todo"),
        ft.dropdown.Option("busquedas"),
        ft.dropdown.Option("consultas"),
        ft.dropdown.Option("eliminaciones"),
    ])
    status = ft.Text("", size=12, color=ft.Colors.BLUE_GREY_600)
    count_badge = ft.Container(content=ft.Text("0", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD), bgcolor=ACCENT_COLOR, border_radius=10, padding=ft.padding.symmetric(horizontal=8, vertical=2))
    pager_label = ft.Text("Página 1 / 1", size=12)
    records: list[dict] = []
    state = {"page_index": 0}

    def _action_cell(rec: dict):
        a = (rec.get("accion") or "").lower()
        if a in ("eliminacion_documento", "eliminacion_ciudadano"):
            return ft.IconButton(icon=ft.Icons.RESTORE, tooltip="Recuperar", on_click=lambda ev, r=rec: open_restore_dialog(r))
        return ft.Container()

    pending_rebuild = False

    def _badge(accion: str) -> ft.Control:
        amap = {
            "busqueda": (ft.Colors.BLUE_100, ft.Colors.BLUE_700, ft.Icons.SEARCH),
            "consulta_ciudadano": (ft.Colors.TEAL_100, ft.Colors.TEAL_700, ft.Icons.PERSON_SEARCH),
            "eliminacion_documento": (ft.Colors.ORANGE_100, ft.Colors.ORANGE_800, ft.Icons.DELETE),
            "eliminacion_ciudadano": (ft.Colors.RED_100, ft.Colors.RED_800, ft.Icons.DELETE_FOREVER),
        }
        bg, fg, ic = amap.get(accion, (ft.Colors.GREY_100, ft.Colors.GREY_800, ft.Icons.HISTORY))
        return ft.Container(
            bgcolor=bg, padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=16,
            content=ft.Row([ft.Icon(ic, size=14, color=fg), ft.Text(accion, size=11, color=fg, weight=ft.FontWeight.W_600)], spacing=6)
        )

    def _rebuild_list():
        nonlocal pending_rebuild
        if not list_ref.current:
            # Diferir reconstrucción hasta que el ListView esté montado
            pending_rebuild = True
            return
        page_size = 30
        start = state["page_index"] * page_size
        end = start + page_size
        page_records = records[start:end]
        items: list[ft.Control] = []
        if not page_records:
            items.append(ft.Container(padding=16, content=ft.Text("No hay eventos", size=12, color=ft.Colors.BLUE_GREY_400)))
        for idx, r in enumerate(page_records):
            accion = (r.get("accion") or "").lower()
            icon = ft.Icons.HISTORY
            detail = ""
            if accion == "busqueda":
                icon = ft.Icons.SEARCH
                detail = f"'{r.get('query','')}' • {r.get('resultados',0)} resultado(s)"
            elif accion == "consulta_ciudadano":
                icon = ft.Icons.PERSON_SEARCH
                detail = f"DNI {r.get('dni','—')} • {r.get('apellidos','')} {r.get('nombres','')} (ID {r.get('id_ciudadano','')})"
            elif accion == "eliminacion_ciudadano":
                icon = ft.Icons.DELETE_FOREVER
                detail = f"Ciudadano ID {r.get('id_ciudadano','?')} • Docs {r.get('removed_docs',0)} • Archivos {r.get('removed_files',0)}"
            elif accion == "eliminacion_documento":
                icon = ft.Icons.DELETE
                d = r.get("documento", {})
                detail = f"Doc #{d.get('id_documento','?')} • {d.get('nombre_archivo','')}"
            ts = r.get("ts", "")
            stripe = ft.Container(width=4, bgcolor=ACCENT_COLOR if 'eliminacion' in accion else ft.Colors.BLUE_GREY_200)
            card = ft.Container(
                border=ft.border.all(1, ft.Colors.BLUE_GREY_50),
                border_radius=10,
                bgcolor=ft.Colors.WHITE,
                padding=10,
                content=ft.Row([
                    stripe,
                    ft.Container(width=12),
                    ft.Column([
                        ft.Row([
                            ft.Text(str(ts)[:19], size=12, color=ft.Colors.BLUE_GREY_600),
                            ft.Container(width=12),
                            _badge(accion),
                            ft.Container(expand=True),
                            ft.Icon(icon, size=16, color=ACCENT_COLOR),
                        ], alignment=ft.MainAxisAlignment.START, spacing=6),
                        ft.Row([
                            ft.Text(f"{r.get('usuario','—')}", size=13, weight=ft.FontWeight.W_600),
                            ft.Text(f"({r.get('rol','—')})", size=12, color=ft.Colors.BLUE_GREY_600),
                        ], spacing=6),
                        ft.Text(detail, size=12),
                    ], expand=True, spacing=4),
                    ft.Container(width=12),
                    _action_cell(r),
                ], alignment=ft.MainAxisAlignment.START)
            )
            items.append(ft.Container(content=card, margin=ft.margin.only(bottom=8)))
        list_ref.current.controls = items
        list_ref.current.update()
        total_pages = max(1, (len(records) + page_size - 1) // page_size)
        pager_label.value = f"Página {state['page_index']+1} / {total_pages}"
        pager_label.update()
        status.value = f"{len(records)} evento(s)"; status.update()

    def _schedule_rebuild_delay():
        # Reintenta reconstruir tras breve espera si aún no está montado
        try:
            if hasattr(page, "run_task"):
                async def _later():
                    await asyncio.sleep(0.05)
                    if pending_rebuild and list_ref.current:
                        _rebuild_list()
                page.run_task(_later())
        except Exception:
            pass

    def load_logs(_=None):
        from datetime import datetime as _dt
        log_path_consultas = os.path.join("storage", "data", "logs", "consultas.jsonl")
        log_path_elim = os.path.join("storage", "data", "logs", "auditoria_eliminaciones.jsonl")
        items: list[dict] = []
        q = (filter_tf.value or "").strip().lower()
        kind = (type_dd.value or "todo").lower()

        def _add_rec(rec: dict):
            accion = (rec.get("accion") or "").lower()
            if kind == "busquedas" and accion != "busqueda":
                return
            if kind == "consultas" and accion != "consulta_ciudadano":
                return
            if kind == "eliminaciones" and accion not in ("eliminacion_ciudadano", "eliminacion_documento"):
                return
            df = (date_from_tf.value or "").strip()
            dtv = (date_to_tf.value or "").strip()
            blob = " ".join([
                str(rec.get("usuario") or ""), str(rec.get("rol") or ""), str(rec.get("query") or ""),
                str(rec.get("dni") or ""), str(rec.get("apellidos") or ""), str(rec.get("nombres") or ""), accion,
                str(rec.get("id_ciudadano") or ""), str(rec.get("removed_docs") or ""), str(rec.get("removed_files") or ""),
            ]).lower()
            if q and q not in blob:
                return
            ts = rec.get("ts")
            try:
                ts_dt = _dt.fromisoformat(ts) if ts else None
            except Exception:
                ts_dt = None
            try:
                if df:
                    df_dt = _dt.strptime(df, "%Y-%m-%d")
                    if ts_dt and ts_dt < df_dt:
                        return
                if dtv:
                    dt_dt = _dt.strptime(dtv, "%Y-%m-%d")
                    if ts_dt and ts_dt > dt_dt.replace(hour=23, minute=59, second=59):
                        return
            except Exception:
                pass
            items.append(rec)

        any_file = False
        if os.path.exists(log_path_consultas):
            any_file = True
            with open(log_path_consultas, "r", encoding="utf-8") as f:
                lines = f.readlines()[-1000:]
            for ln in reversed(lines):
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                _add_rec(rec)
        if os.path.exists(log_path_elim):
            any_file = True
            with open(log_path_elim, "r", encoding="utf-8") as f:
                lines_e = f.readlines()[-1000:]
            for ln in reversed(lines_e):
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                _add_rec(rec)
        nonlocal records
        records = items
        state["page_index"] = 0
        _rebuild_list()
        if pending_rebuild:
            _schedule_rebuild_delay()
        count_badge.content.value = str(len(records)); count_badge.update()
        if not any_file:
            status.value = "Sin archivos de logs todavía"
        elif len(items) == 0:
            status.value = "No hay eventos según los filtros"
        else:
            status.value = f"{len(items)} evento(s)"
        status.update()

    def export_csv(_):
        log_dir = os.path.join("storage", "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        out_path = os.path.join(log_dir, "auditoria_export.csv")
        import csv
        cols = ["ts","id_usuario","usuario","rol","accion","query","resultados","id_ciudadano","dni","lm","apellidos","nombres","removed_docs","removed_files"]
        filtered = records if records else []
        if filtered:
            with open(out_path, "w", newline="", encoding="utf-8") as cf:
                w = csv.DictWriter(cf, fieldnames=cols)
                w.writeheader()
                for r in filtered:
                    w.writerow({k: r.get(k, "") for k in cols})
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Exportación completada"),
                content=ft.Text(f"Archivo generado: {out_path}"),
                actions=[ft.TextButton("Abrir carpeta", on_click=lambda e: os.startfile(log_dir)), ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
            )
            page.open(dlg)
        else:
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Sin datos para exportar"),
                content=ft.Text("No hay eventos según el filtro actual."),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
            )
            page.open(dlg)
        page.update()

    # ---- Restauraciones desde auditoría ----
    def _restore_document(rec: dict):
        try:
            session = SessionLocal()
            doc_info = rec.get("documento", {})
            moved = rec.get("moved") or {}
            original = moved.get("from") or doc_info.get("ruta_almacenamiento")
            trash_path = moved.get("to")
            if trash_path and original and os.path.exists(trash_path):
                os.makedirs(os.path.dirname(original), exist_ok=True)
                shutil.move(trash_path, original)
            ruta = original or doc_info.get("ruta_almacenamiento")
            exist = None
            if ruta:
                exist = session.execute(select(models.Documento).where(models.Documento.ruta_almacenamiento == ruta)).scalar_one_or_none()
            if not exist:
                exist = models.Documento(
                    nombre_archivo=doc_info.get("nombre_archivo") or (os.path.basename(ruta) if ruta else None),
                    ruta_almacenamiento=ruta,
                    fecha_extraccion=datetime.now(),
                    id_usuario_extraccion=(user_data or {}).get("id_usuario") or 1,
                )
                session.add(exist); session.flush()
            cid = rec.get("id_ciudadano")
            if cid and exist:
                link = session.execute(select(models.CiudadanoDocumento).where(
                    (models.CiudadanoDocumento.id_ciudadano == cid) & (models.CiudadanoDocumento.id_documento == exist.id_documento)
                )).first()
                if not link:
                    session.add(models.CiudadanoDocumento(id_ciudadano=cid, id_documento=exist.id_documento))
            session.commit()
            page.snack_bar = ft.SnackBar(content=ft.Text("Documento restaurado"), open=True)
        except Exception as ex:
            page.open(ft.AlertDialog(title=ft.Text("Error restaurando"), content=ft.Text(str(ex)), modal=True))
        finally:
            session.close(); page.update(); load_logs()

    def _restore_citizen(rec: dict):
        try:
            session = SessionLocal()
            snap = rec.get("snapshot", {})
            c = snap.get("ciudadano") or {}
            docs = snap.get("documentos") or []
            serv = snap.get("servicio") or None
            doc_serv = snap.get("doc_servicio") or []
            moved_files = rec.get("files_moved") or []
            for mv in moved_files:
                src = mv.get("to"); dst = mv.get("from")
                if src and dst and os.path.exists(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.move(src, dst)
            target = models.Ciudadano(
                dni=c.get("dni"), lm=c.get("lm"), apellidos=c.get("apellidos") or "", nombres=c.get("nombres") or "",
                fecha_nacimiento=None, presto_servicio=c.get("presto_servicio"),
                fecha_creacion=datetime.now(), id_usuario_creacion=(user_data or {}).get("id_usuario") or 1,
            )
            session.add(target); session.flush()
            for d in docs:
                ruta = d.get("ruta_almacenamiento"); exist = None
                if ruta:
                    exist = session.execute(select(models.Documento).where(models.Documento.ruta_almacenamiento == ruta)).scalar_one_or_none()
                if not exist:
                    exist = models.Documento(
                        nombre_archivo=d.get("nombre_archivo") or (os.path.basename(ruta) if ruta else None),
                        ruta_almacenamiento=ruta,
                        fecha_extraccion=datetime.now(), id_usuario_extraccion=(user_data or {}).get("id_usuario") or 1,
                    )
                    session.add(exist); session.flush()
                link = session.execute(select(models.CiudadanoDocumento).where(
                    (models.CiudadanoDocumento.id_ciudadano == target.id_ciudadano) & (models.CiudadanoDocumento.id_documento == exist.id_documento)
                )).first()
                if not link:
                    session.add(models.CiudadanoDocumento(id_ciudadano=target.id_ciudadano, id_documento=exist.id_documento))
            if serv and not session.execute(select(models.DatosServicioMilitar).where(models.DatosServicioMilitar.id_ciudadano == target.id_ciudadano)).scalar_one_or_none():
                def _p(s):
                    try:
                        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
                    except Exception:
                        return None
                serv_obj = models.DatosServicioMilitar(
                    id_ciudadano=target.id_ciudadano,
                    id_unidad_alta=serv.get("id_unidad_alta"), id_unidad_baja=serv.get("id_unidad_baja"),
                    id_grado=serv.get("id_grado"), id_motivo_baja=serv.get("id_motivo_baja"),
                    referencia_documento_origen=serv.get("referencia_documento_origen"), clase=serv.get("clase"), libro=serv.get("libro"), folio=serv.get("folio"),
                    fecha_alta=_p(serv.get("fecha_alta")), fecha_baja=_p(serv.get("fecha_baja")),
                )
                session.add(serv_obj); session.flush()
                for link in doc_serv:
                    did = link.get("id_documento")
                    if did:
                        doc_exist = session.get(models.Documento, did)
                        if doc_exist:
                            rel = session.execute(select(models.DocumentoServicio).where(
                                (models.DocumentoServicio.id_documento == did) & (models.DocumentoServicio.id_servicio == serv_obj.id_servicio)
                            )).first()
                            if not rel:
                                session.add(models.DocumentoServicio(id_documento=did, id_servicio=serv_obj.id_servicio))
            session.commit()
            try:
                if hasattr(page, "pubsub") and hasattr(page.pubsub, "send_all"):
                    page.pubsub.send_all({"type": "stats_changed"})
            except Exception:
                pass
            page.snack_bar = ft.SnackBar(content=ft.Text("Ciudadano restaurado"), open=True)
        except Exception as ex:
            page.open(ft.AlertDialog(title=ft.Text("Error restaurando"), content=ft.Text(str(ex)), modal=True))
        finally:
            session.close(); page.update(); load_logs()

    def open_restore_dialog(rec: dict):
        accion = (rec.get("accion") or "").lower()
        if accion == "eliminacion_documento":
            d = rec.get("documento", {})
            resumen = ft.Column([
                ft.Text("¿Restaurar documento eliminado?", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"ID doc: {d.get('id_documento','—')}  •  Archivo: {d.get('nombre_archivo','—')}", size=12),
                ft.Text(f"Ruta original: {d.get('ruta_almacenamiento','—')}", size=12, color=ft.Colors.BLUE_GREY_700),
                ft.Text(f"ID ciudadano: {rec.get('id_ciudadano','—')}", size=12, color=ft.Colors.BLUE_GREY_700),
            ], spacing=6, tight=True)

            def confirmar(_):
                page.close(dlg)
                _restore_document(rec)
                info = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Restauración completada"),
                    content=ft.Text(f"Se restauró el documento #{d.get('id_documento','—')} ({d.get('nombre_archivo','')})."),
                    actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(info))],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                page.open(info)

            dlg = ft.AlertDialog(
                modal=True,
                content=resumen,
                actions=[ft.TextButton("Cancelar", on_click=lambda e: page.close(e.control.parent)), ft.FilledButton("Restaurar", icon=ft.Icons.RESTORE, on_click=confirmar)],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.open(dlg)
            return

        if accion == "eliminacion_ciudadano":
            snap = rec.get("snapshot", {})
            c = snap.get("ciudadano") or {}
            docs = snap.get("documentos") or []
            resumen = ft.Column([
                ft.Text("¿Restaurar ciudadano eliminado?", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"ID: {rec.get('id_ciudadano','—')}  •  DNI: {c.get('dni','—')}", size=12),
                ft.Text(f"Nombre: {c.get('apellidos','')} {c.get('nombres','')}", size=12),
                ft.Text(f"Documentos a relinkear: {len(docs)}", size=12, color=ft.Colors.BLUE_GREY_700),
            ], spacing=6, tight=True)

            def confirmar2(_):
                page.close(_.control.parent)
                _restore_citizen(rec)
                info = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Restauración completada"),
                    content=ft.Text(f"Se restauró el ciudadano {c.get('apellidos','')} {c.get('nombres','')} (DNI {c.get('dni','—')})."),
                    actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                page.open(info)

            dlg = ft.AlertDialog(
                modal=True,
                content=resumen,
                actions=[ft.TextButton("Cancelar", on_click=lambda e: page.close(e.control.parent)), ft.FilledButton("Restaurar", icon=ft.Icons.RESTORE_PAGE, on_click=confirmar2)],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.open(dlg)
            return

    # ---------- Acciones administrativas (lado derecho) ----------
    backup_dir_tf = ft.TextField(label="Carpeta de respaldo", value=os.path.join("storage", "backups"), width=380)
    target_db_tf = ft.TextField(label="DATABASE_URL destino (migración)", width=380, hint_text="postgresql+psycopg2://usuario:pass@host:puerto/db")

    def clear_cache(_):
        temp_dir = os.path.join("storage", "data", "temp")
        archivos_temp = os.listdir(temp_dir) if os.path.exists(temp_dir) else []
        def do_clear(_):
            try:
                if os.path.exists(temp_dir):
                    for name in os.listdir(temp_dir):
                        p = os.path.join(temp_dir, name)
                        try:
                            if os.path.isfile(p) or os.path.islink(p):
                                os.unlink(p)
                            elif os.path.isdir(p):
                                shutil.rmtree(p)
                        except Exception:
                            pass
                dlg2 = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Caché liberada"),
                    content=ft.Text("Se liberaron los archivos temporales."),
                    actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
                )
                page.open(dlg2)
            except Exception as ex:
                page.open(ft.AlertDialog(title=ft.Text("Error limpiando"), content=ft.Text(str(ex)), modal=True))
            finally:
                page.update()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Liberar caché temporal"),
            content=ft.Column([
                ft.Text("Archivos temporales detectados en caché:", size=15, weight=ft.FontWeight.BOLD),
                ft.Column([ft.Text(f"• {name}", size=13) for name in archivos_temp]) if archivos_temp else ft.Text("No hay archivos temporales en caché.", size=13, color=ft.Colors.BLUE_GREY_600),
                ft.Divider(),
                ft.Text("¿Está seguro de eliminar estos archivos temporales?", size=13, color=ft.Colors.RED_700) if archivos_temp else ft.Text("Nada que eliminar.", size=13, color=ft.Colors.GREEN_700)
            ], tight=True, spacing=8),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(e.control.parent)),
                ft.FilledButton("Liberar caché", icon=ft.Icons.CLEAR_ALL, on_click=do_clear, disabled=not archivos_temp)
            ],
        )
        page.open(dlg)
        page.update()

    def export_backup(_):
        # Validación de campo de carpeta de respaldo
        base_dir = backup_dir_tf.value or ""
        if not base_dir.strip():
            page.open(ft.AlertDialog(
                modal=True,
                title=ft.Text("Error de validación"),
                content=ft.Text("Debe especificar la carpeta de respaldo antes de exportar."),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
            ))
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(base_dir, f"backup_{ts}")
            os.makedirs(out_dir, exist_ok=True)
            session = SessionLocal()
            payload = {
                "roles": [vars(x) for x in session.execute(select(models.Rol)).scalars().all()],
                "usuarios": [vars(x) for x in session.execute(select(models.Usuario)).scalars().all()],
                "ciudadanos": [vars(x) for x in session.execute(select(models.Ciudadano)).scalars().all()],
                "documentos": [vars(x) for x in session.execute(select(models.Documento)).scalars().all()],
                "servicios": [vars(x) for x in session.execute(select(models.DatosServicioMilitar)).scalars().all()],
                "ciudadano_documento": [{"id_ciudadano": x.id_ciudadano, "id_documento": x.id_documento} for x in session.execute(select(models.CiudadanoDocumento)).scalars().all()],
                "documento_servicio": [{"id_documento": x.id_documento, "id_servicio": x.id_servicio} for x in session.execute(select(models.DocumentoServicio)).scalars().all()],
            }
            # convertir objetos ORM a dict simple
            def _clean(o):
                if not isinstance(o, dict):
                    return {}
                return {k: v for k, v in o.items() if not k.startswith("_")}
            clean = {k: [_clean(d) for d in v] for k, v in payload.items()}
            with open(os.path.join(out_dir, "backup.json"), "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, default=str)
            page.open(ft.AlertDialog(
                modal=True,
                title=ft.Text("✅ Respaldo exportado correctamente"),
                content=ft.Text(f"El respaldo se generó en: {out_dir}\n¿Desea abrir la carpeta de respaldos para revisar el archivo?"),
                actions=[
                    ft.TextButton("Abrir carpeta", on_click=lambda e: os.startfile(out_dir)),
                    ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))
                ],
            ))
            page.update()
        except Exception as ex:
            page.open(ft.AlertDialog(title=ft.Text("Error exportando"), content=ft.Text(str(ex)), modal=True))
        finally:
            try:
                session.close()
            except Exception:
                pass
            page.update()

    def import_backup(_):
        path = backup_dir_tf.value or "storage/backups/backup.json"
        if not path.strip():
            page.open(ft.AlertDialog(
                modal=True,
                title=ft.Text("Error de validación"),
                content=ft.Text("Debe especificar la ruta del respaldo a importar."),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
            ))
            return
        if not os.path.exists(path):
            page.open(ft.AlertDialog(
                modal=True,
                title=ft.Text("Archivo no encontrado"),
                content=ft.Text(f"No se encontró el archivo: {path}"),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
            ))
            return
        def confirmar_importacion(_):
            path_local = backup_dir_tf.value or "storage/backups/backup.json"
            try:
                with open(path_local, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = SessionLocal()
                def _upsert(model, rows, keys):
                    for r in rows:
                        filt = [getattr(model, k) == r.get(k) for k in keys]
                        exist = session.execute(select(model).where(*filt)).scalar_one_or_none()
                        if not exist:
                            obj = model(**{k: r.get(k) for k in r.keys()})
                            session.add(obj)
                _upsert(models.Rol, data.get("roles", []), ["id_rol"])
                _upsert(models.Usuario, data.get("usuarios", []), ["id_usuario"])
                _upsert(models.Ciudadano, data.get("ciudadanos", []), ["id_ciudadano"])
                _upsert(models.Documento, data.get("documentos", []), ["id_documento"])
                _upsert(models.DatosServicioMilitar, data.get("servicios", []), ["id_servicio"])
                for r in data.get("ciudadano_documento", []):
                    exist = session.execute(select(models.CiudadanoDocumento).where((models.CiudadanoDocumento.id_ciudadano == r.get("id_ciudadano")) & (models.CiudadanoDocumento.id_documento == r.get("id_documento")))).first()
                    if not exist:
                        session.add(models.CiudadanoDocumento(id_ciudadano=r.get("id_ciudadano"), id_documento=r.get("id_documento")))
                for r in data.get("documento_servicio", []):
                    exist = session.execute(select(models.DocumentoServicio).where((models.DocumentoServicio.id_documento == r.get("id_documento")) & (models.DocumentoServicio.id_servicio == r.get("id_servicio")))).first()
                    if not exist:
                        session.add(models.DocumentoServicio(id_documento=r.get("id_documento"), id_servicio=r.get("id_servicio")))
                session.commit()
                dlg2 = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Respaldo importado"),
                    content=ft.Text(f"Respaldo restaurado desde: {os.path.basename(path_local)}"),
                    actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg2))],
                )
                page.dialog = dlg2
                dlg2.open = True
            except Exception as ex:
                page.dialog = ft.AlertDialog(title=ft.Text("Error importando"), content=ft.Text(str(ex)), modal=True)
                page.dialog.open = True
            finally:
                try:
                    session.close()
                except Exception:
                    pass
                page.update()
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar importación de respaldo"),
            content=ft.Text(f"¿Está seguro de importar el respaldo desde: {os.path.basename(backup_dir_tf.value or 'storage/backups/backup.json')}? Esta acción puede sobrescribir datos existentes."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(e.control.parent)),
                ft.FilledButton("Importar", icon=ft.Icons.UPLOAD, on_click=confirmar_importacion)
            ],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def migrate_database(_):
        url = (target_db_tf.value or "").strip()
        if not url:
            page.open(ft.AlertDialog(
                modal=True,
                title=ft.Text("Falta información"),
                content=ft.Text("Ingrese DATABASE_URL destino para migrar la base de datos."),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
            ))
            return
    def confirmar_migracion(_):
        url_local = (target_db_tf.value or "").strip()
        try:
            eng = create_engine(url_local, future=True)
            models.Base.metadata.create_all(eng)
            TargetSession = sessionmaker(bind=eng, autocommit=False, autoflush=False)
            src = SessionLocal(); dst = TargetSession()
            def _copy(model):
                rows = src.execute(select(model)).scalars().all()
                for r in rows:
                    data = {c.name: getattr(r, c.name) for c in model.__table__.columns}
                    pk_cols = [c.name for c in model.__table__.primary_key.columns]
                    filt = [getattr(model, k) == data.get(k) for k in pk_cols]
                    ex = dst.execute(select(model).where(*filt)).scalar_one_or_none()
                    if not ex:
                        dst.add(model(**data))
            for m in [models.MotivoBaja, models.UnidadMilitar, models.Grado, models.Rol, models.Usuario, models.Documento, models.Ciudadano, models.DatosServicioMilitar]:
                _copy(m)
            for m in [models.CiudadanoDocumento, models.DocumentoServicio]:
                _copy(m)
            dst.commit()
            try:
                src.close(); dst.close()
            except Exception:
                pass
            dlg2 = ft.AlertDialog(
                modal=True,
                title=ft.Text("Migración completada"),
                content=ft.Text("La base de datos fue migrada correctamente."),
                actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg2))],
            )
            page.dialog = dlg2
            dlg2.open = True
            page.update()
        except Exception as ex:
            page.dialog = ft.AlertDialog(title=ft.Text("Error migrando"), content=ft.Text(str(ex)), modal=True)
            page.dialog.open = True
            page.update()
    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Confirmar migración de base de datos"),
        content=ft.Text(f"¿Está seguro de migrar la base de datos al destino indicado? Esta acción puede sobrescribir datos existentes."),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: page.close(e.control.parent)),
            ft.FilledButton("Migrar", icon=ft.Icons.MOVE_UP, on_click=confirmar_migracion)
        ],
    )
    page.dialog = dlg
    dlg.open = True
    page.update()

    def purge_trash(_):
        # Vaciar solo la Papelera (.trash)
        err = ft.Text("", size=12, color=ft.Colors.RED_600)
        trash_dir = os.path.join("storage", "data", ".trash")
        temp_dir = os.path.join("storage", "data", "temp")
        archivos_trash = os.listdir(trash_dir) if os.path.exists(trash_dir) else []
        archivos_temp = os.listdir(temp_dir) if os.path.exists(temp_dir) else []

        def do_purge(_):
            temp_dir = os.path.join("storage", "data", "temp")
            trash_dir = os.path.join("storage", "data", ".trash")
            archivos_temp = os.listdir(temp_dir) if os.path.exists(temp_dir) else []
            archivos_trash = os.listdir(trash_dir) if os.path.exists(trash_dir) else []
            def confirmar_cache(_):
                try:
                    for d in [temp_dir, trash_dir]:
                        if os.path.exists(d):
                            for name in os.listdir(d):
                                p = os.path.join(d, name)
                                try:
                                    if os.path.isfile(p) or os.path.islink(p):
                                        os.unlink(p)
                                    elif os.path.isdir(p):
                                        shutil.rmtree(p)
                                except Exception:
                                    pass
                    dlg2 = ft.AlertDialog(
                        modal=True,
                        title=ft.Text("Caché y Papelera liberadas"),
                        content=ft.Text("Se liberaron los archivos temporales y la papelera."),
                        actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(e.control.parent))],
                    )
                    page.open(dlg2)
                    page.update()
                except Exception as ex:
                    page.dialog = ft.AlertDialog(title=ft.Text("Error limpiando"), content=ft.Text(str(ex)), modal=True)
                    page.dialog.open = True
                    page.update()
        # Construir lista interactiva de archivos
        trash_list = ft.Column([
            ft.Text(f"• {name}", size=13) for name in archivos_trash
        ]) if archivos_trash else ft.Text("No hay documentos en la papelera para eliminación definitiva.", size=13, color=ft.Colors.BLUE_GREY_600)

        dlg = ft.AlertDialog(
            title=ft.Text("Eliminación Definitiva de Documentos"),
            content=ft.Column([
                ft.Text("Documentos en papelera a eliminar definitivamente:", size=15, weight=ft.FontWeight.BOLD),
                trash_list,
                ft.Divider(),
                ft.Text("¿Está seguro de eliminar estos documentos de forma permanente? Esta acción no se puede deshacer.", size=13, color=ft.Colors.RED_700) if archivos_trash else ft.Text("Nada que eliminar.", size=13, color=ft.Colors.GREEN_700)
            ], tight=True, spacing=8),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(e.control.parent)),
                ft.FilledButton("Eliminar definitivamente", icon=ft.Icons.DELETE_FOREVER, on_click=do_purge, disabled=not archivos_trash)
            ],
            modal=True
        )
        page.open(dlg)
        page.update()

    # Wire filtros
    filter_tf.on_change = load_logs
    date_from_tf.on_change = load_logs
    date_to_tf.on_change = load_logs
    type_dd.on_change = load_logs


    audit_filters = ft.Column([
        ft.Row([
            ft.Text("Historial de Auditoría", size=22, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            count_badge,
            ft.Container(expand=True),
            ft.IconButton(icon=ft.Icons.REFRESH, tooltip="Actualizar", on_click=load_logs),
            ft.OutlinedButton("Exportar Excel", icon=ft.Icons.DOWNLOAD, on_click=export_csv),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([filter_tf, type_dd], spacing=10),
        ft.Row([date_from_tf, date_to_tf, ft.FilledButton("Aplicar", icon=ft.Icons.FILTER_ALT, on_click=load_logs)], spacing=10),
    ], spacing=8)
    audit_list = ft.Container(content=ft.ListView(ref=list_ref, expand=True, spacing=0, padding=0), expand=True, bgcolor=ft.Colors.GREY_50, border_radius=10, padding=12, height=680)
    pager = ft.Row([
        ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=lambda e: (state.update({"page_index": max(0, state["page_index"]-1)}), _rebuild_list())),
        pager_label,
        ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=lambda e: (state.update({"page_index": state["page_index"]+1}), _rebuild_list())),
    ], alignment=ft.MainAxisAlignment.CENTER, spacing=16)

    left = ft.Column([audit_filters, audit_list, pager, ft.Row([status], alignment=ft.MainAxisAlignment.END)], expand=True, spacing=12)

    # Layout derecha (Acciones)
    actions = ft.Column([
        ft.Text("Acciones Administrativas", size=18, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
        ft.Container(height=6),
        backup_dir_tf,
        ft.Row([
            ft.FilledButton("Exportar respaldo", icon=ft.Icons.SAVE_ALT, on_click=export_backup),
            ft.OutlinedButton("Importar respaldo", icon=ft.Icons.UPLOAD, on_click=import_backup),
        ], spacing=10),
        ft.Divider(),
        target_db_tf,
        ft.FilledButton("Migrar base de datos", icon=ft.Icons.MOVE_UP, on_click=migrate_database),
        ft.Divider(),
    ft.OutlinedButton("Liberar caché", icon=ft.Icons.CLEAR_ALL, on_click=clear_cache),
    ft.OutlinedButton("Eliminación Definitiva", icon=ft.Icons.DELETE_FOREVER, style=ft.ButtonStyle(color=ft.Colors.RED_700), on_click=purge_trash),
    ], width=420, spacing=12)

    root = ft.Column([
        ft.Text("🛠️ Backups, Auditoría y Administración", size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
        ft.Container(height=12),
        ft.Row([
            ft.Container(content=left, expand=True, bgcolor=CARD_BG, border_radius=10, padding=12),
            ft.Container(width=16),
            ft.Container(content=actions, bgcolor=CARD_BG, border_radius=10, padding=12),
        ], expand=True),
    ], expand=True)

    # Carga inicial diferida para evitar error "ListView must be added first"
    try:
        if hasattr(page, "run_task"):
            async def _initial():
                await asyncio.sleep(0.05)
                load_logs()
            page.run_task(_initial())
        else:
            # Fallback: simple llamada (puede funcionar si mount ya ocurrió)
            load_logs()
    except Exception:
        pass
    return root
