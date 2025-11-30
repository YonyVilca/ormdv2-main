# Temporary stub for JPG view to keep package import healthy while fixing main view
# This keeps the dashboard and PDF module working without importing the broken file.

import flet as ft
from utils.nav_guard import register_guard, unregister_guard

class Colors:
    SURFACE = "#F0FDF4"
    ON_SURFACE = "#14532D"


def create_digitalizacion_jpg_view(page: ft.Page, user_data=None):
    # Register a minimal guard that always returns False (no pending work)
    def has_pending_work():
        return False

    register_guard("digitalizacion_jpg", has_pending_work)

    # Minimal, informative placeholder UI
    container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.IMAGE, size=24),
                ft.Text("Digitalización de Imágenes (JPG)", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            ft.Text("Módulo temporalmente en mantenimiento. Puedes continuar usando el flujo de PDFs.", size=14),
        ], spacing=12),
        padding=20,
        bgcolor=Colors.SURFACE,
    )

    def cleanup():
        unregister_guard("digitalizacion_jpg")

    container.cleanup = cleanup
    return container
