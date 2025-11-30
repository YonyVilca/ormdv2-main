# modules/dashboard/layout.py
# -*- coding: utf-8 -*-
import flet as ft
from database.connection import SessionLocal
from database.models import Ciudadano, Documento

# Paleta (usa ft.Colors)
ACCENT_COLOR  = ft.Colors.BLUE_600
PRIMARY_COLOR = ft.Colors.BLUE_GREY_800
BG_COLOR      = ft.Colors.BLUE_GREY_50
CARD_BG       = ft.Colors.WHITE

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
    return ft.Card(
        elevation=6,
        content=ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(str(value), size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
                            ft.Text(title, size=13, color=ft.Colors.BLUE_GREY_700),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Icon(icon, color=ACCENT_COLOR, size=36),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                spacing=15,
            ),
            padding=15,
            width=220,
            height=100,
            bgcolor=CARD_BG,
            border_radius=10,
        ),
    )

def dashboard_header(user_data, logout_callback):
    return ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    "ORMD - Oficina de Registro Militar 🎖️",
                    size=22, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR
                ),
                ft.Row(
                    [
                        ft.Text(
                            f"Usuario: {user_data['username']} | Rol: {user_data['rol']}",
                            color=PRIMARY_COLOR,
                        ),
                        ft.ElevatedButton(
                            "Salir",
                            icon=ft.Icons.LOGOUT,
                            on_click=logout_callback,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700, color=ft.Colors.WHITE),
                            tooltip="Cerrar Sesión",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END, spacing=15,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.padding.only(left=20, right=20, top=10, bottom=10),
        bgcolor=CARD_BG,
        border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.BLUE_GREY_200)),
        height=60,
    )
