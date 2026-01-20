from django.shortcuts import get_object_or_404

from .models import (Bien, DocumentoSiniestro, Factura, Finiquito,
                     Notificacion, Poliza, ResponsableCustodio, Siniestro,
                     Usuario)


class UsuarioRepository:
    """Repositorio para operaciones de acceso a datos de Usuario"""

    @staticmethod
    def get_by_username(username: str):
        """Buscar usuario por nombre de usuario"""
        try:
            return Usuario.objects.get(username=username)
        except Usuario.DoesNotExist:
            return None

    @staticmethod
    def get_by_id(usuario_id):
        try:
            return Usuario.objects.get(id=usuario_id)
        except Usuario.DoesNotExist:
            return None

    @staticmethod
    def get_all_usuarios():
        return Usuario.objects.all()

    @staticmethod
    def create_usuario(data):
        return Usuario.objects.create_user(**data)

    @staticmethod
    def update_usuario(usuario_id, data):
        usuario = Usuario.objects.get(id=usuario_id)
        for key, value in data.items():
            setattr(usuario, key, value)
        usuario.save()
        return usuario

    @staticmethod
    def delete_usuario(usuario_id):
        Usuario.objects.filter(id=usuario_id).delete()


class PolizaRepository:
    """Repositorio para operaciones de acceso a datos de Pólizas"""

    @staticmethod
    def get_all():
        return Poliza.objects.all().order_by("-fecha_registro")

    @staticmethod
    def get_by_id(poliza_id):
        try:
            return Poliza.objects.get(id=poliza_id)
        except Poliza.DoesNotExist:
            return None

    @staticmethod
    def create(data):
        return Poliza.objects.create(**data)

    @staticmethod
    def update(poliza, data):
        for field, value in data.items():
            setattr(poliza, field, value)
        poliza.save()
        return poliza

    @staticmethod
    def delete(poliza):
        poliza.delete()


class SiniestroRepository:
    @staticmethod
    def get_all():
        return Siniestro.objects.all().order_by("-fecha_siniestro")

    @staticmethod
    def get_by_poliza(poliza_id):
        return Siniestro.objects.filter(poliza_id=poliza_id).order_by(
            "-fecha_siniestro"
        )

    @staticmethod
    def get_by_id(id):
        return Siniestro.objects.filter(id=id).first()

    @staticmethod
    def create(poliza, data, usuario):
        # Creamos la instancia manualmente para tener control total
        siniestro = Siniestro(
            poliza=poliza,
            # Asignamos el Custodio que viene del formulario
            custodio=data.get("custodio"),
            # Asignamos el Bien que viene del formulario
            bien=data.get("bien"),
            # Datos básicos
            fecha_siniestro=data.get("fecha_siniestro"),
            tipo_siniestro=data.get("tipo_siniestro"),
            ubicacion_bien=data.get("ubicacion_bien"),
            causa_siniestro=data.get("causa_siniestro"),
            # Datos opcionales
            cobertura_aplicada=data.get("cobertura_aplicada"),
            # Datos de auditoría
            usuario_gestor=usuario,
            estado_tramite="REPORTADO",  # Estado inicial por defecto
        )
        siniestro.save()
        return siniestro

    @staticmethod
    def update(siniestro_id, data):
        siniestro = get_object_or_404(Siniestro, id=siniestro_id)

        print("🔍 DEPURACIÓN - ACTUALIZACIÓN DE SINIESTRO")
        print(f"ANTES - Bien actual: {siniestro.bien}")
        print(f"ANTES - Custodio actual: {siniestro.custodio}")
        print(f"NUEVO - Bien a asignar: {data.get('bien')}")
        print(f"NUEVO - Custodio a asignar: {data.get('custodio')}")

        # Lista para llevar registro de qué campos estamos cambiando
        campos_a_actualizar = []

        # Actualizamos solo si el campo viene en el diccionario 'data'
        if "fecha_siniestro" in data:
            siniestro.fecha_siniestro = data.get("fecha_siniestro")
            campos_a_actualizar.append("fecha_siniestro")

        if "tipo_siniestro" in data:
            siniestro.tipo_siniestro = data.get("tipo_siniestro")
            campos_a_actualizar.append("tipo_siniestro")

        if "custodio" in data:
            siniestro.custodio = data.get("custodio")
            campos_a_actualizar.append("custodio")

        # ✅ LÍNEA FALTANTE - ASIGNAR EL BIEN
        if "bien" in data:
            siniestro.bien = data.get("bien")
            campos_a_actualizar.append("bien")
            print("✅ Bien asignado correctamente")

        if "nombre_bien" in data:
            siniestro.nombre_bien = data.get("nombre_bien")
            campos_a_actualizar.append("nombre_bien")

        if "ubicacion_bien" in data:
            siniestro.ubicacion_bien = data.get("ubicacion_bien")
            campos_a_actualizar.append("ubicacion_bien")

        if "causa_siniestro" in data:
            siniestro.causa_siniestro = data.get("causa_siniestro")
            campos_a_actualizar.append("causa_siniestro")

        if "estado_tramite" in data:
            siniestro.estado_tramite = data.get("estado_tramite")
            campos_a_actualizar.append("estado_tramite")

        # Campos opcionales adicionales
        if "cobertura_aplicada" in data:
            siniestro.cobertura_aplicada = data.get("cobertura_aplicada")
            campos_a_actualizar.append("cobertura_aplicada")

        if (
            "valor_reclamo_estimado" in data
            and data.get("valor_reclamo_estimado") is not None
        ):
            siniestro.valor_reclamo_estimado = data.get("valor_reclamo_estimado")
            campos_a_actualizar.append("valor_reclamo_estimado")

        # EL CAMBIO CLAVE:
        # Si hay campos para actualizar, usamos update_fields
        if campos_a_actualizar:
            print(f"🔄 Guardando cambios en campos: {campos_a_actualizar}")
            siniestro.save(update_fields=campos_a_actualizar)
            print(f"✅ DESPUÉS - Bien actualizado: {siniestro.bien}")
            print(f"✅ DESPUÉS - Custodio actualizado: {siniestro.custodio}")
        else:
            print("⚠️ No hay campos para actualizar")

        return siniestro


class FacturaRepository:
    """Repositorio para operaciones de acceso a datos de Facturas"""

    @staticmethod
    def get_all():
        # Ordenamos por fecha de emisión (más recientes primero)
        return Factura.objects.all().order_by("-fecha_emision")

    @staticmethod
    def get_by_id(factura_id):
        try:
            return Factura.objects.get(id=factura_id)
        except Factura.DoesNotExist:
            return None

    @staticmethod
    def create(data):
        # Al usar create(), Django llama internamente a save(),
        # por lo que tus cálculos automáticos (IVA, descuentos) SE EJECUTARÁN.
        return Factura.objects.create(**data)


# DocumentoSiniestroRepository


class DocumentoRepository:

    @staticmethod
    def create(data, archivo, usuario):
        """
        Crea el registro en BD.
        Nota: Django maneja la subida a MinIO automáticamente al llamar a .create()
        gracias a la configuración del settings.py.
        """
        return DocumentoSiniestro.objects.create(
            siniestro=data["siniestro"],
            tipo=data["tipo"],
            descripcion=data.get("descripcion", ""),
            archivo=archivo,  # El objeto archivo en memoria
            subido_por=usuario,
        )

    @staticmethod
    def get_by_siniestro(siniestro_id):
        return DocumentoSiniestro.objects.filter(siniestro_id=siniestro_id).order_by(
            "-fecha_subida"
        )

    @staticmethod
    def delete(documento_id):
        # Al borrar el registro, django-storages también intenta borrar el archivo en MinIO
        return DocumentoSiniestro.objects.filter(id=documento_id).delete()


class CustodioRepository:
    """Repositorio para gestión de Responsables/Custodios"""

    @staticmethod
    def get_all():
        return ResponsableCustodio.objects.all().order_by("nombre_completo")

    @staticmethod
    def get_by_id(custodio_id):
        try:
            return ResponsableCustodio.objects.get(id=custodio_id)
        except ResponsableCustodio.DoesNotExist:
            return None

    @staticmethod
    def create(data):
        return ResponsableCustodio.objects.create(**data)

    @staticmethod
    def update(custodio, data):
        for field, value in data.items():
            setattr(custodio, field, value)
        custodio.save()
        return custodio

    @staticmethod
    def delete(custodio_id):
        return ResponsableCustodio.objects.filter(id=custodio_id).delete()


class BienRepository:
    """Repositorio para acceso a datos de Activos Fijos (Bienes)"""

    @staticmethod
    def get_by_custodio(custodio_id):
        """Obtener todos los bienes asignados a un custodio"""
        return Bien.objects.filter(
            custodio_id=custodio_id, estado_operativo="ACTIVO"
        ).order_by("codigo")

    @staticmethod
    def get_by_id(bien_id):
        """Obtener un bien específico"""
        try:
            # Usamos select_related para traer datos del custodio en una sola consulta si fuera necesario
            return Bien.objects.select_related("custodio").get(id=bien_id)
        except Bien.DoesNotExist:
            return None


class FiniquitoRepository:
    """Repositorio para manejo de Finiquitos (Cierre de Siniestros)"""

    @staticmethod
    def create(datos_finiquito):
        """
        Crea el registro de finiquito.
        Nota: Los cálculos ya deben venir listos desde el Servicio.
        """
        return Finiquito.objects.create(**datos_finiquito)

    @staticmethod
    def get_by_siniestro(siniestro_id):
        """Busca si existe un finiquito para un siniestro dado"""
        try:
            return Finiquito.objects.get(siniestro_id=siniestro_id)
        except Finiquito.DoesNotExist:
            return None


class NotificacionRepository:
    """Repositorio para gestión de Notificaciones"""

    @staticmethod
    def crear(data):
        return Notificacion.objects.create(**data)

    @staticmethod
    def get_by_usuario(usuario):
        # Devuelve primero las más nuevas
        return Notificacion.objects.filter(usuario=usuario).order_by("-fecha_emision")

    @staticmethod
    def get_pendientes_count(usuario):
        return Notificacion.objects.filter(usuario=usuario, estado="PENDIENTE").count()

    @staticmethod
    def get_by_id(notificacion_id):
        try:
            return Notificacion.objects.get(id=notificacion_id)
        except Notificacion.DoesNotExist:
            return None

    @staticmethod
    def marcar_como_leida(notificacion):
        notificacion.estado = "LEIDA"
        notificacion.save()
        return notificacion
