# modules/login/login_view.py
import flet as ft
from modules.login.login_controller import authenticate_user

# Paleta de colores verde consistente con el sistema
class Colors:
    PRIMARY = "#16A34A"           # Verde principal semi-oscuro
    PRIMARY_LIGHT = "#22C55E"     # Verde claro
    PRIMARY_DARK = "#15803D"      # Verde oscuro
    SECONDARY = "#059669"         # Verde secundario
    DANGER = "#EF4444"            # Rojo para errores
    SUCCESS = "#047857"           # Verde éxito oscuro
    SURFACE = "#F0FDF4"           # Fondo verde muy claro
    SURFACE_VARIANT = "#DCFCE7"   # Verde claro para variantes
    ON_SURFACE = "#14532D"        # Texto verde oscuro
    ON_SURFACE_VARIANT = "#166534" # Texto verde medio
    BORDER = "#BBF7D0"            # Borde verde claro
    WHITE = "#FFFFFF"
    BLACK = "#000000"

def create_login_view(page: ft.Page, on_success):
    def login_click(e):
        username = user_field.value.strip()
        password = pass_field.value
        if not username or not password:
            error_text.value = "❌ Complete todos los campos"
            page.update()
            return
        user_data = authenticate_user(username, password)
        if user_data:
            error_text.value = ""
            on_success(user_data)
        else:
            error_text.value = "❌ Usuario o contraseña incorrectos"
        page.update()

    user_field = ft.TextField(
        label="Usuario", 
        width=320,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.ON_SURFACE),
        label_style=ft.TextStyle(color=Colors.ON_SURFACE_VARIANT),
        bgcolor=Colors.WHITE,
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        border_radius=12
    )

    pass_field = ft.TextField(
        label="Contraseña", 
        password=True, 
        can_reveal_password=True, 
        width=320,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.ON_SURFACE),
        label_style=ft.TextStyle(color=Colors.ON_SURFACE_VARIANT),
        bgcolor=Colors.WHITE,
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        border_radius=12,
        on_submit=login_click
    )

    error_text = ft.Text("", color=Colors.DANGER, size=14, weight=ft.FontWeight.W_500)

    # Contenedor principal con fondo y sombra
    login_container = ft.Container(
        width=400,
        content=ft.Column([
            ft.Container(height=20),
            # Logo Ejército del Perú
            ft.Container(
                content=ft.Image(
                    src="assets/ejercito sin fondo.png",
                    width=200,
                    height=200,
                    fit=ft.ImageFit.CONTAIN,
                    error_content=ft.Icon(ft.Icons.MILITARY_TECH, size=120, color=Colors.PRIMARY)
                ),
                bgcolor=Colors.WHITE,
                border_radius=100,
                padding=20,
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=12,
                    color="#20000000",
                    offset=ft.Offset(0, 4)
                )
            ),
            ft.Container(height=30),
            ft.Text("ORMD", size=36, weight=ft.FontWeight.BOLD, color=Colors.PRIMARY),
            ft.Text("Oficina de Registro Militar", size=16, color=Colors.ON_SURFACE_VARIANT, italic=True),
            ft.Container(height=40),
            user_field,
            pass_field,
            ft.Container(height=8),
            error_text,
            ft.Container(height=24),
            ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.LOGIN, color=Colors.WHITE, size=20),
                    ft.Text("Ingresar", color=Colors.WHITE, size=16, weight=ft.FontWeight.BOLD)
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True),
                width=320, 
                height=50,
                on_click=login_click,
                style=ft.ButtonStyle(
                    bgcolor=Colors.PRIMARY,
                    color=Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    shadow_color=Colors.PRIMARY,
                    elevation=4
                ),
            ),
            ft.Container(height=20),
        ], 
        alignment=ft.MainAxisAlignment.CENTER, 
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
        spacing=8,
        tight=True),
        padding=40,
        bgcolor=Colors.WHITE,
        border_radius=20,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=20,
            color="#30000000",
            offset=ft.Offset(0, 8)
        ),
        border=ft.border.all(1, Colors.BORDER)
    )

    return ft.View(
        route="/",
        controls=[
            ft.Container(
                content=login_container,
                alignment=ft.alignment.center,
                bgcolor=ft.LinearGradient(
                    colors=[Colors.SURFACE, Colors.SURFACE_VARIANT],
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right
                )
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
