import datetime
import os
from datetime import date
from decimal import Decimal

import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Factura, Finiquito, Notificacion, Poliza, Siniestro, Usuario
from .repositories import (
    BienRepository,
    CustodioRepository,
    DocumentoRepository,
    FacturaRepository,
    FiniquitoRepository,
    NotificacionRepository,
    PolizaRepository,
    SiniestroRepository,
    UsuarioRepository,
)


class AuthService:
    """Servicio de Autenticación y Reglas de Negocio"""

    @staticmethod
    def login_universal(username, password):
        """
        Login estándar para el sistema web (admin / analista)
        Usa el sistema de autenticación de Django
        """
        if not username or not password:
            raise ValidationError("Usuario y contraseña son obligatorios")

        user = authenticate(username=username, password=password)

        if user is None:
            raise ValidationError("Credenciales inválidas")

        if not hasattr(user, "rol"):
            raise ValidationError("El usuario no tiene un rol asignado")

        return user, user.rol

    @staticmethod
    def login_analista(username, password):
        """
        Login con JWT solo para analistas (API / servicios)
        """
        if not username or not password:
            raise ValidationError("Usuario y contraseña son obligatorios")

        user = UsuarioRepository.get_by_username(username)

        if not user or not user.check_password(password):
            raise ValidationError("Credenciales inválidas")

        if user.rol != Usuario.ANALISTA:
            raise ValidationError("Acceso denegado. Este usuario no es Analista.")

        payload = {
            "id": user.id,
            "username": user.username,
            "rol": user.rol,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2),
            "iat": datetime.datetime.utcnow(),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        return token


class PolizaService:
    """Servicio para gestión de Pólizas"""

    @staticmethod
    def listar_polizas():
        return PolizaRepository.get_all()

    @staticmethod
    def crear_poliza(data):
        # 1. Validaciones
        if data.get("prima_total") < data.get("prima_base"):
            raise ValidationError("La prima total no puede ser menor a la prima base")

        # 2. Crear la póliza
        poliza = PolizaRepository.create(data)

        # 3. --- NUEVO: GENERAR NOTIFICACIÓN AUTOMÁTICA ---
        # Verificamos si hay un usuario gestor asociado para enviarle la alerta
        usuario = data.get("usuario_gestor")

        if usuario:
            # Usamos NotificacionRepository directamente para evitar errores de orden de lectura
            NotificacionRepository.crear(
                {
                    "usuario": usuario,
                    "tipo_alerta": "VENCIMIENTO_POLIZA",  # Usamos este tipo o 'OTRO' para indicar nueva creación
                    "mensaje": f"Se ha registrado exitosamente la nueva póliza {poliza.numero_poliza}.",
                    "estado": "PENDIENTE",
                    "id_referencia": str(poliza.id),
                }
            )
        # -------------------------------------------------

        return poliza

    @staticmethod
    def obtener_poliza(poliza_id):
        poliza = PolizaRepository.get_by_id(poliza_id)
        if not poliza:
            raise ValidationError("La póliza no existe")
        return poliza

    @staticmethod
    def actualizar_poliza(poliza_id, data):
        poliza = PolizaRepository.get_by_id(poliza_id)
        if not poliza:
            raise ValidationError("La póliza no existe")
        return PolizaRepository.update(poliza, data)

    @staticmethod
    def eliminar_poliza(poliza_id):
        poliza = PolizaRepository.get_by_id(poliza_id)
        if not poliza:
            raise ValidationError("La póliza no existe")
        PolizaRepository.delete(poliza)

    @staticmethod
    def contar_polizas_activas():
        return Poliza.objects.filter(estado=True).count()

    @staticmethod
    def contar_polizas_vencidas():
        return Poliza.objects.filter(vigencia_fin__lt=date.today()).count()


# ---------------------
# SINIESTRO
class SiniestroService:
    @staticmethod
    def listar_todos():
        return SiniestroRepository.get_all()

    @staticmethod
    def listar_por_poliza(poliza_id):
        return SiniestroRepository.get_by_poliza(poliza_id)

    @staticmethod
    def crear_siniestro(poliza, data, usuario):
        """
        Crea un siniestro y notifica al usuario (solo texto).
        """

        # 1. Validaciones de Negocio
        if not poliza.estado:
            raise ValidationError(
                "No se puede registrar un siniestro en una póliza inactiva."
            )

        # 2. Guardar el siniestro
        siniestro = SiniestroRepository.create(poliza, data, usuario)

        # 3. --- NUEVO: NOTIFICACIÓN DE SINIESTRO ---
        if usuario:
            NotificacionRepository.crear(
                {
                    "usuario": usuario,
                    "tipo_alerta": "OTRO",
                    # AQUÍ USAMOS EL BIEN PARA OBTENER EL NOMBRE:
                    "mensaje": f"Nuevo Siniestro registrado en la póliza {poliza.numero_poliza}. Bien afectado: {siniestro.bien.detalle}",
                    "estado": "PENDIENTE",
                    "id_referencia": str(siniestro.id),
                }
            )
        # -------------------------------------------

        return siniestro

    @staticmethod
    def actualizar_siniestro(siniestro_id, data):
        return SiniestroRepository.update(siniestro_id, data)


class FacturaService:
    """Servicio para gestión de Facturación y Cobranzas"""

    @staticmethod
    def listar_facturas():
        return FacturaRepository.get_all()

    @staticmethod
    def crear_factura(data):
        # 1. Primero creamos la factura normalmente
        factura = FacturaRepository.create(data)

        # 2. --- NUEVO: ALERTA DE COBRANZA AUTOMÁTICA ---
        # Buscamos al dueño de la póliza para avisarle
        usuario_destino = factura.poliza.usuario_gestor

        if usuario_destino:
            NotificacionRepository.crear(
                {
                    "usuario": usuario_destino,
                    "tipo_alerta": "PAGO_PENDIENTE",  # <--- Esto pone el ícono de Cobranza/Dinero
                    "mensaje": f"Nueva Factura {factura.numero_factura} generada. Valor a pagar: ${factura.valor_a_pagar}",
                    "estado": "PENDIENTE",
                    "id_referencia": str(factura.id),
                }
            )
        # ------------------------------------------------

        return factura

    @staticmethod
    def obtener_factura(factura_id):
        factura = FacturaRepository.get_by_id(factura_id)
        if not factura:
            raise ValidationError("La factura solicitada no existe")
        return factura


# Servicio para gestión de Documentos de Siniestros


class DocumentoService:

    # Extensiones permitidas (Seguridad)
    EXTENSIONES_VALIDAS = [".pdf", ".jpg", ".jpeg", ".png"]
    # Tamaño máximo (5MB)
    MAX_TAMANO_MB = 5 * 1024 * 1024

    @staticmethod
    def subir_evidencia(siniestro_id, data_form, archivo, usuario):
        """
        Lógica de negocio para validar y subir un archivo.
        """
        # 1. Validar existencia del siniestro
        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        if not siniestro:
            raise ValidationError("El siniestro no existe.")

        # 2. Validar que el siniestro no esté cerrado (Regla de negocio)
        if siniestro.estado_tramite == "LIQUIDADO":
            raise ValidationError(
                "No se pueden agregar documentos a un siniestro liquidado."
            )

        # 3. Validar extensión del archivo
        ext = os.path.splitext(archivo.name)[1].lower()
        if ext not in DocumentoService.EXTENSIONES_VALIDAS:
            raise ValidationError(
                f"Formato no permitido. Use: {', '.join(DocumentoService.EXTENSIONES_VALIDAS)}"
            )

        # 4. Validar tamaño
        if archivo.size > DocumentoService.MAX_TAMANO_MB:
            raise ValidationError("El archivo es demasiado pesado. Máximo 5MB.")

        # 5. Preparar datos para el repositorio
        datos_limpios = {
            "siniestro": siniestro,
            "tipo": data_form["tipo"],
            "descripcion": data_form.get("descripcion"),
        }

        # 6. Llamar al repositorio
        return DocumentoRepository.create(datos_limpios, archivo, usuario)

    @staticmethod
    def listar_evidencias(siniestro_id):
        return DocumentoRepository.get_by_siniestro(siniestro_id)


class CustodioService:
    """Servicio para gestión de Custodios"""

    @staticmethod
    def listar_custodios():
        return CustodioRepository.get_all()

    @staticmethod
    def crear_custodio(data):
        # Validar duplicados de cédula si es necesario (aunque el modelo ya tiene unique=True)
        return CustodioRepository.create(data)

    @staticmethod
    def obtener_custodio(custodio_id):
        custodio = CustodioRepository.get_by_id(custodio_id)
        if not custodio:
            raise ValidationError("El custodio no existe")
        return custodio

    @staticmethod
    def actualizar_custodio(custodio_id, data):
        custodio = CustodioRepository.get_by_id(custodio_id)
        if not custodio:
            raise ValidationError("El custodio no existe")
        return CustodioRepository.update(custodio, data)

    @staticmethod
    def eliminar_custodio(custodio_id):
        # Aquí podrías validar si tiene siniestros asociados antes de borrar
        # (Django lanzará error de integridad ProtectedError por on_delete=models.PROTECT,
        # pero es bueno manejarlo)
        try:
            CustodioRepository.delete(custodio_id)
        except Exception as e:
            raise ValidationError(
                "No se puede eliminar: El custodio tiene siniestros asociados."
            )


class BienService:
    """Servicio de Negocio para gestión de Bienes"""

    @staticmethod
    def listar_por_custodio(custodio_id):
        # Validamos que el custodio exista antes de buscar sus bienes
        custodio = CustodioRepository.get_by_id(custodio_id)
        if not custodio:
            raise ValidationError("El custodio solicitado no existe.")

        return BienRepository.get_by_custodio(custodio_id).select_related("custodio")

    @staticmethod
    def obtener_detalle_bien(bien_id):
        bien = BienRepository.get_by_id(bien_id)
        if not bien:
            raise ValidationError("El bien no existe.")
        return bien


class FiniquitoService:
    """Lógica de negocio para Liquidación de Siniestros"""

    @staticmethod
    def liquidar_siniestro(siniestro_id, data, archivo_firmado, usuario):
        """
        Procesa la liquidación: Cálculos, creación de registro y cambio de estado.
        Todo envuelto en una transacción atómica para evitar datos inconsistentes.
        """
        # 1. Obtener Siniestro
        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        if not siniestro:
            raise ValidationError("El siniestro no existe.")

        # 2. Validar que no esté ya liquidado (Evita duplicados lógicos)
        if siniestro.estado_tramite == "LIQUIDADO":
            raise ValidationError("Este siniestro ya ha sido liquidado.")

        # 3. Lógica de Cálculo Financiero
        valor_reclamo = Decimal(data["valor_total_reclamo"])
        deducible = Decimal(data["valor_deducible"])
        depreciacion = Decimal(data["valor_depreciacion"])

        # Fórmula: Reclamo - Deducible - Depreciación
        valor_final = valor_reclamo - deducible - depreciacion

        if valor_final < 0:
            valor_final = Decimal("0.00")

        # 4. Preparar datos para persistencia
        datos_finiquito = {
            "siniestro": siniestro,
            "fecha_finiquito": data["fecha_finiquito"],
            "id_finiquito": data.get("id_finiquito"),
            "valor_total_reclamo": valor_reclamo,
            "valor_deducible": deducible,
            "valor_depreciacion": depreciacion,
            "valor_final_pago": valor_final,
            "documento_firmado": archivo_firmado,
            "pagado_a_usuario": False,
        }

        # --- INICIO DE TRANSACCIÓN ---
        with transaction.atomic():
            # 5. Guardar Finiquito (Repositorio)
            # Si esto falla (ej. error de almacenamiento en MinIO), se detiene aquí.
            finiquito = FiniquitoRepository.create(datos_finiquito)

            # 6. Actualizar Estado del Siniestro
            # Si esto falla (ej. IntegrityError por campos nulos), se hace ROLLBACK del paso 5.
            SiniestroRepository.update(siniestro.id, {"estado_tramite": "LIQUIDADO"})

            return finiquito
        # --- FIN DE TRANSACCIÓN ---


class NotificacionService:
    """Servicio de Negocio para Notificaciones"""

    @staticmethod
    def crear_notificacion(usuario, tipo, mensaje, id_ref=None):
        data = {
            "usuario": usuario,
            "tipo_alerta": tipo,
            "mensaje": mensaje,
            "id_referencia": id_ref,
            "estado": "PENDIENTE",
        }
        return NotificacionRepository.crear(data)

    @staticmethod
    def listar_mis_notificaciones(usuario):
        return NotificacionRepository.get_by_usuario(usuario)

    @staticmethod
    def contar_no_leidas(usuario):
        return NotificacionRepository.get_pendientes_count(usuario)

    @staticmethod
    def leer_notificacion(notificacion_id, usuario):
        # Verificamos que la notificación exista y pertenezca al usuario
        noti = NotificacionRepository.get_by_id(notificacion_id)
        if noti and noti.usuario.id == usuario.id:
            return NotificacionRepository.marcar_como_leida(noti)
        return None
