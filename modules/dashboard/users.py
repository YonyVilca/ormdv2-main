# modules/dashboard/users.py
# -*- coding: utf-8 -*-
import flet as ft
from .layout import PRIMARY_COLOR
from .users_view import create_users_view

def build(page: ft.Page, user_data):
    return ft.Column(
        [
            ft.Text("🛠️ Módulo: Gestión de Usuarios", size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ft.Container(height=10),
            create_users_view(page, user_data),
        ],
        expand=True,
    )
