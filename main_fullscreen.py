import flet as ft
from modules.login.login_view import create_login_view
from modules.dashboard.dashboard_view import create_dashboard_view
from modules.digitalizacion.digitalizacion_pdf_view import create_digitalizacion_pdf_view 
from utils.nav_guard import install_nav_guard 

def main(page: ft.Page):
    print("🔧 Configurando aplicación...")
    
    page.title = "ORMD - Sistema de Registro Militar"
    
    # Configuración básica primero
    page.adaptive = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    
    # Forzar pantalla completa de manera más directa
    print("📺 Activando pantalla completa...")
    page.window_resizable = True
    page.window_maximized = True
    page.window_full_screen = True
    page.update()
    print("✅ Pantalla completa activada")
    
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
    
    # --- Setup de Ventana simplificado ---
    def _setup_window_for(route: str):
        # Mantener pantalla completa siempre
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
            page.views.append(create_dashboard_view(page, logout_callback, state["current_user"]))
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

    # Función para forzar pantalla completa
    def force_fullscreen():
        page.window_maximized = True
        page.window_full_screen = True
        page.update()
        print("🖥️ Pantalla completa forzada")

    # Función para alternar pantalla completa
    def toggle_fullscreen():
        current = page.window_full_screen
        page.window_full_screen = not current
        if not page.window_full_screen:
            page.window_maximized = True
        page.update()
        print(f"🖥️ Pantalla completa: {'ON' if not current else 'OFF'}")

    # --- Manejador de eventos de teclado ---
    def on_keyboard(e: ft.KeyboardEvent):
        print(f"🔧 Tecla: {e.key}")
        if e.key == "F11":
            toggle_fullscreen()
        elif e.key == "F10":
            force_fullscreen()

    # Handlers
    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.on_keyboard_event = on_keyboard

    # Instalar guardia de navegación después de configurar handlers
    install_nav_guard(page)

    # Arranque
    print("🚀 Iniciando navegación...")
    page.go(page.route or "/")
    
    # Forzar pantalla completa final
    force_fullscreen()
    print("✅ Aplicación lista en pantalla completa")


if __name__ == "__main__":
    print("🔧 Iniciando aplicación ORMD...")
    ft.app(target=main, view=ft.AppView.FLET_APP, port=0)