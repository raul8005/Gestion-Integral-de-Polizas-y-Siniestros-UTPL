
import jwt
import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate

from datetime import date
from .models import Usuario, Poliza, Siniestro, Factura
from .repositories import UsuarioRepository, PolizaRepository, SiniestroRepository, FacturaRepository, DocumentoRepository

import os


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

        if not hasattr(user, 'rol'):
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
            'id': user.id,
            'username': user.username,
            'rol': user.rol,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2),
            'iat': datetime.datetime.utcnow()
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        return token


class PolizaService:
    """Servicio para gestión de Pólizas"""

    @staticmethod
    def listar_polizas():
        return PolizaRepository.get_all()

    @staticmethod
    def crear_poliza(data):
        if data.get('prima_total') < data.get('prima_base'):
            raise ValidationError("La prima total no puede ser menor a la prima base")

        return PolizaRepository.create(data)

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
        return Poliza.objects.filter(estado='Activa').count()
    
    @staticmethod
    def contar_polizas_vencidas():
        return Poliza.objects.filter(vigencia_fin__lt=date.today()).count()
    
#---------------------
# SINIESTRO
class SiniestroService:

    @staticmethod
    def crear_siniestro(*, poliza_id, data, usuario):
        # 1. Usar el repositorio de pólizas para obtener la instancia
        poliza = PolizaRepository.get_by_id(poliza_id)
        if not poliza:
            raise ValidationError("La póliza no existe")
            
        # 2. Preparar el diccionario de datos para el repositorio de siniestros
        data['poliza'] = poliza
        data['usuario_gestor'] = usuario
        
        # 3. Guardar a través del repositorio
        return SiniestroRepository.create(data)
    
    @staticmethod
    def listar_todos():
        # USAR EL REPOSITORIO
        return SiniestroRepository.get_all()

    @staticmethod
    def actualizar_siniestro(siniestro_id, data):
        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        if not siniestro:
            raise ValidationError("El siniestro no existe")
        
        if siniestro.estado_tramite == 'LIQUIDADO':
            raise ValidationError("No se puede editar un siniestro ya liquidado")
            
        # IMPORTANTE: No pasar campos que el repositorio no deba tocar
        # aunque el formulario ya los excluye por el 'exclude' del Meta
        return SiniestroRepository.update(siniestro, data)
    
    @staticmethod
    def listar_por_poliza(poliza_id):
        """Lógica de negocio para obtener siniestros de una póliza específica"""
        return SiniestroRepository.get_por_poliza(poliza_id)
    

class FacturaService:
    """Servicio para gestión de Facturación y Cobranzas"""

    @staticmethod
    def listar_facturas():
        return FacturaRepository.get_all()

    @staticmethod
    def crear_factura(data):
        # Aquí podrías agregar validaciones extra si quisieras antes de crear
        # Por ahora, delegamos al repositorio
        return FacturaRepository.create(data)

    @staticmethod
    def obtener_factura(factura_id):
        factura = FacturaRepository.get_by_id(factura_id)
        if not factura:
            raise ValidationError("La factura solicitada no existe")
        return factura





  # Servicio para gestión de Documentos de Siniestros

class DocumentoService:
        
    # Extensiones permitidas (Seguridad)
    EXTENSIONES_VALIDAS = ['.pdf', '.jpg', '.jpeg', '.png']
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
        if siniestro.estado_tramite == 'LIQUIDADO':
            raise ValidationError("No se pueden agregar documentos a un siniestro liquidado.")

        # 3. Validar extensión del archivo
        ext = os.path.splitext(archivo.name)[1].lower()
        if ext not in DocumentoService.EXTENSIONES_VALIDAS:
            raise ValidationError(f"Formato no permitido. Use: {', '.join(DocumentoService.EXTENSIONES_VALIDAS)}")

        # 4. Validar tamaño
        if archivo.size > DocumentoService.MAX_TAMANO_MB:
            raise ValidationError("El archivo es demasiado pesado. Máximo 5MB.")

        # 5. Preparar datos para el repositorio
        datos_limpios = {
            'siniestro': siniestro,
            'tipo': data_form['tipo'],
            'descripcion': data_form.get('descripcion')
        }

        # 6. Llamar al repositorio
        return DocumentoRepository.create(datos_limpios, archivo, usuario)

    @staticmethod
    def listar_evidencias(siniestro_id):
        return DocumentoRepository.get_by_siniestro(siniestro_id)