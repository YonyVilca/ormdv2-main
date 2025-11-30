# modules/dashboard/registry.py
# -*- coding: utf-8 -*-
import flet as ft

from . import home
from . import data
from . import users
from modules.digitalizacion import digitalizacion_view  # tu vista real
from . import backups

# Cada entrada: (nombre, icono, build_func)
MODULES = [
    ("Inicio",             ft.Icons.HOME,          home.build),
    ("Gestión de Datos",   ft.Icons.PEOPLE_ALT,    data.build),
    ("Digitalización",     ft.Icons.SCANNER_SHARP, lambda page, user: digitalizacion_view.create_digitalizacion_view(page, user)),
    ("Gestión de Usuarios",ft.Icons.PERSON_4,      users.build),
    ("Backups",            ft.Icons.BACKUP_SHARP,  backups.build),
]
