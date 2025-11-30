import flet as ft

def main(page: ft.Page):
    page.title = "Login App"
    page.window_width = 400
    page.window_height = 600
    page.window_resizable = False
    page.padding = 0
    page.bgcolor = "#f5f5f5"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    email_field = ft.TextField(
        label="Correo electrónico",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        border_radius=12,
        bgcolor=ft.Colors.WHITE,
        focused_border_color="#6C63FF",
        height=50,
    )

    password_field = ft.TextField(
        label="Contraseña",
        prefix_icon=ft.Icons.LOCK_OUTLINED,
        password=True,
        can_reveal_password=True,
        border_radius=12,
        bgcolor=ft.Colors.WHITE,
        focused_border_color="#6C63FF",
        height=50,
    )

    login_button = ft.ElevatedButton(
        text="Iniciar Sesión",
        width=300,
        height=50,
        bgcolor="#6C63FF",
        color=ft.Colors.WHITE,
        elevation=8,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
        ),
        on_click=lambda e: page.show_snack_bar(
            ft.SnackBar(ft.Text("¡Login exitoso!"), open=True)
        ),
    )

    login_container = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),
                ft.Text("Bienvenido", size=32, weight=ft.FontWeight.BOLD, color="#2D2D2D"),
                ft.Text("Inicia sesión para continuar", size=16, color="#777777"),
                ft.Container(height=40),
                email_field,
                ft.Container(height=15),
                password_field,
                ft.Container(height=30),
                login_button,
                ft.Container(height=20),
                ft.TextButton("¿Olvidaste tu contraseña?", style=ft.ButtonStyle(color="#6C63FF")),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        width=340,
        padding=40,
        border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=["#FFFFFF", "#F0F0FF"],
        ),
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=15,
            color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
            offset=ft.Offset(0, 5),
        ),
    )

    page.add(
        ft.Container(
            content=login_container,
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#E0E7FF", "#C3C8FF"],
            ),
            alignment=ft.alignment.center,
        )
    )

ft.app(target=main)