from django.contrib import admin
from .models import (
    Usuario, Poliza, Siniestro, Factura, DocumentoSiniestro,
    ResponsableCustodio, Aseguradora, Broker, Finiquito, Notificacion, DocumentoPoliza
)

# ... otros imports
from .models import Bien # Asegúrate de importar Bien

@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'detalle', 'custodio', 'marca', 'modelo', 'estado_operativo')
    list_filter = ('estado_fisico', 'estado_operativo', 'marca')
    search_fields = ('codigo', 'detalle', 'custodio__nombre_completo')
    raw_id_fields = ('custodio',) # Útil si tienes miles de custodios

    
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'rol', 'cedula', 'estado')
    list_filter = ('rol', 'estado')

@admin.register(Aseguradora)
class AseguradoraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'contacto', 'telefono')

@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo')

@admin.register(ResponsableCustodio)
class CustodioAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'identificacion', 'departamento')
    search_fields = ('nombre_completo', 'identificacion')

@admin.register(Poliza)
class PolizaAdmin(admin.ModelAdmin):
    # CORREGIDO: Eliminamos 'tipo_poliza'
    list_display = ('numero_poliza', 'aseguradora', 'ramo', 'vigencia_fin', 'estado')
    list_filter = ('estado', 'aseguradora', 'ramo')
    search_fields = ('numero_poliza', 'aseguradora__nombre')

@admin.register(Siniestro)
class SiniestroAdmin(admin.ModelAdmin):
    list_display = ('numero_reclamo', 'poliza', 'custodio', 'fecha_siniestro', 'estado_tramite')
    list_filter = ('estado_tramite', 'tipo_siniestro')
    search_fields = ('poliza__numero_poliza', 'custodio__nombre_completo')

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_factura', 'poliza', 'fecha_emision', 'total_facturado', 'pagado')
    list_filter = ('pagado',)

@admin.register(Finiquito)
class FiniquitoAdmin(admin.ModelAdmin):
    list_display = ('id_finiquito', 'siniestro', 'valor_final_pago', 'fecha_finiquito')

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo_alerta', 'estado', 'fecha_emision')
    list_filter = ('estado', 'tipo_alerta')

admin.site.register(DocumentoSiniestro)
admin.site.register(DocumentoPoliza)