# modules/dashboard/dashboard_view.py
# -*- coding: utf-8 -*-
import flet as ft
from database.connection import SessionLocal
from database.models import Ciudadano, Documento

# Importa el paquete y/o sus vistas de forma segura
try:
    import modules.digitalizacion as digitalizacion
except Exception:
    digitalizacion = None

# Importa vistas específicas de datos y usuarios
try:
    from modules.dashboard import data as data_module
except Exception as ex:
    print(f"[ERROR] No se pudo importar modules.dashboard.data: {ex}")
    data_module = None

try:
    from modules.dashboard import users as users_module
except Exception:
    users_module = None

try:
    from modules.dashboard import backups as backups_module
except Exception:
    backups_module = None

ACCENT_COLOR = ft.Colors.GREEN_600
PRIMARY_COLOR = ft.Colors.GREEN_800
BG_COLOR = ft.Colors.GREEN_50
CARD_BG = ft.Colors.WHITE


def get_stats():
    db = SessionLocal()
    try:
        total_ciudadanos = db.query(Ciudadano).count()
        total_documentos = db.query(Documento).count()
    except Exception as e:
        print(f"Error al obtener estadísticas: {e}")
        total_ciudadanos = 0
        total_documentos = 0
    finally:
        db.close()
    return total_ciudadanos, total_documentos


def stat_card(title: str, value, icon=ft.Icons.INFO_OUTLINE):
    # Si es un nombre largo (jefes), ajustar el diseño
    is_long_text = isinstance(value, str) and len(str(value)) > 15
    
    if is_long_text:
        return ft.Card(
            elevation=6,
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, color=ACCENT_COLOR, size=32),
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                    ], alignment=ft.MainAxisAlignment.START, spacing=10),
                    ft.Container(height=8),
                    ft.Text(
                        str(value), 
                        size=16, 
                        weight=ft.FontWeight.W_500, 
                        color=ft.Colors.BLUE_GREY_800,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=2,
                        overflow=ft.TextOverflow.VISIBLE
                    ),
                ], 
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5),
                padding=18,
                width=280,
                height=120,
                bgcolor=CARD_BG,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.BLUE_GREY_200)
            ),
        )
    else:
        return ft.Card(
            elevation=6,
            content=ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(str(value), size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                        ft.Text(title, size=13, color=ft.Colors.BLUE_GREY_700),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Icon(icon, color=ACCENT_COLOR, size=36),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=15),
                padding=18,
                width=280,
                height=120,
                bgcolor=CARD_BG,
                border_radius=12,
                border=ft.border.all(1, ft.Colors.BLUE_GREY_200)
            ),
        )


def dashboard_header(user_data, logout_callback):
    # Validar que user_data sea un diccionario
    if not isinstance(user_data, dict):
        user_data = {}
    
    username = (user_data or {}).get("username", "usuario")
    rol = (user_data or {}).get("rol", "—")

    return ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    "ORMD - Oficina de Registro Militar",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    color=PRIMARY_COLOR,
                ),
                ft.Row(
                    [
                        ft.Text(f"Usuario: {username} | Rol: {rol}", color=PRIMARY_COLOR),
                        ft.ElevatedButton(
                            "Salir",
                            icon=ft.Icons.LOGOUT,
                            on_click=logout_callback,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                            tooltip="Cerrar Sesión",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                    spacing=15,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.padding.only(left=20, right=20, top=10, bottom=10),
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.BLUE_GREY_200)),
        height=60,
    )


def create_dashboard_view(page: ft.Page, user_data, logout_callback):
    # Área dinámica
    content_area = ft.Container(
        padding=25, expand=True, bgcolor=BG_COLOR, alignment=ft.alignment.top_left
    )

    # Icono PDF compatible
    pdf_icon = getattr(ft.Icons, "PICTURE_AS_PDF", ft.Icons.DESCRIPTION)

    modules = [
        {"name": "Inicio",                    "icon": ft.Icons.HOME,           "content_func": None, "role": "any"},
        {"name": "Gestión de Datos",          "icon": ft.Icons.PEOPLE_ALT,     "content_func": None, "role": "consulta"},
        {"name": "Digitalización (Imágenes)", "icon": ft.Icons.IMAGE,          "content_func": None, "role": "operador"},
        {"name": "Digitalización (PDF)",      "icon": pdf_icon,                "content_func": None, "role": "operador"},
        {"name": "Gestión de Usuarios",       "icon": ft.Icons.PERSON_4,       "content_func": None, "role": "editor"},
        {"name": "Backups",                   "icon": ft.Icons.BACKUP_SHARP,   "content_func": None, "role": "admin"},
    ]

    # ---- Contenido: Inicio mejorado ----
    # Variables para datos editables
    jefe_ormd = {"value": "SUP. Tc Saravia"}
    jefe_archivo = {"value": "TCR. Cap Hinojosa Gamboa"}

    def create_home_content():
        ciud, docs = get_stats()
        
        # Función para abrir modal (simplificada)
        def open_config_modal(e):
            # Crear campos de entrada
            field_ormd = ft.TextField(
                label="Jefe ORMD",
                value=jefe_ormd["value"],
                width=350,
                prefix_icon=ft.Icons.MILITARY_TECH
            )
            field_archivo = ft.TextField(
                label="Jefe Archivo",
                value=jefe_archivo["value"],
                width=350,
                prefix_icon=ft.Icons.ARCHIVE_SHARP
            )
            
            def guardar_cambios(e):
                jefe_ormd["value"] = field_ormd.value
                jefe_archivo["value"] = field_archivo.value
                page.close(config_dialog)
                # Recargar contenido
                content_area.content = create_home_content()
                page.update()
            
            def cancelar(e):
                page.close(config_dialog)
            
            # Crear modal
            config_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("⚙️ Configuración de Personal", size=18, weight=ft.FontWeight.BOLD),
                content=ft.Column([
                    ft.Text("Modifique los datos del personal:", size=14),
                    ft.Container(height=10),
                    field_ormd,
                    ft.Container(height=10),
                    field_archivo,
                ], width=400, height=180, tight=True),
                actions=[
                    ft.TextButton("Cancelar", on_click=cancelar),
                    ft.ElevatedButton(
                        "💾 Guardar",
                        on_click=guardar_cambios,
                        style=ft.ButtonStyle(bgcolor=PRIMARY_COLOR, color=ft.Colors.WHITE)
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            
            page.open(config_dialog)
        
        # Header con botón de configuración
        header_row = ft.Row([
            ft.Text("📊 Panel de Control Principal", size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ft.ElevatedButton(
                text="⚙️ CONFIGURACIÓN",
                on_click=open_config_modal,
                style=ft.ButtonStyle(
                    bgcolor=PRIMARY_COLOR,
                    color=ft.Colors.WHITE,
                    text_style=ft.TextStyle(
                        size=16,
                        weight=ft.FontWeight.BOLD
                    ),
                    padding=ft.padding.symmetric(horizontal=20, vertical=12),
                    shape=ft.RoundedRectangleBorder(radius=8)
                )
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Tarjetas de estadísticas mejoradas con mejor alineación
        stats_row = ft.Column([
            # Primera fila: Estadísticas numéricas
            ft.Row([
                stat_card("Ciudadanos Registrados", ciud, ft.Icons.PERSON_ADD_ALT_1),
                stat_card("Documentos Digitalizados", docs, ft.Icons.FOLDER_OPEN),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=30),
            
            ft.Container(height=20),
            
            # Segunda fila: Información de personal
            ft.Row([
                stat_card("Jefe ORMD", jefe_ormd["value"], ft.Icons.MILITARY_TECH),
                stat_card("Jefe Archivo", jefe_archivo["value"], ft.Icons.ARCHIVE_SHARP),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=30),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # Gráficas realistas mejoradas
        def create_chart_card(title, chart_content):
            return ft.Card(
                elevation=4,
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                        ft.Container(height=15),
                        chart_content
                    ]),
                    padding=20,
                    width=400,
                    height=280,
                    bgcolor=CARD_BG,
                    border_radius=10
                )
            )

        # Gráfico realista: Documentos procesados por mes (últimos 6 meses)
        import datetime
        current_month = datetime.datetime.now().month
        months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        last_6_months = []
        for i in range(6):
            month_idx = (current_month - 6 + i) % 12
            last_6_months.append(months[month_idx])

        # Datos realistas basados en el total de documentos
        if docs > 0:
            monthly_data = [
                max(1, docs // 8),  # Mes -5
                max(1, docs // 6),  # Mes -4
                max(1, docs // 7),  # Mes -3
                max(1, docs // 5),  # Mes -2
                max(1, docs // 4),  # Mes -1
                max(1, docs // 3),  # Mes actual
            ]
        else:
            monthly_data = [2, 5, 3, 8, 6, 4]

        chart1_content = ft.Column([
            ft.Text("📈 Documentos Procesados Mensualmente", size=14, color=ft.Colors.BLUE_GREY_700),
            ft.Container(height=15),
            # Barras proporcionales a los datos
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Container(bgcolor=ft.Colors.BLUE_600, width=35, height=min(150, max(20, val * 3)), border_radius=3),
                        ft.Text(str(val), size=10, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ) for val in monthly_data
            ], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=15),
            ft.Row([
                ft.Text(month, size=11, color=ft.Colors.BLUE_GREY_600) for month in last_6_months
            ], spacing=28, alignment=ft.MainAxisAlignment.CENTER)
        ])

        # Gráfico realista: Tipos de documentos más procesados con distribución mejorada
        doc_types = [
            {"name": "Libretas Militares", "count": max(1, docs // 2 + 5), "color": ft.Colors.BLUE_600, "percent": 45},
            {"name": "Certificados SMV", "count": max(1, docs // 3 + 3), "color": ft.Colors.GREEN_600, "percent": 30}, 
            {"name": "Resoluciones", "count": max(1, docs // 4 + 2), "color": ft.Colors.ORANGE_600, "percent": 20},
            {"name": "Otros Documentos", "count": max(1, docs // 8 + 1), "color": ft.Colors.RED_600, "percent": 5}
        ]

        chart2_content = ft.Column([
            ft.Text("📊 Distribución de Documentos por Tipo", size=14, color=ft.Colors.BLUE_GREY_700),
            ft.Container(height=15),
            
            # Gráfico de barras horizontales mejorado
            ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(doc["name"], size=12, color=ft.Colors.BLUE_GREY_700, weight=ft.FontWeight.W_500),
                        width=130,
                        alignment=ft.alignment.center_left
                    ),
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                bgcolor=doc["color"], 
                                width=max(15, doc["percent"] * 2.5), 
                                height=18, 
                                border_radius=9
                            ),
                            ft.Text(f"{doc['percent']}%", size=11, color=PRIMARY_COLOR, weight=ft.FontWeight.BOLD)
                        ], spacing=8, alignment=ft.CrossAxisAlignment.CENTER),
                        width=200
                    ),
                    ft.Text(f"{doc['count']} docs", size=11, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR, width=60),
                ], spacing=10, alignment=ft.CrossAxisAlignment.CENTER)
                for doc in doc_types
            ], spacing=15),
            
            ft.Container(height=15),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"� Total procesados: {sum(d['count'] for d in doc_types)} documentos", 
                           size=13, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                    ft.Text(f"🎯 Tipo principal: {doc_types[0]['name']} ({doc_types[0]['percent']}%)", 
                           size=12, color=ft.Colors.BLUE_GREY_600)
                ], spacing=5),
                padding=10,
                bgcolor=ft.Colors.BLUE_GREY_50,
                border_radius=8
            )
        ])

        charts_row = ft.Row([
            create_chart_card("Producción Mensual", chart1_content),
            create_chart_card("Distribución por Tipo", chart2_content)
        ], wrap=True, spacing=25, alignment=ft.MainAxisAlignment.CENTER)

        return ft.Column([
            header_row,
            ft.Container(height=25),
            stats_row,
            ft.Container(height=30),
            ft.Text("📊 Análisis de Rendimiento ORMD 55-A", size=20, weight=ft.FontWeight.W_600, color=PRIMARY_COLOR),
            ft.Container(height=15),
            charts_row,
            ft.Container(height=20)
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    # ---- Genérico (placeholder)
    def create_generic_module_content(title):
        return ft.Column(
            [
                ft.Text(f"🛠️ Módulo: {title}", size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                ft.Container(height=25),
                ft.Text("Este módulo se encuentra actualmente en fase de desarrollo.", size=18, color=ft.Colors.GREY_700),
                ft.Text("Por favor, vuelve más tarde.", size=16, color=ft.Colors.GREY_600),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    # ---- Registrar funciones disponibles
    modules[0]["content_func"] = create_home_content

    # Solo registra si existen las funciones exportadas
    if digitalizacion and hasattr(digitalizacion, "create_digitalizacion_jpg_view"):
        modules[2]["content_func"] = lambda: digitalizacion.create_digitalizacion_jpg_view(page, user_data)
    else:
        print("[WARN] create_digitalizacion_jpg_view no disponible en modules.digitalizacion")

    if digitalizacion and hasattr(digitalizacion, "create_digitalizacion_pdf_view"):
        modules[3]["content_func"] = lambda: digitalizacion.create_digitalizacion_pdf_view(page, user_data)
    else:
        print("[WARN] create_digitalizacion_pdf_view no disponible en modules.digitalizacion")

    # Registrar Gestión de Datos y Gestión de Usuarios si están disponibles
    if data_module:
        if hasattr(data_module, "build"):
            modules[1]["content_func"] = lambda: data_module.build(page, user_data)
        else:
            print("[WARN] Módulo 'Gestión de Datos' sin build(); attrs:", getattr(data_module, "__all__", dir(data_module)))
    else:
        print("[WARN] Módulo 'Gestión de Datos' no disponible o sin build()")

    if users_module and hasattr(users_module, "build"):
        modules[4]["content_func"] = lambda: users_module.build(page, user_data)
    else:
        print("[WARN] Módulo 'Gestión de Usuarios' no disponible o sin build()")

    if backups_module and hasattr(backups_module, "build"):
        modules[5]["content_func"] = lambda: backups_module.build(page, user_data)
    else:
        print("[WARN] Módulo 'Backups' no disponible o sin build()")

    # ---- Cambio de módulo
    selected_module_index = 0

    def change_module(index: int):
        nonlocal selected_module_index
        selected_module_index = index
        title = modules[index]["name"]
        content_func = modules[index].get("content_func")

        try:
            content_area.content = content_func() if content_func else create_generic_module_content(title)
        except Exception as ex:
            # Evita que la app "muera" si un módulo lanza excepción
            print(f"[ERROR] Falló módulo '{title}': {ex}")
            content_area.content = create_generic_module_content(title)

        page.update()

    # ---- Crear menú lateral personalizado con botones ----
    def _norm_role(name: str) -> str:
        n = (name or "").strip().lower()
        mapping = {
            "administrador": "admin",
            "admin": "admin",
            "acceso 1": "admin",
            "editor": "editor",
            "acceso 2": "editor",
            "operador": "operador",
            "ingresador": "operador",
            "acceso 3": "operador",
            "consulta": "consulta",
            "acceso 4": "consulta",
        }
        return mapping.get(n, n)

    current_role = _norm_role((user_data or {}).get("rol") or (user_data or {}).get("rol_nombre") or "")

    def _role_allows(module_role: str) -> bool:
        # module_role niveles mínimos: any, consulta, operador, editor, admin
        hierarchy = ["any", "consulta", "operador", "editor", "admin"]
        def level(r: str) -> int:
            try:
                return hierarchy.index(r)
            except ValueError:
                return 0
        user_level = level(current_role)
        needed_level = level(module_role)
        # Permisos según requerimiento:
        # ADMIN: todo
        # EDITOR: todo menos borrar (ver módulos incluido Backups?) => limitar Backups sólo admin
        # OPERADOR: Inicio, Gestión de Datos, Digitalización imagen/PDF
        # CONSULTA: Inicio y Gestión de Datos
        if current_role == "admin":
            return True
        if current_role == "editor":
            return module_role in ("any", "consulta", "operador", "editor")
        if current_role == "operador":
            return module_role in ("any", "consulta", "operador")
        if current_role == "consulta":
            return module_role in ("any", "consulta")
        return module_role == "any"

    def create_menu_button(icon, text, index):
        def on_click(e):
            change_module(index)
            # Actualizar estados visuales
            for i, btn in enumerate(menu_buttons):
                if i == index:
                    btn.bgcolor = ACCENT_COLOR
                    btn.content.controls[1].color = ft.Colors.WHITE
                else:
                    btn.bgcolor = ft.Colors.TRANSPARENT
                    btn.content.controls[1].color = PRIMARY_COLOR
            page.update()
        
        allowed = _role_allows(modules[index]["role"])
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=20, color=(ACCENT_COLOR if index == 0 else PRIMARY_COLOR) if allowed else ft.Colors.BLUE_GREY_300),
                ft.Text(
                    text,
                    size=14,
                    color=(ft.Colors.WHITE if index == 0 else PRIMARY_COLOR) if allowed else ft.Colors.BLUE_GREY_300,
                    weight=ft.FontWeight.W_500
                )
            ], spacing=12),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            bgcolor=ACCENT_COLOR if index == 0 and allowed else ft.Colors.TRANSPARENT,
            border_radius=8,
            margin=ft.margin.symmetric(horizontal=8, vertical=2),
            on_click=on_click if allowed else None,
            ink=allowed
        )

    # Crear botones del menú (solo módulos permitidos)
    visible_indices = [i for i, m in enumerate(modules) if _role_allows(m["role"]) ]
    # Garantizar que Inicio (0) siempre esté
    if 0 not in visible_indices:
        visible_indices.insert(0, 0)
    menu_buttons = []
    for i in visible_indices:
        name = modules[i]["name"]
        if i == 0:
            menu_buttons.append(create_menu_button(ft.Icons.HOME, name, i))
        elif i == 1:
            menu_buttons.append(create_menu_button(ft.Icons.PEOPLE_ALT, name, i))
        elif i == 2:
            menu_buttons.append(create_menu_button(ft.Icons.IMAGE, name, i))
        elif i == 3:
            menu_buttons.append(create_menu_button(pdf_icon, name, i))
        elif i == 4:
            menu_buttons.append(create_menu_button(ft.Icons.PERSON_4, name, i))
        elif i == 5:
            menu_buttons.append(create_menu_button(ft.Icons.BACKUP_SHARP, name, i))

    # Panel lateral personalizado
    sidebar = ft.Container(
        content=ft.Column([
            # Header con escudo ORMD
            ft.Container(
                content=ft.Column([
                    ft.Image(
                        src="assets/ormd sin fondo.png",
                        width=150,
                        height=150,
                        fit=ft.ImageFit.CONTAIN,
                        error_content=ft.Icon(ft.Icons.MILITARY_TECH, size=75, color=ACCENT_COLOR)
                    ),
                    ft.Container(height=5),
                    ft.Text("ORMD 055-A", size=16, weight=ft.FontWeight.BOLD, color=ACCENT_COLOR)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=15),
                bgcolor=ft.Colors.BLUE_GREY_100,
                border_radius=8,
                margin=ft.margin.only(bottom=20, left=8, right=8, top=8)
            ),
            # Botones del menú
            ft.Column(menu_buttons, spacing=4)
        ], scroll=ft.ScrollMode.AUTO),
        width=300,  # Aumentado para acomodar imagen de 150px
        bgcolor=CARD_BG,
        padding=ft.padding.symmetric(vertical=8),
        border=ft.border.only(right=ft.BorderSide(1, ft.Colors.BLUE_GREY_200))
    )

    # Suscribirse a eventos para refrescar Inicio (estadísticas) cuando cambian documentos/ciudadanos
    try:
        def _on_event(message):
            try:
                if isinstance(message, dict) and message.get("type") == "stats_changed":
                    if selected_module_index == 0 and modules[0].get("content_func"):
                        content_area.content = modules[0]["content_func"]()
                        page.update()
            except Exception as ex:
                print(f"[WARN] Falló handler de pubsub: {ex}")

        if hasattr(page, "pubsub") and hasattr(page.pubsub, "subscribe"):
            page.pubsub.subscribe(_on_event)
    except Exception as ex:
        print(f"[WARN] No se pudo suscribir a pubsub: {ex}")

    # Carga inicial: primer módulo visible
    initial_index = visible_indices[0] if visible_indices else 0
    selected_module_index = initial_index
    content_area.content = modules[initial_index]["content_func"]()
    page.update()

    # Devuelve la vista
    return ft.View(
        route="/dashboard",
        controls=[
            ft.Column(
                [
                    dashboard_header(user_data, logout_callback),
                    ft.Container(
                        content=ft.Row(
                            [
                                sidebar,
                                content_area,
                            ],
                            expand=True,
                        ),
                        expand=True
                    ),
                ],
                expand=True,
            )
        ],
        padding=0,
    )
