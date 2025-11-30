"""Controlador para gestión de usuarios y roles.

Responsabilidades:
 - Listar usuarios con paginación y búsqueda.
 - Crear, editar, eliminar usuarios.
 - Asignar rol existente.
 - Crear nuevos roles.
"""
from typing import Optional, List, Dict
import flet as ft
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from database.connection import SessionLocal
from database.models import Usuario, Rol, Documento, Ciudadano
from utils.security import hash_password  # asumimos que existe; si no, reemplazar


class UserService:
    """Operaciones CRUD sobre usuarios y roles en una capa simple."""

    def __init__(self):
        self.db = SessionLocal()

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass

    # ---- Roles ----
    def list_roles(self) -> List[Rol]:
        return list(self.db.execute(select(Rol)).scalars().all())

    def get_role_map(self) -> Dict[int, str]:
        return {r.id_rol: r.nombre_rol for r in self.list_roles()}

    def seed_default_roles(self) -> None:
        """Garantiza que los 4 niveles base existan.
        Orden sugerido de jerarquía:
        1. Administrador (plenos permisos)
        2. Editor (modifica usuarios y datos excepto eliminar)
        3. Operador (ingresa datos/documentos, no modifica usuarios)
        4. Consulta (solo lectura)
        """
        base_roles = ["Administrador", "Editor", "Operador", "Consulta"]
        for rn in base_roles:
            try:
                self.ensure_role(rn)
            except Exception:
                pass

    def ensure_role(self, nombre: str) -> Rol:
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("Nombre de rol vacío")
        rol = self.db.execute(select(Rol).where(Rol.nombre_rol == nombre)).scalar_one_or_none()
        if rol:
            return rol
        rol = Rol(nombre_rol=nombre)
        self.db.add(rol)
        self.db.commit()
        self.db.refresh(rol)
        return rol

    # ---- Usuarios ----
    def list_users(self, q: Optional[str] = None) -> List[Usuario]:
        stmt = select(Usuario)
        if q:
            qlike = f"%{q.strip()}%"
            stmt = stmt.where(Usuario.nombre_usuario.ilike(qlike))
        return list(self.db.execute(stmt).scalars().all())

    def create_user(self, nombre_usuario: str, contrasena: str, rol_nombre: str, apellidos: str = "", nombres: str = "") -> Usuario:
        nombre_usuario = nombre_usuario.strip()
        if not nombre_usuario or not contrasena:
            raise ValueError("Usuario y contraseña requeridos")
        existing = self.db.execute(select(Usuario).where(Usuario.nombre_usuario == nombre_usuario)).scalar_one_or_none()
        if existing:
            raise ValueError("Usuario ya existe")
        rol = self.ensure_role(rol_nombre)
        contrasena_hash = hash_password(contrasena)
        user = Usuario(nombre_usuario=nombre_usuario, contrasena_hash=contrasena_hash, id_rol=rol.id_rol, apellidos=apellidos, nombres=nombres)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, rol_nombre: Optional[str] = None, nueva_contrasena: Optional[str] = None) -> Usuario:
        user = self.db.execute(select(Usuario).where(Usuario.id_usuario == user_id)).scalar_one_or_none()
        if not user:
            raise ValueError("Usuario no encontrado")
        if rol_nombre:
            rol = self.ensure_role(rol_nombre)
            user.id_rol = rol.id_rol
        if nueva_contrasena:
            user.contrasena_hash = hash_password(nueva_contrasena)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        user = self.db.execute(select(Usuario).where(Usuario.id_usuario == user_id)).scalar_one_or_none()
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True

    def get_user_activity(self, user_id: int, limit: int = 20) -> List[Dict]:
        """Devuelve actividad combinada reciente del usuario.
        - Documentos extraídos por el usuario
        - Ciudadanos creados por el usuario
        - Ciudadanos modificados por el usuario
        """
        acts: List[Dict] = []
        # Documentos extraídos
        docs = self.db.execute(
            select(Documento).where(Documento.id_usuario_extraccion == user_id).order_by(Documento.fecha_extraccion.desc()).limit(limit)
        ).scalars().all()
        for d in docs:
            acts.append({
                "ts": getattr(d, "fecha_extraccion", None),
                "title": f"Documento extraído",
                "subtitle": f"{d.nombre_archivo} | {d.ruta_almacenamiento or ''}",
                "icon": ft.Icons.DESCRIPTION,
            })

        # Ciudadanos creados
        creados = self.db.execute(
            select(Ciudadano).where(Ciudadano.id_usuario_creacion == user_id).order_by(Ciudadano.fecha_creacion.desc()).limit(limit)
        ).scalars().all()
        for c in creados:
            acts.append({
                "ts": getattr(c, "fecha_creacion", None),
                "title": "Ciudadano creado",
                "subtitle": f"{c.apellidos} {c.nombres} | DNI: {c.dni or '—'} | LM: {c.lm or '—'}",
                "icon": ft.Icons.PERSON_ADD_ALT_1,
            })

        # Ciudadanos modificados
        mods = self.db.execute(
            select(Ciudadano).where(Ciudadano.id_usuario_ultima_modificacion == user_id).order_by(Ciudadano.fecha_ultima_modificacion.desc()).limit(limit)
        ).scalars().all()
        for c in mods:
            acts.append({
                "ts": getattr(c, "fecha_ultima_modificacion", None),
                "title": "Ciudadano modificado",
                "subtitle": f"{c.apellidos} {c.nombres} | DNI: {c.dni or '—'} | LM: {c.lm or '—'}",
                "icon": ft.Icons.EDIT,
            })

        # Ordenar y truncar
        acts.sort(key=lambda a: a.get("ts") or 0, reverse=True)
        return acts[:limit]


def validate_password(pw: str) -> List[str]:
    problems = []
    if len(pw) < 8:
        problems.append("Debe tener al menos 8 caracteres")
    if pw.lower() == pw:
        problems.append("Debe incluir mayúsculas")
    if pw.upper() == pw:
        problems.append("Debe incluir minúsculas")
    if not any(c.isdigit() for c in pw):
        problems.append("Debe incluir dígitos")
    return problems
