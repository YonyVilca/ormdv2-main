# database/crud.py
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import (
    Ciudadano, Documento, DatosServicioMilitar,
    MotivoBaja, UnidadMilitar, Grado,
    DocumentoServicio, CiudadanoDocumento
)

def _parse_date_ddmmyyyy(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        d, m, y = s.split("/")
        return date(int(y), int(m), int(d))
    except Exception:
        return None

def _to_bool_si_no(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    vs = str(v).strip().upper()
    if vs in ("SI", "SÍ", "S", "SI."):
        return True
    if vs in ("NO", "N", "NO."):
        return False
    return None

def _get_or_create(session: Session, model, where_kwargs: dict, create_kwargs: dict = None):
    obj = session.execute(select(model).filter_by(**where_kwargs)).scalar_one_or_none()
    if obj:
        return obj, False
    obj = model(**(create_kwargs or where_kwargs))
    session.add(obj)
    session.flush()
    return obj, True

def create_full_digital_record(
    db: Session,
    data: dict,
    file_info: dict,
    id_usuario_actual: int
) -> dict:
    """
    Crea/actualiza:
      - Ciudadano (por dni o lm)
      - DatosServicioMilitar (1:1 con ciudadano)
      - Documento
      - Asociaciones N:M con Documento
    Devuelve: {'ciudadano_id', 'servicio_id', 'documento_id'}
    """
    # --- normalizaciones de entrada ---
    dni = (data.get("dni") or "").strip() or None
    lm  = (data.get("lm") or "").strip() or None
    apellidos = (data.get("apellidos") or "").strip()
    nombres   = (data.get("nombres") or "").strip()

    fecha_nacimiento = _parse_date_ddmmyyyy(data.get("fecha_nacimiento"))
    presto_servicio  = _to_bool_si_no(data.get("presto_servicio"))

    gran_unidad = (data.get("gran_unidad") or "").strip() or None
    unidad_alta_nombre = (data.get("unidad_alta") or "").strip() or None
    unidad_baja_nombre = (data.get("unidad_baja") or "").strip() or None

    fecha_alta = _parse_date_ddmmyyyy(data.get("fecha_alta"))
    fecha_baja = _parse_date_ddmmyyyy(data.get("fecha_baja"))

    grado_desc = (data.get("grado") or "").strip() or None
    motivo_baja_desc = (data.get("motivo_baja") or "").strip() or None

    clase = (data.get("clase") or "").strip() or None
    libro = (data.get("libro") or "").strip() or None
    folio = (data.get("folio") or "").strip() or None
    referencia_origen = (data.get("or") or "").strip() or None

    # --- catálogos ---
    grado = None
    if grado_desc:
        grado, _ = _get_or_create(
            db, Grado,
            where_kwargs={"descripcion": grado_desc},
            create_kwargs={"descripcion": grado_desc, "codigo_grado": None}
        )

    motivo_baja = None
    if motivo_baja_desc:
        motivo_baja, _ = _get_or_create(
            db, MotivoBaja,
            where_kwargs={"descripcion": motivo_baja_desc},
            create_kwargs={"descripcion": motivo_baja_desc}
        )

    unidad_alta = None
    if unidad_alta_nombre:
        unidad_alta, _ = _get_or_create(
            db, UnidadMilitar,
            where_kwargs={"nombre_unidad": unidad_alta_nombre},
            create_kwargs={"nombre_unidad": unidad_alta_nombre, "gran_unidad": gran_unidad}
        )
    unidad_baja = None
    if unidad_baja_nombre:
        unidad_baja, _ = _get_or_create(
            db, UnidadMilitar,
            where_kwargs={"nombre_unidad": unidad_baja_nombre},
            create_kwargs={"nombre_unidad": unidad_baja_nombre, "gran_unidad": gran_unidad}
        )

    # --- ciudadano (dni o lm requerido) ---
    if not dni and not lm:
        raise ValueError("Se requiere al menos DNI o LM para registrar al ciudadano.")

    q = select(Ciudadano)
    if dni and lm:
        q = q.where((Ciudadano.dni == dni) | (Ciudadano.lm == lm))
    elif dni:
        q = q.where(Ciudadano.dni == dni)
    else:
        q = q.where(Ciudadano.lm == lm)

    ciudadano = db.execute(q).scalar_one_or_none()
    now = datetime.utcnow()

    if ciudadano is None:
        ciudadano = Ciudadano(
            dni=dni,
            lm=lm,
            apellidos=apellidos,
            nombres=nombres,
            fecha_nacimiento=fecha_nacimiento,
            presto_servicio=presto_servicio,
            fecha_creacion=now,
            id_usuario_creacion=id_usuario_actual
        )
        db.add(ciudadano)
        db.flush()
    else:
        if apellidos: ciudadano.apellidos = apellidos
        if nombres:   ciudadano.nombres = nombres
        if fecha_nacimiento is not None: ciudadano.fecha_nacimiento = fecha_nacimiento
        if presto_servicio is not None:  ciudadano.presto_servicio = presto_servicio
        if dni and not ciudadano.dni: ciudadano.dni = dni
        if lm  and not ciudadano.lm:  ciudadano.lm  = lm
        ciudadano.fecha_ultima_modificacion = now
        ciudadano.id_usuario_ultima_modificacion = id_usuario_actual
        db.flush()

    # --- datos servicio militar (1:1) ---
    servicio = db.execute(
        select(DatosServicioMilitar).where(DatosServicioMilitar.id_ciudadano == ciudadano.id_ciudadano)
    ).scalar_one_or_none()

    if servicio is None:
        servicio = DatosServicioMilitar(
            id_ciudadano=ciudadano.id_ciudadano,
            referencia_documento_origen=referencia_origen,
            clase=clase, libro=libro, folio=folio,
            fecha_alta=fecha_alta, fecha_baja=fecha_baja,
            id_unidad_alta=unidad_alta.id_unidad if unidad_alta else None,
            id_unidad_baja=unidad_baja.id_unidad if unidad_baja else None,
            id_grado=grado.id_grado if grado else None,
            id_motivo_baja=motivo_baja.id_motivo_baja if motivo_baja else None
        )
        db.add(servicio)
        db.flush()
    else:
        servicio.referencia_documento_origen = referencia_origen or servicio.referencia_documento_origen
        servicio.clase = clase or servicio.clase
        servicio.libro = libro or servicio.libro
        servicio.folio = folio or servicio.folio
        if fecha_alta is not None: servicio.fecha_alta = fecha_alta
        if fecha_baja is not None: servicio.fecha_baja = fecha_baja
        if unidad_alta: servicio.id_unidad_alta = unidad_alta.id_unidad
        if unidad_baja: servicio.id_unidad_baja = unidad_baja.id_unidad
        if grado:       servicio.id_grado = grado.id_grado
        if motivo_baja: servicio.id_motivo_baja = motivo_baja.id_motivo_baja
        db.flush()

    # --- documento ---
    documento = Documento(
        nombre_archivo=file_info.get("name"),
        ruta_almacenamiento=file_info.get("path"),
        fecha_extraccion=now,
        id_usuario_extraccion=id_usuario_actual
    )
    db.add(documento)
    db.flush()

    # --- asociaciones N:M ---
    db.add(DocumentoServicio(id_documento=documento.id_documento, id_servicio=servicio.id_servicio))
    db.add(CiudadanoDocumento(id_ciudadano=ciudadano.id_ciudadano, id_documento=documento.id_documento))

    # --- commit ---
    db.commit()

    return {
        "ciudadano_id": ciudadano.id_ciudadano,
        "servicio_id": servicio.id_servicio,
        "documento_id": documento.id_documento
    }
