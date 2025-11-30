# utils/nav_guard.py
# -*- coding: utf-8 -*-
import flet as ft

# Mapa de checkers por módulo: cada callable debe devolver True si hay pendientes
_registered_checkers: dict[str, callable] = {}

# Estado del guard
_bs: ft.BottomSheet | None = None
_bs_target = {"value": None}
_installed = {"done": False}
_prev_on_route_change = {"fn": None}
_prev_on_view_pop = {"fn": None}
_current_route = {"value": "/"}

def register_guard(source_id: str, has_pending_callable):
    """Registra un checker para un módulo (p.ej. 'digitalizacion')."""
    _registered_checkers[source_id] = has_pending_callable

def unregister_guard(source_id: str):
    _registered_checkers.pop(source_id, None)

def _has_any_pending() -> bool:
    """Devuelve True si CUALQUIER checker reporta pendientes."""
    for fn in _registered_checkers.values():
        try:
            if fn():
                return True
        except Exception:
            # ignoramos fallos individuales de checkers
            pass
    return False

def install_nav_guard(page: ft.Page, sheet_width: int = 520):
    """
    Instala un guard global de navegación. Debe llamarse DESPUÉS de:
      page.on_route_change = ...
      page.on_view_pop     = ...
    Inyecta:
      - Interceptor sobre on_route_change y on_view_pop
      - page.safe_go(...) para navegar respetando el guard
    """
    if _installed["done"]:
        return

    # --- BottomSheet global ---
    def _close_sheet(_=None):
        if _bs:
            # Algunas versiones requieren explícitamente cerrar con set open False
            _bs.open = False
            page.update()

    def _confirm_and_go(_=None):
        if _bs:
            target = _bs_target["value"]
            _bs.open = False
            page.update()
            if target:
                _current_route["value"] = target
                page.go(target)

    content = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER),
                        ft.Text("Cambios pendientes", weight=ft.FontWeight.BOLD, size=16),
                    ]
                ),
                ft.Text(
                    "Tienes documentos cargados en Digitalización. "
                    "Si sales ahora podrías perder cambios. ¿Deseas salir de todos modos?",
                    size=14,
                ),
                ft.Row(
                    [
                        ft.OutlinedButton("Cancelar", icon=ft.Icons.CLOSE, on_click=_close_sheet),
                        ft.FilledButton("Salir sin guardar", icon=ft.Icons.EXIT_TO_APP, on_click=_confirm_and_go),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12,
            tight=True,
        ),
        padding=16,
        width=sheet_width,
    )

    global _bs
    _bs = ft.BottomSheet(content=content, show_drag_handle=True)
    if _bs not in page.overlay:
        page.overlay.append(_bs)

    # Memoriza handlers originales
    _prev_on_route_change["fn"] = getattr(page, "on_route_change", None)
    _prev_on_view_pop["fn"] = getattr(page, "on_view_pop", None)
    _current_route["value"] = page.route or "/"

    # --- Interceptor de cambios de ruta (page.go / url / botones) ---
    def _guarded_route_change(e: ft.RouteChangeEvent):
        desired = e.route
        if _has_any_pending():
            # Mantener ruta actual, abrir el sheet (usar page.open para compat)
            _bs_target["value"] = desired
            page.open(_bs)  # 👈 clave para Flet en algunas versiones
            return
        # Sin pendientes => propagar
        _current_route["value"] = desired
        prev = _prev_on_route_change["fn"]
        if callable(prev):
            prev(e)

    # --- Interceptor del back (view_pop) ---
    def _guarded_view_pop(view):
        if _has_any_pending():
            # Cancelar el pop y abrir el sheet
            _bs_target["value"] = None  # volver atrás no tiene un target explícito
            page.open(_bs)  # 👈 clave
            return
        prev = _prev_on_view_pop["fn"]
        if callable(prev):
            prev(view)

    page.on_route_change = _guarded_route_change
    page.on_view_pop = _guarded_view_pop

    # --- Exponer navegación segura ---
    def safe_go(target_route: str):
        if _has_any_pending():
            _bs_target["value"] = target_route
            page.open(_bs)  # 👈 clave
            return
        _current_route["value"] = target_route
        page.go(target_route)

    page.safe_go = safe_go  # type: ignore

    _installed["done"] = True
