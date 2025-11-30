import bcrypt
from database.connection import SessionLocal
from database.models import Usuario
from utils.security import verify_password

def authenticate_user(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.nombre_usuario == username).first()
        if user and verify_password(password, user.contrasena_hash):
            return {
                "id_usuario": user.id_usuario,      # <-- clave estándar
                "nombre_usuario": user.nombre_usuario,
                "rol": user.rol.nombre_rol
            }
        return None
    except Exception as e:
        print(f"Error en autenticación: {e}")
        return None
    finally:
        db.close()

