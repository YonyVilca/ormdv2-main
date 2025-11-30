import flet as ft
from modules.login.login_view import create_login_view
from modules.dashboard.dashboard_view import create_dashboard_view
from modules.digitalizacion.digitalizacion_pdf_view import create_digitalizacion_pdf_view 
from utils.nav_guard import install_nav_guard 

def main(page: ft.Page):
    page.title = "ORMD - Sistema de Registro Militar"
    
    # Configuración directa para forzar pantalla completa real
    import time
    
    def setup_fullscreen():
        """Configuración agresiva para pantalla completa real"""
        # Paso 1: Configurar propiedades básicas
        page.window_resizable = True
        page.window_always_on_top = False
        page.adaptive = True
        page.theme_mode = ft.ThemeMode.LIGHT
        page.padding = 0
        page.spacing = 0
        
        # Paso 2: Obtener dimensiones de pantalla y aplicarlas
        try:
            import tkinter as tk
            root = tk.Tk()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.destroy()
            
            print(f"📏 Resolución detectada: {screen_width}x{screen_height}")
            
            # Configurar tamaño exacto de la pantalla
            page.window_width = screen_width
            page.window_height = screen_height
            page.window_left = 0
            page.window_top = 0
            
        except Exception as e:
            print(f"⚠️ Error obteniendo resolución: {e}")
        
        # Paso 3: Forzar maximización y pantalla completa
        page.window_maximized = True
        page.update()
        
        # Paso 4: Pequeña pausa y luego pantalla completa
        time.sleep(0.1)
        page.window_full_screen = True
        page.update()
        
        print("🖥️ Configuración de pantalla completa aplicada")
    
    # Aplicar configuración inicial
    setup_fullscreen()
    
    # Función simplificada para pantalla completa con verificación
    def force_fullscreen():
        """Fuerza pantalla completa de manera directa con verificación"""
        try:
            print("🔄 Aplicando pantalla completa...")
            
            # Aplicar configuraciones
            page.window_maximized = True
            page.window_full_screen = True
            page.update()
            
            # Verificar estado
            print(f"📊 Estado actual:")
            print(f"   - Maximizada: {page.window_maximized}")
            print(f"   - Pantalla completa: {page.window_full_screen}")
            print(f"   - Ancho: {page.window_width}")
            print(f"   - Alto: {page.window_height}")
            
            print("✅ Pantalla completa aplicada")
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    # Función simplificada para alternar pantalla completa
    def toggle_fullscreen():
        """Alterna pantalla completa de manera directa"""
        try:
            current = page.window_full_screen
            new_state = not current
            
            if new_state:
                # Activar pantalla completa
                page.window_maximized = True
                page.window_full_screen = True
            else:
                # Desactivar pantalla completa pero mantener maximizado
                page.window_full_screen = False
                page.window_maximized = True
            
            page.update()
            print(f"🖥️ Pantalla completa: {'ON' if new_state else 'OFF (maximizada)'}")
            return True
        except Exception as e:
            print(f"❌ Error al alternar: {e}")
            return False
    
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
        # NO tocar configuraciones de pantalla completa aquí
        # Solo configurar alineación y botones
        
        if route == "/":
            # Para login, centrar contenido
            page.vertical_alignment = ft.MainAxisAlignment.CENTER
            page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
            page.floating_action_button = None
        else: # /dashboard y /digitalizacion
            # Para otras vistas, alineación normal
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
        prev = current_route["value"] # 👈 Usamos el valor guardado antes del cambio de Flet

        # 🚀 GUARD: Bloqueamos si salimos de /digitalizacion y hay docs cargados
        if prev == "/digitalizacion" and desired != "/digitalizacion" and digi_has_docs_ref.current:
            # Bloqueamos la navegación, mantenemos la ruta anterior
            # No se llama a page.go() ni se actualiza current_route["value"]
            _open_leave_sheet(desired)
            return

        # No hay bloqueo => procede navegación normal y actualización de estado
        current_route["value"] = desired 
        page.views.clear()

        if desired == "/":
            page.views.append(create_login_view(page, go_to_dashboard))
            _setup_window_for("/")
        elif desired == "/dashboard":
            if not state["current_user"]:
                page.go("/")
                return
            page.views.append(create_dashboard_view(page, state["current_user"], logout_callback))
            _setup_window_for("/dashboard")
        elif desired == "/digitalizacion":
            if not state["current_user"]:
                page.go("/")
                return
            # ✅ CLAVE: Pasamos el Ref de estado a la vista de digitalización
            view_content = create_digitalizacion_pdf_view(page, state["current_user"], has_docs_ref=digi_has_docs_ref)
            
            page.views.append(
                ft.View(
                    route="/digitalizacion",
                    controls=[view_content],
                    scroll=ft.ScrollMode.ADAPTIVE
                )
            )
            _setup_window_for("/digitalizacion")
        else:
            page.go("/")
            return

        page.update()

    # --- Botón back / pop de vistas (con guardia) ---
    def view_pop(view):
        # La ruta que estamos a punto de salir es la última en la pila (view.route)
        prev_route = view.route
        
        # 🚀 GUARD: si estamos saliendo de /digitalizacion y hay docs, bloqueamos el pop.
        if prev_route == "/digitalizacion" and digi_has_docs_ref.current:
            _open_leave_sheet(None) # Si confirman, el sheet llamará al pop
            return
        
        # comportamiento normal
        if page.views:
            page.views.pop()
        
        # Actualizar el estado de la ruta después del pop
        new_route = page.views[-1].route if page.views else "/"
        current_route["value"] = new_route 
        page.go(new_route)

    # --- Manejador de eventos de teclado mejorado ---
    def on_keyboard(e: ft.KeyboardEvent):
        """Maneja eventos de teclado globales"""
        print(f"🔧 Tecla detectada: '{e.key}' - Shift: {e.shift} - Ctrl: {e.ctrl} - Alt: {e.alt}")
        
        if e.key == "F11":
            print("🎯 F11 detectado - Alternando pantalla completa")
            toggle_fullscreen()
        elif e.key == "F10":
            print("🎯 F10 detectado - Forzando pantalla completa")
            force_fullscreen()
        elif e.key.lower() == "f" and e.ctrl:
            # Ctrl+F como alternativa
            print("🎯 Ctrl+F detectado - Alternando pantalla completa")
            toggle_fullscreen()
        else:
            print(f"🔍 Tecla no manejada: {e.key}")

    # Handlers
    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.on_keyboard_event = on_keyboard

    # Instalar guardia de navegación después de configurar handlers
    install_nav_guard(page)

    # Arranque simplificado
    print("🚀 Iniciando aplicación...")
    page.go(page.route or "/")
    
    # Forzar pantalla completa después del arranque
    print("📺 Configurando pantalla completa...")
    force_fullscreen()


if __name__ == "__main__":
    print("🔧 Iniciando aplicación ORMD en pantalla completa...")
    
    # Configuración de Flet
    ft.app(
        target=main,
        view=ft.AppView.FLET_APP,          # Aplicación nativa
        port=0                             # Puerto automático
    )