from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Usuario(AbstractUser):
    # Heredamos id, username, password, email, first_name y last_name de AbstractUser

    ADMINISTRADOR = 'admin'
    ANALISTA = 'analista'
    
    TIPO_USUARIO_CHOICES = [
        (ADMINISTRADOR, 'Administrador'),
        (ANALISTA, 'Analista'),
    ]

    rol = models.CharField(
        max_length=20,
        choices=TIPO_USUARIO_CHOICES,
        default=ANALISTA
    )

    cedula = models.IntegerField(unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=15, null=True, blank=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.username} - {self.rol}"

class Poliza(models.Model):
    numero_poliza = models.CharField(max_length=50, unique=True)
    vigencia_inicio = models.DateField()
    vigencia_fin = models.DateField()
    monto_asegurado = models.IntegerField()
    tipo_poliza = models.CharField(max_length=100)
    prima_base = models.FloatField()  
    prima_total = models.FloatField()
    estado = models.CharField(max_length=20)
    renovable = models.BooleanField(default=False)
    fecha_emision = models.DateField()
    fecha_registro = models.DateField(auto_now_add=True)
    
    # RELACIÓN: Uno a Muchos (Un administrador gestiona muchas pólizas)
    usuario_gestor = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='polizas_gestionadas'
    )

    def __str__(self):
        return self.numero_poliza
    

class Siniestro(models.Model):
    # Identificación del Siniestro 
    numero_reclamo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    # RELACIÓN 1: Agregación (1 Póliza -> * Siniestros)
    # Se usa ForeignKey para representar la multiplicidad 1 a muchos desde la Póliza.
    poliza = models.ForeignKey(
        Poliza, 
        on_delete=models.CASCADE, 
        related_name='siniestros'
    )
    # RELACIÓN 2: Asociación (1 Usuario -> * Siniestros)
    # El usuario que gestiona o registra el siniestro.
    usuario_gestor = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='siniestros_gestionados'
    )

    # Datos clave del siniestro y del bien afectado [cite: 88, 91, 93]
    fecha_siniestro = models.DateField()
    tipo_siniestro = models.CharField(max_length=100) # Ej: Robo, Incendio, Daños
    ubicacion_bien = models.CharField(max_length=255)
    causa_siniestro = models.TextField()
    
    # Detalles del bien asegurado [cite: 88, 91]
    nombre_bien = models.CharField(max_length=100)
    marca = models.CharField(max_length=50, null=True, blank=True)
    modelo = models.CharField(max_length=50, null=True, blank=True)
    serie = models.CharField(max_length=50, null=True, blank=True)
    codigo_activo = models.CharField(max_length=50, null=True, blank=True)
    responsable_custodio = models.CharField(max_length=150) # [cite: 92]

    # Estado y Gestión del Trámite [cite: 87]
    ESTADO_CHOICES = [
        ('REPORTADO', 'Reportado'),
        ('DOCUMENTACION', 'En validación de documentos'),
        ('ENVIADO_ASEGURADORA', 'Enviado a Aseguradora'),
        ('LIQUIDADO', 'Liquidado'),
        ('RECHAZADO', 'Rechazado'),
    ]
    estado_tramite = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='REPORTADO')
    fecha_notificacion = models.DateField(auto_now_add=True) # Fecha inicial del reporte [cite: 86]
    cobertura_aplicada = models.CharField(max_length=100, null=True, blank=True) # [cite: 87]

    # Datos de Liquidación y Finiquito 
    valor_reclamo = models.FloatField(default=0.0) # Valor total reclamado
    deducible_aplicado = models.FloatField(default=0.0)
    depreciacion = models.FloatField(default=0.0)
    valor_a_pagar = models.FloatField(default=0.0) # Valor final a pagar

 
class Factura(models.Model):
    # RELACIÓN: Una Póliza -> Muchas Facturas
    poliza = models.ForeignKey(
        'Poliza', # Usamos string para evitar problemas de orden de declaración
        on_delete=models.CASCADE,
        related_name='facturas'
    )

    # DATOS DE ENTRADA
    numero_factura = models.CharField(max_length=50, unique=True)
    documento_contable = models.CharField(max_length=50, null=True, blank=True)
    fecha_emision = models.DateField()
    fecha_pago = models.DateField(null=True, blank=True)
    
    # VALORES MONETARIOS
    prima = models.FloatField(help_text="Valor de la prima sobre la cual se calculan impuestos")
    retenciones = models.FloatField(default=0.0)

    # CAMPOS CALCULADOS AUTOMÁTICAMENTE
    contribucion_super = models.FloatField(default=0.0)  
    seguro_campesino = models.FloatField(default=0.0)    
    derechos_emision = models.FloatField(default=0.0)    
    
    base_imponible = models.FloatField(default=0.0)      
    iva = models.FloatField(default=0.0)                 
    
    descuento_pronto_pago = models.FloatField(default=0.0)
    total_facturado = models.FloatField(default=0.0)     
    valor_a_pagar = models.FloatField(default=0.0)       

    # ESTADO
    mensaje_resultado = models.CharField(max_length=255, null=True, blank=True)
    pagado = models.BooleanField(default=False)

    def calcular_derechos_emision(self):
        if self.prima <= 250:
            return 0.50
        elif self.prima <= 500:
            return 1.00
        elif self.prima <= 1000:
            return 3.00
        elif self.prima <= 2000:
            return 5.00
        elif self.prima <= 4000:
            return 7.00
        else:
            return 9.00 

    def calcular_descuento(self):
        # Solo aplica si hay fecha de pago registrada
        if self.fecha_pago and self.fecha_emision:
            dias_diferencia = (self.fecha_pago - self.fecha_emision).days
            # Si se paga dentro de los 20 días siguientes a la emisión
            if dias_diferencia <= 20:
                return self.prima * 0.05
        return 0.0

    def save(self, *args, **kwargs):
        # 1. Calcular Contribuciones Legales
        self.contribucion_super = round(self.prima * 0.035, 2)
        self.seguro_campesino = round(self.prima * 0.005, 2)

        # 2. Calcular Derechos de Emisión
        self.derechos_emision = self.calcular_derechos_emision()

        # 3. Calcular Base Imponible
        self.base_imponible = round(
            self.prima + self.contribucion_super + self.seguro_campesino + self.derechos_emision, 2
        )

        # 4. Calcular IVA (15%)
        self.iva = round(self.base_imponible * 0.15, 2)

        # 5. Calcular Total Facturado
        self.total_facturado = round(self.base_imponible + self.iva, 2)

        # 6. Calcular Descuento Pronto Pago
        self.descuento_pronto_pago = round(self.calcular_descuento(), 2)

        # 7. Calcular Valor Final a Pagar
        self.valor_a_pagar = round(
            self.total_facturado - self.retenciones - self.descuento_pronto_pago, 2
        )

        # Actualizar estado de mensaje
        if self.valor_a_pagar <= 0:
             self.mensaje_resultado = "Factura Saldada"
        elif self.pagado:
             self.mensaje_resultado = "Pagado"
        else:
             self.mensaje_resultado = "Pendiente de Pago"
        
        super(Factura, self).save(*args, **kwargs)

    def __str__(self):
        return f"Factura {self.numero_factura} - Póliza {self.poliza}"




# Documentos adjuntos a siniestros

def ruta_documento_siniestro(instance, filename):
    # Esto genera rutas como: siniestros/ID_123/evidencia_policial.pdf
    return f'siniestros/ID_{instance.siniestro.id}/{filename}'

class DocumentoSiniestro(models.Model):
    TIPO_DOCUMENTO = [
        ('INFORME', 'Informe del Siniestro'),
        ('FOTOS', 'Fotografías del Siniestro'),
        ('CEDULA', 'Documentos Personales'),
        ('FACTURA', 'Facturas de Gastos'),
        ('OTRO', 'Otros Documentos'),
    ]

    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name='documentos')
    archivo = models.FileField(upload_to=ruta_documento_siniestro)
    tipo = models.CharField(max_length=20, choices=TIPO_DOCUMENTO)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    # Usuario que subió el archivo (para auditoría)
    subido_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.siniestro.id}"
    

# ========================================================
# SEÑALES PARA LIMPIEZA DE ARCHIVOS EN MINIO
# ========================================================

@receiver(post_delete, sender=DocumentoSiniestro)
def eliminar_archivo_de_minio(sender, instance, **kwargs):
    """
    Se ejecuta automáticamente justo después de que se borra un 
    registro de la tabla DocumentoSiniestro.
    """
    if instance.archivo:
        # Esto borra el archivo físico del bucket de MinIO
        instance.archivo.delete(save=False)