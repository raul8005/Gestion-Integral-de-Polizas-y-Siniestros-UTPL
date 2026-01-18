from django import forms
from .models import Poliza, Siniestro, Factura, ResponsableCustodio, Aseguradora, Broker, Finiquito

class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'usernameInput'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'id': 'passwordInput'})
    )

class PolizaForm(forms.ModelForm):
    class Meta:
        model = Poliza
        fields = '__all__'
        
        exclude = ['fecha_registro', 'usuario_gestor'] 
        
        widgets = {
            'numero_poliza': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Nuevos selectores para las Relaciones
            'aseguradora': forms.Select(attrs={'class': 'form-select'}),
            'broker': forms.Select(attrs={'class': 'form-select'}),
            
            'vigencia_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'vigencia_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'monto_asegurado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            # Campos de texto para Ramo/Objeto (Reemplazan a tipo_poliza)
            'ramo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Ramos Generales'}),
            'objeto_asegurado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Vehículos'}),
            
            'prima_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            # CAMPO MANUAL
            'prima_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            'fecha_emision': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'renovable': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }
        labels = {
            'estado': '¿Póliza Activa?',
            'renovable': '¿Es Renovable?',
            'ramo': 'Grupo / Ramo',
            'objeto_asegurado': 'Subgrupo / Objeto',
            'prima_total': 'Prima Total (Incl. Impuestos)'
        }

    def clean_estado(self):
        # Convertir checkbox a booleano explícito si es necesario
        return self.cleaned_data.get('estado')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.estado:
            self.initial['estado'] = True

# SINIESTRO FORM


class SiniestroForm(forms.ModelForm):
    custodio = forms.ModelChoiceField(
        queryset=ResponsableCustodio.objects.all().order_by('nombre_completo'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Responsable / Custodio",
        empty_label="-- Seleccione un Funcionario --"
    )

    class Meta:
        model = Siniestro
        fields = '__all__'
        exclude = [
            'usuario_gestor', 'fecha_notificacion', 'estado_tramite',
            'valor_reclamo', 'deducible_aplicado', 'depreciacion', 
            'valor_a_pagar', 'valor_reclamo_estimado'
        ]
        widgets = {
            'fecha_siniestro': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tipo_siniestro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Choque, Robo, Incendio'}),
            'ubicacion_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'causa_siniestro': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'nombre_bien': forms.TextInput(attrs={'class': 'form-control'}),
            # Ocultamos la póliza si ya viene preseleccionada en la vista, o la dejamos select si es general
            'poliza': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # USA ESTA LÓGICA CON CONDICIONALES:
        if 'poliza' in self.fields:
            self.fields['poliza'].queryset = Poliza.objects.filter(estado=True)
            
        if 'custodio' in self.fields:
            self.fields['custodio'].queryset = ResponsableCustodio.objects.all().order_by('nombre_completo')
            self.fields['custodio'].label = "Responsable / Custodio del Bien"
            self.fields['custodio'].empty_label = "Seleccione un Funcionario..."

class SiniestroPorPolizaForm(forms.ModelForm):
    class Meta:
        model = Siniestro
        exclude = [
            'poliza',
            'usuario_gestor',
            'fecha_notificacion',
            'estado_tramite',
            'valor_reclamo',
            'deducible_aplicado',
            'depreciacion',
            'valor_a_pagar',
        ]

        widgets = {
            'fecha_siniestro': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tipo_siniestro': forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'causa_siniestro': forms.Textarea(attrs={'class': 'form-control'}),
            'nombre_bien': forms.TextInput(attrs={'class': 'form-control'}),
        }


class SiniestroEditForm(SiniestroForm):
    # 1. Aseguramos que el campo custodio cargue la lista desde la BD
    custodio = forms.ModelChoiceField(
        queryset=ResponsableCustodio.objects.all().order_by('nombre_completo'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Responsable / Custodio",
        empty_label="-- Seleccione un Funcionario --"
    )

    class Meta(SiniestroForm.Meta):
        model = Siniestro
        
        # 2. Excluimos 'poliza' porque NO se debe cambiar a qué póliza pertenece el siniestro una vez creado.
        # También excluimos campos automáticos de auditoría.
        exclude = [
            'poliza', 
            'usuario_gestor', 
            'fecha_notificacion'
        ]

        # 3. Definimos los widgets para que se vean bien con Bootstrap
        widgets = {
            'fecha_siniestro': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tipo_siniestro': forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'causa_siniestro': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'nombre_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'bien': forms.Select(attrs={'class': 'form-select'}), 

            # Campos adicionales que SÍ se pueden editar en esta etapa
            'estado_tramite': forms.Select(attrs={'class': 'form-select'}),
            'cobertura_aplicada': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_reclamo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'deducible_aplicado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'depreciacion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_a_pagar': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_reclamo_estimado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            # Campos técnicos del bien
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'serie': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_activo': forms.TextInput(attrs={'class': 'form-control'}),

            
        }


# Factura form
class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = ['poliza', 'numero_factura', 'documento_contable', 'fecha_emision', 'fecha_pago', 'prima']
        
        widgets = {
            'fecha_emision': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_pago': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'poliza': forms.Select(attrs={'class': 'form-select'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control'}),
            'documento_contable': forms.TextInput(attrs={'class': 'form-control'}),
            'prima': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'prima': 'Valor de la Prima (Base)',
            'poliza': 'Seleccionar Póliza Asociada'
        }


# Formulario para documentos de siniestro
from .models import DocumentoSiniestro

class DocumentoSiniestroForm(forms.ModelForm):
    class Meta:
        model = DocumentoSiniestro
        fields = ['tipo', 'archivo', 'descripcion']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
        }

class CustodioForm(forms.ModelForm):
    class Meta:
        model = ResponsableCustodio
        fields = ['nombre_completo', 'identificacion', 'correo', 'departamento']
        widgets = {
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre Apellido'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cédula/RUC'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@utpl.edu.ec'}),
            'departamento': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'identificacion': 'Cédula o Identificación',
        }

class FiniquitoForm(forms.ModelForm):
    class Meta:
        model = Finiquito
        fields = [
            'id_finiquito', 
            'fecha_finiquito', 
            'valor_total_reclamo', 
            'valor_deducible', 
            'valor_depreciacion', 
            'documento_firmado'
        ]
        widgets = {
            'fecha_finiquito': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'id_finiquito': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. LIQ-2024-001'}),
            'valor_total_reclamo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_deducible': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_depreciacion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': 0}),
            'documento_firmado': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'valor_total_reclamo': 'Monto Bruto del Reclamo',
            'valor_deducible': 'Deducible Aplicado (-)',
            'valor_depreciacion': 'Depreciación (-)',
            'documento_firmado': 'Acta de Finiquito Firmada (PDF)'
        }