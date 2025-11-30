"""Vista Flet para gestión de usuarios y roles.

Incluye:
 - Búsqueda de usuarios
 - Tabla paginada
 - Creación / edición / eliminación
 - Gestión de roles
"""
import flet as ft
from .users_controller import UserService, validate_password
from database.connection import SessionLocal
from database import models
from sqlalchemy import select
from .layout import PRIMARY_COLOR, ACCENT_COLOR, BG_COLOR, CARD_BG


def create_users_view(page: ft.Page, user_data: dict | None = None) -> ft.Control:
    svc = UserService()

    search_ref = ft.Ref[ft.TextField]()
    table_ref = ft.Ref[ft.DataTable]()
    status_text = ft.Ref[ft.Text]()
    activity_list_ref = ft.Ref[ft.ListView]()
    detail_title_ref = ft.Ref[ft.Text]()
    detail_role_ref = ft.Ref[ft.Text]()

    rows_cache = []
    selected_user_id: int | None = None

    # ---- Permisos por rol (4 niveles) ----
    # Administrador > Editor > Operador > Consulta
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
        return _norm_role((user_data or {}).get("rol", "")) == "administrador"
    def can_edit_users() -> bool:
        return _norm_role((user_data or {}).get("rol", "")) in ("administrador", "editor")
    def can_delete_users() -> bool:
        return _norm_role((user_data or {}).get("rol", "")) == "administrador"

    def load(q: str | None = None):
        nonlocal rows_cache
        try:
            users = svc.list_users(q)
            rows_cache = []
            role_map = svc.get_role_map()
            columns = [
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Usuario")),
                ft.DataColumn(ft.Text("Apellido")),
                ft.DataColumn(ft.Text("Rol")),
                ft.DataColumn(ft.Text("Acciones")),
            ]
            if table_ref.current:
                table_ref.current.columns = columns
            svc.seed_default_roles()
            role_map = svc.get_role_map() or role_map
            for u in users:
                action_row = ft.Row([
                    ft.IconButton(icon=ft.Icons.EDIT, tooltip="Editar", on_click=(lambda e, uid=u.id_usuario: open_edit(uid)), disabled=not can_edit_users(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))),
                    ft.IconButton(icon=ft.Icons.DELETE_FOREVER, tooltip="Eliminar", icon_color=ft.Colors.RED_700, on_click=(lambda e, uid=u.id_usuario: open_delete(uid)), disabled=not can_delete_users(), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))),
                ], spacing=4)

                rows_cache.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(u.id_usuario))),
                            ft.DataCell(ft.Text(u.nombre_usuario)),
                            ft.DataCell(ft.Text(u.apellidos or "")),
                            ft.DataCell(ft.Text(role_map.get(u.id_rol, f"Rol {u.id_rol}"))),
                            ft.DataCell(action_row),
                        ],
                        on_select_changed=lambda e, uid=u.id_usuario: select_user(uid)
                    )
                )
            if table_ref.current:
                table_ref.current.rows = rows_cache
            if status_text.current:
                status_text.current.value = f"{len(users)} usuario(s) encontrados"
            # Actualiza toda la página si ya está montada
            if getattr(page, "update", None):
                page.update()
        except Exception as exc:
            if status_text.current:
                status_text.current.value = f"Error: {exc}"
            if getattr(page, "update", None):
                page.update()

    def do_search(e: ft.ControlEvent):
        load(search_ref.current.value.strip())

    def select_user(uid: int):
        nonlocal selected_user_id
        selected_user_id = uid
        # Cargar detalles y actividad
        try:
            user = next((r for r in svc.list_users() if r.id_usuario == uid), None)
            if detail_title_ref.current and user:
                detail_title_ref.current.value = f"👤 {user.nombre_usuario} (#{user.id_usuario})"
            if detail_role_ref.current and user:
                rmap = svc.get_role_map()
                detail_role_ref.current.value = f"Rol: {rmap.get(user.id_rol, user.id_rol)}"
            acts = svc.get_user_activity(uid, limit=25)
            if activity_list_ref.current is not None:
                activity_list_ref.current.controls = [
                    ft.ListTile(
                        leading=ft.Icon(a.get("icon", ft.Icons.HISTORY), color=ACCENT_COLOR),
                        title=ft.Text(a.get("title", ""), weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(_fmt_ts(a.get("ts")) + "  •  " + a.get("subtitle", ""), size=12, color=ft.Colors.BLUE_GREY_600),
                        dense=True,
                    )
                    for a in acts
                ]
            if getattr(page, "update", None):
                page.update()
        except Exception as exc:
            if status_text.current:
                status_text.current.value = f"Error cargando detalle: {exc}"
            if getattr(page, "update", None):
                page.update()

    def open_create(_: ft.ControlEvent):
        if not can_edit_users():
            page.dialog = ft.AlertDialog(title=ft.Text("Sin permisos"), content=ft.Text("Solo Administrador o Editor pueden crear usuarios."), modal=True)
            page.dialog.open = True
            page.update()
            return
        tf_user = ft.TextField(label="Nombre de usuario", autofocus=True, width=260)
        tf_dni = ft.TextField(label="DNI", width=180)
        tf_apellidos = ft.TextField(label="Apellidos", width=220)
        tf_nombres = ft.TextField(label="Nombres", width=220)
        # Selector de rol predefinido
        role_map = svc.get_role_map()
        if not role_map:
            svc.seed_default_roles()
            role_map = svc.get_role_map()
        role_names = [role_map[rid] for rid in sorted(role_map.keys())]
        dd_role = ft.Dropdown(
            label="Rol",
            options=[ft.dropdown.Option(name) for name in role_names],
            width=260,
        )
        tf_pass = ft.TextField(label="Contraseña", password=True, can_reveal_password=True, width=260)
        msg = ft.Text("", size=12, color=ft.Colors.RED_600)

        def submit(_):
            probs = validate_password(tf_pass.value or "")
            if probs:
                msg.value = " | ".join(probs); msg.update(); return
            try:
                svc.create_user(tf_user.value, tf_pass.value, dd_role.value or "", apellidos=tf_apellidos.value, nombres=tf_nombres.value)
                page.close(dlg)
                load(search_ref.current.value.strip())
            except Exception as exc:
                msg.value = str(exc); msg.update()

        detalle = ft.Row([
            ft.Container(tf_dni, width=110),
            ft.Container(tf_apellidos, width=140),
            ft.Container(tf_nombres, width=140)
        ], spacing=6)

        dlg = ft.AlertDialog(
            title=ft.Text("Crear Usuario", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(tf_user, width=180),
                        ft.Container(dd_role, width=180)
                    ], spacing=6),
                    detalle,
                    ft.Container(tf_pass, width=180),
                    msg
                ], tight=True, spacing=8),
                width=445,  # 370 + 75px ≈ 2cm más
                padding=ft.padding.symmetric(vertical=10, horizontal=12),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.FilledButton("Crear", icon=ft.Icons.PERSON_ADD, on_click=submit),
            ],
            modal=True,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=10),
            inset_padding=ft.padding.all(8),
        )
        page.open(dlg)

    def open_edit(user_id: int):
        if not can_edit_users():
            page.dialog = ft.AlertDialog(title=ft.Text("Sin permisos"), content=ft.Text("Solo Administrador o Editor pueden editar usuarios."), modal=True)
            page.dialog.open = True
            page.update()
            return
        user = next((r for r in svc.list_users() if r.id_usuario == user_id), None)
        if not user:
            return
        # Selector de rol reducido
        rmap = svc.get_role_map()
        if not rmap:
            svc.seed_default_roles()
            rmap = svc.get_role_map()
        role_names = [rmap[rid] for rid in sorted(rmap.keys())]
        tf_apellidos = ft.TextField(label="Apellidos", value=user.apellidos or "", width=220)
        tf_nombres = ft.TextField(label="Nombres", value=user.nombres or "", width=220)
        dd_role = ft.Dropdown(label="Rol", options=[ft.dropdown.Option(n) for n in role_names], value=rmap.get(user.id_rol), width=260)
        tf_pass = ft.TextField(label="Nueva contraseña (opcional)", password=True, can_reveal_password=True, width=260)
        msg = ft.Text("", size=12, color=ft.Colors.RED_600)

        def submit(_):
            new_role = dd_role.value.strip() if dd_role.value else None
            new_pass = tf_pass.value.strip() or None
            new_apellidos = tf_apellidos.value.strip() or None
            new_nombres = tf_nombres.value.strip() or None
            if new_pass:
                probs = validate_password(new_pass)
                if probs:
                    msg.value = " | ".join(probs); msg.update(); return
            try:
                # Actualizar apellidos y nombres si el modelo/controlador lo permite
                svc.update_user(user_id, rol_nombre=new_role, nueva_contrasena=new_pass)
                user.apellidos = new_apellidos
                user.nombres = new_nombres
                page.close(dlg)
                load(search_ref.current.value.strip())
            except Exception as exc:
                msg.value = str(exc); msg.update()

        detalle = ft.Row([
            ft.Container(tf_apellidos, width=140),
            ft.Container(tf_nombres, width=140)
        ], spacing=6)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Editar Usuario #{user_id}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"Usuario: {user.nombre_usuario}", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_700),
                    detalle,
                    ft.Container(dd_role, width=180),
                    ft.Container(tf_pass, width=180),
                    msg,
                ], spacing=8, tight=True),
                width=370,
                padding=ft.padding.symmetric(vertical=10, horizontal=12),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.FilledButton("Guardar", icon=ft.Icons.SAVE, on_click=submit),
            ],
            modal=True,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=10),
            inset_padding=ft.padding.all(8),
        )
        page.open(dlg)

    def open_delete(user_id: int):
        if not is_admin():
            page.dialog = ft.AlertDialog(title=ft.Text("Sin permisos"), content=ft.Text("Solo el administrador puede eliminar usuarios."), modal=True)
            page.dialog.open = True
            page.update()
            return
        user = next((r for r in svc.list_users() if r.id_usuario == user_id), None)
        if not user:
            return
        txt = ft.Text(f"¿Eliminar usuario '{user.nombre_usuario}' (ID {user.id_usuario})?\nApellidos: {user.apellidos or ''}\nNombres: {user.nombres or ''}\nEsta acción es irreversible.")
        err = ft.Text("", color=ft.Colors.RED_600, size=12)

        def do_delete(_):
            try:
                svc.delete_user(user_id)
                page.close(dlg)
                load(search_ref.current.value.strip())
            except Exception as exc:
                err.value = str(exc); err.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar Eliminación", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt, err], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dlg)),
                ft.FilledButton("Eliminar", icon=ft.Icons.DELETE_FOREVER, on_click=do_delete, bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
            ],
            modal=True,
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
            inset_padding=ft.padding.all(16),
        )
        page.open(dlg)

    # Historial de auditoría removido de Gestión de Usuarios; ahora se encuentra en el módulo de Backups.

    def open_roles_legend(_):
        # Contenido de la leyenda en un diálogo para no ocupar espacio permanente
        legend = ft.Column([
            ft.Text("Roles y permisos", size=20, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ft.Container(height=8),
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, color=ACCENT_COLOR, size=20),
                    ft.Text("Administrador", size=14, weight=ft.FontWeight.W_600),
                ], spacing=8),
                ft.Text("Control total: crear/editar/eliminar usuarios y datos, ver auditoría", size=12, color=ft.Colors.BLUE_GREY_700),
                ft.Divider(height=10),
                ft.Row([
                    ft.Icon(ft.Icons.EDIT, color=ACCENT_COLOR, size=20),
                    ft.Text("Editor", size=14, weight=ft.FontWeight.W_600),
                ], spacing=8),
                ft.Text("Gestiona datos (crear/editar), sin eliminar usuarios", size=12, color=ft.Colors.BLUE_GREY_700),
                ft.Divider(height=10),
                ft.Row([
                    ft.Icon(ft.Icons.BUILD, color=ACCENT_COLOR, size=20),
                    ft.Text("Operador", size=14, weight=ft.FontWeight.W_600),
                ], spacing=8),
                ft.Text("Digitaliza/adjunta documentos, sin modificar roles ni eliminar", size=12, color=ft.Colors.BLUE_GREY_700),
                ft.Divider(height=10),
                ft.Row([
                    ft.Icon(ft.Icons.VISIBILITY, color=ACCENT_COLOR, size=20),
                    ft.Text("Consulta", size=14, weight=ft.FontWeight.W_600),
                ], spacing=8),
                ft.Text("Solo lectura y búsqueda", size=12, color=ft.Colors.BLUE_GREY_700),
            ], spacing=6),
        ], tight=True, spacing=6)

        dlg = ft.AlertDialog(
            modal=True,
            content=legend,
            actions=[ft.TextButton("Cerrar", on_click=lambda e: page.close(dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
            inset_padding=ft.padding.all(16),
        )
        page.open(dlg)

    header = ft.Container(
        bgcolor=CARD_BG,
        border_radius=10,
        padding=15,
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.PERSON_4, color=ACCENT_COLOR),
                ft.Text("Gestión de Usuarios", size=22, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ], spacing=10),
            ft.Container(expand=True),
            # Leyenda de roles accesible como diálogo, para no ocupar espacio vertical.
            ft.IconButton(icon=ft.Icons.INFO_OUTLINE, tooltip="Roles y permisos", on_click=open_roles_legend),
            # Historial de auditoría movido al módulo de Backups / Administración.
            ft.ElevatedButton("Crear", icon=ft.Icons.PERSON_ADD, on_click=open_create, disabled=not can_edit_users()),
            ft.TextField(ref=search_ref, hint_text="Buscar usuario...", width=260, on_submit=do_search),
            ft.IconButton(icon=ft.Icons.SEARCH, tooltip="Buscar", on_click=do_search),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    right_panel = ft.Container(
        bgcolor=CARD_BG,
        border_radius=10,
        padding=15,
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.HISTORY, color=ACCENT_COLOR),
                ft.Text(ref=detail_title_ref, value="Selecciona un usuario", size=18, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ], spacing=8),
            ft.Text(ref=detail_role_ref, value="", size=12, color=ft.Colors.BLUE_GREY_600),
            ft.Divider(),
            ft.Text("Historial reciente", size=14, weight=ft.FontWeight.W_600, color=PRIMARY_COLOR),
            ft.ListView(ref=activity_list_ref, expand=True, spacing=2, padding=0),
        ], expand=True),
        expand=3,
    )

    # Tabla principal de usuarios
    table = ft.DataTable(
        ref=table_ref,
        columns=[
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Usuario")),
            ft.DataColumn(ft.Text("Apellido")),
            ft.DataColumn(ft.Text("Rol")),
            ft.DataColumn(ft.Text("Acciones")),
        ],
        rows=[],
        heading_row_color=ft.Colors.BLUE_GREY_50,
        divider_thickness=0.3,
        column_spacing=14,
        heading_row_height=32,
        border_radius=6,
        width=420,
        bgcolor=ft.Colors.WHITE,
        # shadow eliminado porque DataTable no lo soporta
    )

    left_panel = ft.Container(content=table, expand=3, bgcolor=CARD_BG, border_radius=10, padding=10)
    body = ft.Row([left_panel, ft.Container(width=16), right_panel], expand=True)

    root_column = ft.Column([
        header,
        ft.Container(height=12),
        body,
        ft.Container(height=8),
        ft.Text(ref=status_text, value="", size=12, color=ft.Colors.BLUE_GREY_600),
    ], expand=True)

    root = ft.Container(content=root_column, bgcolor=BG_COLOR, padding=10, expand=True)

    def _fmt_ts(ts):
        try:
            import datetime
            if ts is None:
                return ""
            if isinstance(ts, (int, float)):
                dt = datetime.datetime.fromtimestamp(ts)
            else:
                dt = ts
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ""

    # Cargar datos iniciales de forma segura (sin forzar update de controles no montados)
    load(None)
    return root
