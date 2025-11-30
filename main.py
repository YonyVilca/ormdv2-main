import flet as ft
import os
from modules.login.login_view import create_login_view
from modules.dashboard.dashboard_view import create_dashboard_view
from modules.digitalizacion.digitalizacion_pdf_view import create_digitalizacion_pdf_view 
from utils.nav_guard import install_nav_guard 

def main(page: ft.Page):
    print("🔧 Configurando aplicación...")
    
    page.title = "ORMD - Sistema de Registro Militar"
    
    # Configuración AGRESIVA para pantalla completa REAL
    page.adaptive = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    
    print("📺 Configurando PANTALLA COMPLETA REAL sin bordes...")
    
    # Configuración paso a paso para pantalla completa real
    def setup_real_fullscreen():
        try:
            # Paso 1: Configurar propiedades de ventana
            page.window_width = 1900
            page.window_height = 1020
            page.window_left = 0
            page.window_top = 0
            page.window_resizable = False
            page.window_always_on_top = False
            page.window_title_bar_hidden = True  # Ocultar barra de título
            page.window_title_bar_buttons_hidden = True  # Ocultar botones
            page.update()
            
            # Paso 2: Forzar pantalla completa
            page.window_maximized = True
            page.window_full_screen = True
            page.update()
            
            print("✅ PANTALLA COMPLETA REAL configurada sin bordes")
            
        except Exception as e:
            print(f"⚠️ Error: {e}")
            # Respaldo: configuración básica
            page.window_maximized = True
            page.window_full_screen = True
            page.update()
    
    # En modo web, saltamos la configuración de ventana de escritorio
    if os.getenv("FLET_MODE") != "web":
        setup_real_fullscreen()
    else:
        print("🌐 Modo Web: Saltando configuración de ventana de escritorio")
    
    # --- Estado Global ---
    state = {"current_user": None}
    
    # 💡 Estado de la ruta anterior (fundamental para la guardia)
    current_route = {"value": page.route or "/"}
    
    # ✅ ft.Ref: El estado de bloqueo compartido y mutable
    # Este Ref es actualizado por digitalizacion_pdf_view.py
    digi_has_docs_ref = ft.Ref[bool]()
    digi_has_docs_ref.current = False

    # --- Funciones de Navegación ---
    
    def go_to_dashboard(user_data):
        state["current_user"] = user_data
        page.go("/dashboard")

    def logout_callback(e=None):
        def cancel_logout(ev):
            bs.open = False
            page.update()

        def confirm_logout(ev):
            # Limpiamos el flag de digitalización al cerrar sesión
            digi_has_docs_ref.current = False
            state["current_user"] = None
            bs.open = False
            page.update()
            page.clean()
            page.go("/")

        bs = ft.BottomSheet(
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Text("Cerrar Sesión", size=18, weight=ft.FontWeight.BOLD),
                        ft.Text("¿Estás seguro de que deseas cerrar sesión?"),
                        ft.Row(
                            [
                                ft.TextButton("Cancelar", on_click=cancel_logout),
                                ft.TextButton("Sí, salir", on_click=confirm_logout),
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    tight=True, spacing=12,
                ),
            )
        )
        page.open(bs)

    # --- BottomSheet de confirmación de salida (Lógica centralizada) ---
    def _open_leave_sheet(target_route: str | None):
        def cancel(_):
            bs.open = False
            page.update()

        def confirm(_):
            bs.open = False
            page.update()
            
            # ✅ CLAVE: Limpiamos el flag antes de navegar/salir
            digi_has_docs_ref.current = False 
            
            if target_route:
                page.go(target_route)
            elif page.views: # Para view_pop
                # Lógica de pop manual si se confirma la salida
                page.views.pop()
                new_route = page.views[-1].route if page.views else "/"
                current_route["value"] = new_route # Actualizamos el estado después de pop
                page.go(new_route)

        bs = ft.BottomSheet(
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Row([ft.Icon(ft.Icons.WARNING_AMBER), ft.Text("Cambios pendientes", size=18, weight=ft.FontWeight.BOLD),]),
                        ft.Text("Tienes documentos cargados en Digitalización. Si sales ahora podrías perder cambios. ¿Deseas salir de todos modos?"),
                        ft.Row([ft.TextButton("Cancelar", on_click=cancel), ft.FilledButton("Salir sin guardar", icon=ft.Icons.EXIT_TO_APP, on_click=confirm),], alignment=ft.MainAxisAlignment.END,),
                    ],
                    tight=True, spacing=12,
                ),
            ),
            show_drag_handle=True,
        )
        page.open(bs)
    
    # --- Setup de Ventana SOLO pantalla completa REAL ---
    def _setup_window_for(route: str):
        # FORZAR pantalla completa REAL sin bordes
        try:
            page.window_title_bar_hidden = True
            page.window_title_bar_buttons_hidden = True
            page.window_full_screen = True
            page.window_maximized = True
            page.window_resizable = False
        except:
            # Respaldo
            page.window_full_screen = True
            page.window_maximized = True
        
        if route == "/":
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
            page.floating_action_button = None
        else:
            page.vertical_alignment = ft.MainAxisAlignment.START
            page.horizontal_alignment = ft.CrossAxisAlignment.START
            page.floating_action_button = None
            if route == "/dashboard":
                page.floating_action_button = ft.FloatingActionButton(
                    icon=ft.Icons.DOCUMENT_SCANNER_OUTLINED,
                    tooltip="Ir a Digitalización",
                    on_click=lambda e: page.go("/digitalizacion"),
                )

    # --- Router principal (con guardia) ---
    def route_change(e: ft.RouteChangeEvent):
        desired = e.route
        prev = current_route["value"]

        # 🚀 GUARD: Bloqueamos si salimos de /digitalizacion y hay docs cargados
        if prev == "/digitalizacion" and desired != "/digitalizacion" and digi_has_docs_ref.current:
            _open_leave_sheet(desired)
            return

        # No hay bloqueo => procede navegación normal y actualización de estado
        current_route["value"] = desired 
        page.views.clear()

        if desired == "/":
            page.views.append(create_login_view(page, go_to_dashboard))
            _setup_window_for("/")
        elif desired == "/dashboard":
            # Orden correcto: page, user_data, logout_callback
            page.views.append(create_dashboard_view(page, state["current_user"], logout_callback))
            _setup_window_for("/dashboard")
        elif desired == "/digitalizacion":
            page.views.append(create_digitalizacion_pdf_view(page, digi_has_docs_ref))
            _setup_window_for("/digitalizacion")

        page.update()

    def view_pop(e):
        if not page.views:
            return
        
        view = page.views[-1] if page.views else None
        if not view:
            return
        
        prev_route = view.route
        
        # 🚀 GUARD: si estamos saliendo de /digitalizacion y hay docs, bloqueamos el pop.
        if prev_route == "/digitalizacion" and digi_has_docs_ref.current:
            _open_leave_sheet(None)
            return
        
        # comportamiento normal
        if page.views:
            page.views.pop()
        
        # Actualizar el estado de la ruta después del pop
        new_route = page.views[-1].route if page.views else "/"
        current_route["value"] = new_route 
        page.go(new_route)

    # Función para mantener pantalla completa REAL
    def force_fullscreen():
        try:
            page.window_title_bar_hidden = True
            page.window_title_bar_buttons_hidden = True
            page.window_maximized = True
            page.window_full_screen = True
            page.update()
            print("🖥️ Pantalla completa REAL mantenida")
        except Exception as e:
            print(f"⚠️ Error manteniendo pantalla completa: {e}")

    # --- SIN manejador de eventos de teclado ---
    # No hay teclas para salir de pantalla completa
    
    # Handlers
    page.on_route_change = route_change
    page.on_view_pop = view_pop
    # SIN eventos de teclado - solo pantalla completa

    # Instalar guardia de navegación después de configurar handlers
    install_nav_guard(page)

    # Arranque
    print("🚀 Iniciando navegación...")
    page.go(page.route or "/")
    
    # Forzar pantalla completa final (solo desktop)
    if os.getenv("FLET_MODE") != "web":
        force_fullscreen()
    print("✅ Aplicación lista en pantalla completa")


if __name__ == "__main__":
    # Detectar modo (web vs desktop)
    IS_WEB = os.getenv("FLET_MODE") == "web"
    
    if IS_WEB:
        print("🌐 INICIANDO EN MODO WEB (DOCKER)...")
        
        # Asegurar directorio de subidas
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
            print(f"📁 Directorio '{upload_dir}' creado.")
            
        try:
            # En modo web: escuchamos en 0.0.0.0, puerto 8080, y habilitamos subidas
            ft.app(
                target=main, 
                view=ft.AppView.WEB_BROWSER, 
                port=8080, 
                host="0.0.0.0",
                upload_dir=upload_dir
            )
        except Exception as e:
            print(f"❌ Error al iniciar aplicación WEB: {e}")
            
    else:
        print("🔧 INICIANDO APLICACIÓN ORMD EN 1900x1020 PANTALLA COMPLETA...")
        try:
            ft.app(target=main, view=ft.AppView.FLET_APP, port=0)
        except Exception as e:
            print(f"❌ Error al iniciar aplicación: {e}")
            input("Presiona Enter para salir...")