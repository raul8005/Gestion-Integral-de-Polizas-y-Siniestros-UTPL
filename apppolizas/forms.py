from django import forms
from .models import Poliza, Siniestro, Factura

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
        exclude = ['fecha_registro', 'usuario_gestor'] # Campos automáticos que no se piden al usuario
        
        widgets = {
            'vigencia_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'vigencia_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_emision': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'numero_poliza': forms.TextInput(attrs={'class': 'form-control'}),
            'monto_asegurado': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo_poliza': forms.TextInput(attrs={'class': 'form-control'}),
            'prima_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prima_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'renovable': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
        }
        labels = {
            'estado': '¿Póliza Activa?',
            'renovable': '¿Es Renovable?'
        }

    def clean_estado(self):
        estado_bool = self.cleaned_data.get('estado')
        if estado_bool: # Si es True (marcado)
            return "Activa"
        else: # Si es False (desmarcado)
            # OJO: Si el campo viene vacío del HTML (checkbox sin marcar), Django a veces lo toma como False
            return "Inactiva"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.estado == 'Activa':
            self.initial['estado'] = True


# SINIESTRO FORM


class SiniestroForm(forms.ModelForm):
    class Meta:
        model = Siniestro
        exclude = [
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
            'poliza': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['poliza'].queryset = Poliza.objects.filter(estado='Activa')



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


class SiniestroEditForm(forms.ModelForm):
    class Meta:
        model = Siniestro
        exclude = [
            'poliza',
            'usuario_gestor',
            'fecha_notificacion',
        ]

        widgets = {
            'fecha_siniestro': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'tipo_siniestro': forms.TextInput(attrs={'class': 'form-control'}),
            'ubicacion_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'causa_siniestro': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'nombre_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'serie': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_activo': forms.TextInput(attrs={'class': 'form-control'}),
            'responsable_custodio': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_tramite': forms.Select(attrs={'class': 'form-select'}),
            'cobertura_aplicada': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_reclamo': forms.NumberInput(attrs={'class': 'form-control'}),
            'deducible_aplicado': forms.NumberInput(attrs={'class': 'form-control'}),
            'depreciacion': forms.NumberInput(attrs={'class': 'form-control'}),
            'valor_a_pagar': forms.NumberInput(attrs={'class': 'form-control'}),
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