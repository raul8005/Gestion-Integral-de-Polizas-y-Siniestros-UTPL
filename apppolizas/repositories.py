from .models import Usuario, Poliza, Siniestro, Factura, DocumentoSiniestro


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
        return Poliza.objects.all().order_by('-fecha_registro')

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
    """Repositorio para operaciones de acceso a datos de Siniestros"""

    @staticmethod
    def get_all():
        # Usamos select_related para optimizar la carga de la póliza relacionada
        return Siniestro.objects.select_related('poliza').all().order_by('-fecha_siniestro')

    @staticmethod
    def get_by_id(siniestro_id):
        try:
            return Siniestro.objects.get(id=siniestro_id)
        except Siniestro.DoesNotExist:
            return None

    @staticmethod
    def create(data):
        return Siniestro.objects.create(**data)

    @staticmethod
    def update(siniestro_instance, data):
        # 'data' es form.cleaned_data
        for key, value in data.items():
            setattr(siniestro_instance, key, value)
        
        # Esta línea es la que realmente guarda en la base de datos
        siniestro_instance.save() 
        return siniestro_instance

    @staticmethod
    def delete(siniestro_id):
        return Siniestro.objects.filter(id=siniestro_id).delete()
    
    @staticmethod
    def get_por_poliza(poliza_id):
        """Consulta directa al ORM filtrando por ID de póliza"""
        return Siniestro.objects.filter(poliza_id=poliza_id).order_by('-fecha_siniestro')
    
    
class FacturaRepository:
    """Repositorio para operaciones de acceso a datos de Facturas"""

    @staticmethod
    def get_all():
        # Ordenamos por fecha de emisión (más recientes primero)
        return Factura.objects.all().order_by('-fecha_emision')

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
            siniestro=data['siniestro'],
            tipo=data['tipo'],
            descripcion=data.get('descripcion', ''),
            archivo=archivo, # El objeto archivo en memoria
            subido_por=usuario
        )

    @staticmethod
    def get_by_siniestro(siniestro_id):
        return DocumentoSiniestro.objects.filter(siniestro_id=siniestro_id).order_by('-fecha_subida')

    @staticmethod
    def delete(documento_id):
        # Al borrar el registro, django-storages también intenta borrar el archivo en MinIO
        return DocumentoSiniestro.objects.filter(id=documento_id).delete()