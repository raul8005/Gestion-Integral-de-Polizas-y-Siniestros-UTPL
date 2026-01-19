from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date
from decimal import Decimal
from django.db.models.signals import post_delete
from django.dispatch import receiver

# ========================================================
# 1. GESTIÓN DE USUARIOS Y ROLES
# ========================================================

class Usuario(AbstractUser):
    ADMINISTRADOR = 'admin'
    ANALISTA = 'analista'
    GERENTE = 'gerente'
    SOLICITANTE = 'solicitante'
    
    TIPO_USUARIO_CHOICES = [
        (ADMINISTRADOR, 'Administrador'),
        (ANALISTA, 'Analista de Seguros'),
        (GERENTE, 'Gerencia'),
        (SOLICITANTE, 'Solicitante'),
    ]

    rol = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES, default=ANALISTA)
    cedula = models.CharField(max_length=10, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=15, null=True, blank=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.username} - {self.rol}"

# ========================================================
# 2. ENTIDADES EXTERNAS Y CUSTODIOS
# ========================================================

class Aseguradora(models.Model):
    nombre = models.CharField(max_length=100)
    ruc = models.CharField(max_length=13, unique=True)
    contacto = models.CharField(max_length=100)
    email_contacto = models.EmailField()
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre

class Broker(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.EmailField() # Para notificación automática
    id_broker = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return self.nombre

class ResponsableCustodio(models.Model):
    """
    Representa a la persona responsable del bien (Custodio) en la UTPL.
    Datos extraídos del Encabezado del Acta de Entrega.
    """
    nombre_completo = models.CharField(max_length=150, verbose_name="Custodio")
    identificacion = models.CharField(max_length=20, unique=True, verbose_name="Cédula")
    correo = models.EmailField() 
    departamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Departamento/Carrera")
    
    # Campos nuevos agregados según la imagen del Acta
    ciudad = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: Loja - CPL")
    edificio = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: Edificio D")
    puesto = models.CharField(max_length=150, blank=True, null=True, help_text="Ej: D4D06-6-PUESTO DE DOCENTE")

    def __str__(self):
        return f"{self.nombre_completo} ({self.identificacion})"
    
# ========================================================
# 3. Bien
# ========================================================

class Bien(models.Model):
    """
    Representa los activos fijos asignados a un custodio.
    Basado en la tabla del Acta de Entrega Recepción.
    """
    ESTADO_BIEN_CHOICES = [
        ('B', 'Bueno'),
        ('R', 'Regular'),
        ('M', 'Malo'),
    ]

    # Relación: Un custodio tiene varios bienes (1 a 5)
    custodio = models.ForeignKey(ResponsableCustodio, on_delete=models.CASCADE, related_name='bienes')

    # Columnas extraídas de la imagen
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código")
    baan_v = models.CharField(max_length=50, blank=True, null=True, verbose_name="BAAN V")
    detalle = models.TextField(verbose_name="Detalle / Descripción")
    serie = models.CharField(max_length=100, blank=True, null=True, default='No aplica')
    modelo = models.CharField(max_length=100, blank=True, null=True, default='No aplica')
    marca = models.CharField(max_length=100, blank=True, null=True)
    ubicacion = models.CharField(max_length=100, default='Sala H - Computo', verbose_name="Ubicación")
    
    # Estado marcado con X en la imagen (B/R)
    estado_fisico = models.CharField(max_length=1, choices=ESTADO_BIEN_CHOICES, default='B', verbose_name="Estado Físico")

    # Nuevo campo para estado operativo
    ESTADO_OPERATIVO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]
    estado_operativo = models.CharField(max_length=10, choices=ESTADO_OPERATIVO_CHOICES, default='ACTIVO', verbose_name="Estado Operativo")

    def clean(self):
        """Validación personalizada para limitar a 5 bienes por custodio"""
        from django.core.exceptions import ValidationError
        
        # Si es un registro nuevo (no tiene ID aún) verificamos el conteo actual
        if self.pk is None:
            cantidad_actual = self.custodio.bienes.count()
            if cantidad_actual >= 5:
                raise ValidationError(f"El custodio {self.custodio.nombre_completo} ya tiene el máximo permitido de 5 bienes asignados.")

    def save(self, *args, **kwargs):
        self.clean() # Ejecutar validación antes de guardar
        super(Bien, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.detalle[:30]}... ({self.codigo})"

# ========================================================
# 3. GESTIÓN DE PÓLIZAS
# ========================================================

class Poliza(models.Model):
    numero_poliza = models.CharField(max_length=50, unique=True)
    
    # IMPORTANTE: Si aún no tienes datos de aseguradora/broker creados, 
    # podrías necesitar null=True temporalmente si ya tienes datos en BD, 
    # pero según el diseño deben ser obligatorios.
    aseguradora = models.ForeignKey(Aseguradora, on_delete=models.PROTECT, related_name='polizas')
    broker = models.ForeignKey(Broker, on_delete=models.PROTECT, related_name='polizas')
    
    vigencia_inicio = models.DateField()
    vigencia_fin = models.DateField()
    monto_asegurado = models.DecimalField(max_digits=15, decimal_places=2)
    
    ramo = models.CharField(max_length=100) 
    objeto_asegurado = models.CharField(max_length=100) 
    
    prima_base = models.DecimalField(max_digits=12, decimal_places=2)  
    prima_total = models.DecimalField(max_digits=12, decimal_places=2)
    
    estado = models.BooleanField(default=True)
    renovable = models.BooleanField(default=False)
    fecha_emision = models.DateField()
    fecha_registro = models.DateField(auto_now_add=True)
    
    usuario_gestor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Póliza {self.numero_poliza}"

class DocumentoPoliza(models.Model):
    poliza = models.ForeignKey(Poliza, related_name='documentos', on_delete=models.CASCADE)
    archivo = models.FileField(upload_to='polizas/')
    tipo = models.CharField(max_length=50) 
    fecha_subida = models.DateTimeField(auto_now_add=True)

# ========================================================
# 4. GESTIÓN DE SINIESTROS
# ========================================================

class Siniestro(models.Model):
    numero_reclamo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    
    poliza = models.ForeignKey(Poliza, on_delete=models.CASCADE, related_name='siniestros')
    
    # Vinculación con el custodio (Responsable)
    custodio = models.ForeignKey(
        ResponsableCustodio, 
        on_delete=models.PROTECT, 
        related_name='siniestros',
        verbose_name="Responsable o Custodio"
    )

    # NUEVO: Vinculación directa con el activo fijo afectado
    bien = models.ForeignKey(
        Bien, 
        on_delete=models.PROTECT, 
        related_name='siniestros',
        verbose_name="Bien Afectado"
    )

    usuario_gestor = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)

    # Datos del evento
    fecha_siniestro = models.DateField()
    fecha_notificacion = models.DateField(auto_now_add=True)
    tipo_siniestro = models.CharField(max_length=100)
    
    # Se mantiene 'ubicacion' porque el siniestro puede ocurrir fuera del puesto habitual del bien
    ubicacion_bien = models.CharField(
        max_length=255, 
        help_text="Lugar exacto donde ocurrió el siniestro"
    )
    causa_siniestro = models.TextField()

    # Estado del Trámite
    ESTADO_CHOICES = [
        ('REPORTADO', 'Reportado'),
        ('DOCUMENTACION', 'En validación'),
        ('ENVIADO_ASEGURADORA', 'Enviado a Aseguradora'),
        ('REPARACION', 'Reparación/Observación'),
        ('LIQUIDADO', 'Liquidado'),
        ('RECHAZADO', 'Rechazado'),
    ]
    estado_tramite = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='REPORTADO')
    cobertura_aplicada = models.CharField(max_length=100, null=True, blank=True)

    # Nuevo campo para el resultado de la reparación
    RESULTADO_CHOICES = [
        ('ARREGLADO', 'Arreglado'),
        ('REEMPLAZADO', 'Reemplazado'),
    ]
    resultado = models.CharField(max_length=20, choices=RESULTADO_CHOICES, null=True, blank=True)
    
    # Valor estimado inicial
    valor_reclamo_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def clean(self):
        """
        Validación opcional: Verificar que el Bien seleccionado 
        realmente pertenezca al Custodio seleccionado.
        """
        from django.core.exceptions import ValidationError
        if self.bien.custodio != self.custodio:
            raise ValidationError(f"El bien '{self.bien.detalle}' no pertenece al custodio {self.custodio.nombre_completo}.")

    def save(self, *args, **kwargs):
        self.clean()
        super(Siniestro, self).save(*args, **kwargs)

    def __str__(self):
        return f"Siniestro {self.id} - {self.bien.detalle[:20]}..."

# ========================================================
# 5. LIQUIDACIÓN Y FINIQUITO
# ========================================================

class Finiquito(models.Model):
    siniestro = models.OneToOneField(Siniestro, on_delete=models.CASCADE, related_name='finiquito')
    
    fecha_finiquito = models.DateField()
    id_finiquito = models.CharField(max_length=50, null=True, blank=True)
    
    valor_total_reclamo = models.DecimalField(max_digits=12, decimal_places=2, help_text="Monto bruto reclamado")
    valor_deducible = models.DecimalField(max_digits=12, decimal_places=2, help_text="Deducible aplicado") 
    valor_depreciacion = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Depreciación del bien") 
    valor_final_pago = models.DecimalField(max_digits=12, decimal_places=2, help_text="Valor líquido a recibir") 
    
    documento_firmado = models.FileField(upload_to='finiquitos/', null=True, blank=True)
    
    fecha_pago_realizado = models.DateField(null=True, blank=True)
    pagado_a_usuario = models.BooleanField(default=False)

    def __str__(self):
        return f"Finiquito {self.id_finiquito} - Siniestro {self.siniestro.id}"

# ========================================================
# 6. FACTURACIÓN Y PAGOS
# ========================================================

class Factura(models.Model):
    poliza = models.ForeignKey(Poliza, on_delete=models.CASCADE, related_name='facturas')
    numero_factura = models.CharField(max_length=50, unique=True)
    documento_contable = models.CharField(max_length=50, null=True, blank=True)
    fecha_emision = models.DateField()
    fecha_pago = models.DateField(null=True, blank=True)
    
    prima = models.DecimalField(max_digits=12, decimal_places=2, help_text="Valor de la prima")
    
    contribucion_super = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    seguro_campesino = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    derechos_emision = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    base_imponible = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_facturado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    retenciones = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_pronto_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_a_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    mensaje_resultado = models.CharField(max_length=255, null=True, blank=True)
    pagado = models.BooleanField(default=False)

    def calcular_derechos_emision(self):
        if self.prima <= 250: return Decimal('0.50')
        elif self.prima <= 500: return Decimal('1.00')
        elif self.prima <= 1000: return Decimal('3.00')
        elif self.prima <= 2000: return Decimal('5.00')
        elif self.prima <= 4000: return Decimal('7.00')
        else: return Decimal('9.00')

    def calcular_descuento(self):
        if self.fecha_pago and self.fecha_emision:
            dias_diferencia = (self.fecha_pago - self.fecha_emision).days
            if dias_diferencia <= 20:
                return self.prima * Decimal('0.05')
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        self.contribucion_super = round(self.prima * Decimal('0.035'), 2)
        self.seguro_campesino = round(self.prima * Decimal('0.005'), 2)
        self.derechos_emision = self.calcular_derechos_emision()
        self.base_imponible = (self.prima + self.contribucion_super + self.seguro_campesino + self.derechos_emision)
        self.iva = round(self.base_imponible * Decimal('0.15'), 2)
        self.total_facturado = self.base_imponible + self.iva
        self.descuento_pronto_pago = round(self.calcular_descuento(), 2)
        self.valor_a_pagar = (self.total_facturado - self.retenciones - self.descuento_pronto_pago)

        if self.pagado: self.mensaje_resultado = "Pagado"
        elif self.valor_a_pagar <= 0: self.mensaje_resultado = "Saldado"
        else: self.mensaje_resultado = "Pendiente"
        
        super(Factura, self).save(*args, **kwargs)

    def __str__(self):
        return f"Factura {self.numero_factura}"

# --------------------------------------------------------
# 7. SISTEMA DE ALERTAS Y NOTIFICACIONES
# --------------------------------------------------------
class Notificacion(models.Model):
    """
    Sistema de alertas basado en el TDR.
    """
    TIPO_ALERTA_CHOICES = [
        ('VENCIMIENTO_POLIZA', 'Vencimiento de Póliza'),
        ('PAGO_PENDIENTE', 'Pago por Realizar'),
        ('SINIESTRO_DEMORA_DOC', 'Retraso Documentación Siniestro'),
        ('SINIESTRO_RESPUESTA_ASEG', 'Retraso Respuesta Aseguradora'),
        ('OTRO', 'Otro'),
    ]
    
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Lectura'),
        ('LEIDA', 'Leída'),
        ('ENVIADA_CORREO', 'Enviada por Correo'),
    ]

    # Relación con tu modelo de Usuario
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones')
    mensaje = models.TextField()
    
    tipo_alerta = models.CharField(max_length=50, choices=TIPO_ALERTA_CHOICES)
    fecha_emision = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='PENDIENTE')
    
    enviado_por_correo = models.BooleanField(default=False)
    
    # Para guardar el ID de la Póliza (ej: "15") o Siniestro relacionado
    id_referencia = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Alerta {self.id} - {self.tipo_alerta} para {self.usuario.username}"

# ========================================================
# 8. DOCUMENTOS DE SINIESTROS
# ========================================================

def ruta_documento_siniestro(instance, filename):
    return f'siniestros/ID_{instance.siniestro.id}/{filename}'

class DocumentoSiniestro(models.Model):
    TIPO_DOCUMENTO = [
        ('INFORME', 'Informe Técnico'),
        ('DENUNCIA', 'Denuncia'),
        ('FOTOS', 'Fotografías'),
        ('FACTURA_REPARACION', 'Facturas Reparación'),
        ('OTRO', 'Otros'),
    ]

    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name='documentos')
    archivo = models.FileField(upload_to=ruta_documento_siniestro)
    tipo = models.CharField(max_length=20, choices=TIPO_DOCUMENTO)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    subido_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)

@receiver(post_delete, sender=DocumentoSiniestro)
def eliminar_archivo_de_minio(sender, instance, **kwargs):
    if instance.archivo:
        instance.archivo.delete(save=False)

@receiver(post_delete, sender=DocumentoPoliza)
def eliminar_archivo_poliza(sender, instance, **kwargs):
    if instance.archivo:
        instance.archivo.delete(save=False)