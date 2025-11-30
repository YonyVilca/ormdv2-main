from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, relationship

# ----------------------------------------------------------------------
# 1. Base y Tablas de Catálogo (Lookup)
# ----------------------------------------------------------------------

class Base(DeclarativeBase):
    pass

class MotivoBaja(Base):
    __tablename__ = 'motivos_baja'
    id_motivo_baja = Column(Integer, primary_key=True)
    descripcion = Column(String(100), unique=True, nullable=False)
    
    # Relación 1:N con DatosServicioMilitar
    servicios = relationship("DatosServicioMilitar", back_populates="motivo_baja")

class UnidadMilitar(Base):
    __tablename__ = 'unidades_militares'
    id_unidad = Column(Integer, primary_key=True)
    nombre_unidad = Column(String(150), unique=True, nullable=False)
    gran_unidad = Column(String(150))
    
    # Relaciones 1:N con DatosServicioMilitar (distinguiendo Alta y Baja)
    servicios_alta = relationship("DatosServicioMilitar", foreign_keys="[DatosServicioMilitar.id_unidad_alta]", back_populates="unidad_alta")
    servicios_baja = relationship("DatosServicioMilitar", foreign_keys="[DatosServicioMilitar.id_unidad_baja]", back_populates="unidad_baja")

class Grado(Base):
    __tablename__ = 'grados'
    id_grado = Column(Integer, primary_key=True)
    codigo_grado = Column(String(10), unique=True)
    descripcion = Column(String(100), nullable=False)
    
    # Relación 1:N con DatosServicioMilitar
    servicios = relationship("DatosServicioMilitar", back_populates="grado")

# ----------------------------------------------------------------------
# 2. Acceso y Documentos (Tablas Existentes Actualizadas)
# ----------------------------------------------------------------------

class Rol(Base):
    __tablename__ = 'roles'
    id_rol = Column(Integer, primary_key=True)
    nombre_rol = Column(String(50), unique=True, nullable=False)
    
    # Relación 1:N con Usuario
    usuarios = relationship("Usuario", back_populates="rol")

class Usuario(Base):
    __tablename__ = 'usuarios'
    id_usuario = Column(Integer, primary_key=True)
    nombre_usuario = Column(String(100), unique=True, nullable=False, index=True)
    contrasena_hash = Column(String(255), nullable=False)
    id_rol = Column(Integer, ForeignKey('roles.id_rol'), nullable=False)
    apellidos = Column(String(150), nullable=True)
    nombres = Column(String(150), nullable=True)

    rol = relationship("Rol", back_populates="usuarios")

    documentos_extraidos = relationship("Documento", back_populates="usuario_extraccion_rel")

    # 🔧 Relación con Ciudadano (creados/modificados)
    ciudadanos_creados = relationship(
        "Ciudadano",
        back_populates="usuario_creacion_rel",
        foreign_keys="[Ciudadano.id_usuario_creacion]"
    )
    ciudadanos_modificados = relationship(
        "Ciudadano",
        back_populates="usuario_modificacion_rel",
        foreign_keys="[Ciudadano.id_usuario_ultima_modificacion]"
    )
class Documento(Base):
    __tablename__ = 'documentos'
    id_documento = Column(Integer, primary_key=True)
    nombre_archivo = Column(String(255), nullable=False)
    ruta_almacenamiento = Column(String(255))
    fecha_extraccion = Column(DateTime, nullable=False)
    id_usuario_extraccion = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)

    # Relaciones N:1
    usuario_extraccion_rel = relationship("Usuario", back_populates="documentos_extraidos", foreign_keys=[id_usuario_extraccion])
    
    # Relaciones N:M con Servicio y Ciudadano
    servicios = relationship("DocumentoServicio", back_populates="documento")
    ciudadanos_vinculados = relationship("CiudadanoDocumento", back_populates="documento")

# ----------------------------------------------------------------------
# 3. Ciudadanos y Servicio Militar
# ----------------------------------------------------------------------
class Ciudadano(Base):
    __tablename__ = 'ciudadanos'
    id_ciudadano = Column(Integer, primary_key=True)
    dni = Column(String(20), unique=True)
    lm = Column(String(20), unique=True)
    apellidos = Column(String(150), nullable=False)
    nombres = Column(String(150), nullable=False)
    fecha_nacimiento = Column(Date)
    presto_servicio = Column(Boolean)

    # Auditoría
    fecha_creacion = Column(DateTime, nullable=False)
    id_usuario_creacion = Column(Integer, ForeignKey('usuarios.id_usuario'), nullable=False)
    fecha_ultima_modificacion = Column(DateTime)
    id_usuario_ultima_modificacion = Column(Integer, ForeignKey('usuarios.id_usuario'))

    # Relaciones
    datos_servicio = relationship("DatosServicioMilitar", back_populates="ciudadano", uselist=False)
    documentos_vinculados = relationship("CiudadanoDocumento", back_populates="ciudadano")

    # 🔧 Relación inversa con Usuario (creador/modificador)
    usuario_creacion_rel = relationship(
        "Usuario",
        back_populates="ciudadanos_creados",
        foreign_keys=[id_usuario_creacion]
    )
    usuario_modificacion_rel = relationship(
        "Usuario",
        back_populates="ciudadanos_modificados",
        foreign_keys=[id_usuario_ultima_modificacion]
    )


class DatosServicioMilitar(Base):
    __tablename__ = 'datos_servicio_militar'
    id_servicio = Column(Integer, primary_key=True)
    
    # Claves Foráneas
    id_ciudadano = Column(Integer, ForeignKey('ciudadanos.id_ciudadano'), nullable=False)
    id_unidad_alta = Column(Integer, ForeignKey('unidades_militares.id_unidad'))
    id_unidad_baja = Column(Integer, ForeignKey('unidades_militares.id_unidad'))
    id_grado = Column(Integer, ForeignKey('grados.id_grado'))
    id_motivo_baja = Column(Integer, ForeignKey('motivos_baja.id_motivo_baja'))
    
    # Campos de datos
    referencia_documento_origen = Column(String(50))
    clase = Column(String(10))
    libro = Column(String(10))
    folio = Column(String(10))
    fecha_alta = Column(Date)
    fecha_baja = Column(Date)
    
    # Relaciones (ORM)
    ciudadano = relationship("Ciudadano", back_populates="datos_servicio")
    unidad_alta = relationship("UnidadMilitar", foreign_keys=[id_unidad_alta], back_populates="servicios_alta")
    unidad_baja = relationship("UnidadMilitar", foreign_keys=[id_unidad_baja], back_populates="servicios_baja")
    grado = relationship("Grado", back_populates="servicios")
    motivo_baja = relationship("MotivoBaja", back_populates="servicios")
    
    # Relación N:M con Documento
    documentos = relationship("DocumentoServicio", back_populates="servicio")

# ----------------------------------------------------------------------
# 4. Tablas de Asociación (N:M)
# ----------------------------------------------------------------------

class DocumentoServicio(Base):
    __tablename__ = 'documento_servicio'
    id_documento = Column(Integer, ForeignKey('documentos.id_documento'), primary_key=True)
    id_servicio = Column(Integer, ForeignKey('datos_servicio_militar.id_servicio'), primary_key=True)
    
    # Relaciones de vuelta
    documento = relationship("Documento", back_populates="servicios")
    servicio = relationship("DatosServicioMilitar", back_populates="documentos")

class CiudadanoDocumento(Base):
    __tablename__ = 'ciudadano_documento'
    id_ciudadano = Column(Integer, ForeignKey('ciudadanos.id_ciudadano'), primary_key=True)
    id_documento = Column(Integer, ForeignKey('documentos.id_documento'), primary_key=True)
    
    # Relaciones de vuelta
    ciudadano = relationship("Ciudadano", back_populates="documentos_vinculados")
    documento = relationship("Documento", back_populates="ciudadanos_vinculados")