# modules/dashboard/home.py
# -*- coding: utf-8 -*-
import flet as ft
from .layout import PRIMARY_COLOR, CARD_BG, stat_card, get_stats

def build(page: ft.Page, user_data):
    ciud, docs = get_stats()
    return ft.Column(
        [
            ft.Text("📊 Panel de Control Principal", size=28, weight=ft.FontWeight.BOLD, color=PRIMARY_COLOR),
            ft.Container(height=25),
            ft.Row(
                [
                    stat_card("Ciudadanos Registrados", ciud, ft.Icons.PERSON_ADD_ALT_1),
                    stat_card("Documentos Digitalizados", docs, ft.Icons.FOLDER_OPEN),
                    stat_card("Jefe ORMD", "Cap. Juan Pérez", ft.Icons.MILITARY_TECH),
                    stat_card("Jefe Archivo", "Tte. María Gómez", ft.Icons.ARCHIVE_SHARP),
                ],
                wrap=True, alignment=ft.MainAxisAlignment.START, spacing=30,
            ),
            ft.Container(height=30),
            ft.Text("Visualizaciones Rápidas", size=20, weight=ft.FontWeight.W_600, color=PRIMARY_COLOR),
            ft.Container(height=15),
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text("Gráfico 1"),
                        width=350, height=200, bgcolor=CARD_BG, border_radius=10, padding=20,
                    ),
                    ft.Container(
                        content=ft.Text("Gráfico 2"),
                        width=350, height=200, bgcolor=CARD_BG, border_radius=10, padding=20,
                    ),
                ],
                wrap=True, spacing=30,
            ),
        ],
        scroll=ft.ScrollMode.AUTO, expand=True,
    )
