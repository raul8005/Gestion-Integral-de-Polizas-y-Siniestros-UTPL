from django import forms

from .models import (Aseguradora, Bien, Broker, Factura, Finiquito, Poliza,
                     ResponsableCustodio, Siniestro)


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "id": "usernameInput"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "id": "passwordInput"}
        )
    )


class PolizaForm(forms.ModelForm):
    class Meta:
        model = Poliza
        fields = "__all__"

        exclude = ["fecha_registro", "usuario_gestor"]

        widgets = {
            "numero_poliza": forms.TextInput(attrs={"class": "form-control"}),
            # Nuevos selectores para las Relaciones
            "aseguradora": forms.Select(attrs={"class": "form-select"}),
            "broker": forms.Select(attrs={"class": "form-select"}),
            "vigencia_inicio": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "vigencia_fin": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "monto_asegurado": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            # Campos de texto para Ramo/Objeto (Reemplazan a tipo_poliza)
            "ramo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej. Ramos Generales"}
            ),
            "objeto_asegurado": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej. Vehículos"}
            ),
            "prima_base": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            # CAMPO MANUAL
            "prima_total": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "fecha_emision": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "estado": forms.CheckboxInput(
                attrs={"class": "form-check-input", "role": "switch"}
            ),
            "renovable": forms.CheckboxInput(
                attrs={"class": "form-check-input", "role": "switch"}
            ),
        }
        labels = {
            "estado": "¿Póliza Activa?",
            "renovable": "¿Es Renovable?",
            "ramo": "Grupo / Ramo",
            "objeto_asegurado": "Subgrupo / Objeto",
            "prima_total": "Prima Total (Incl. Impuestos)",
        }

    def clean_estado(self):
        # Convertir checkbox a booleano explícito si es necesario
        return self.cleaned_data.get("estado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.estado:
            self.initial["estado"] = True


# SINIESTRO FORM


# Modifica la clase SiniestroForm para incluir los campos técnicos
class SiniestroForm(forms.ModelForm):
    # Campos auxiliares para mostrar info del Bien (no se guardan en BD)
    bien_ajax = forms.CharField(
        label="Buscar Bien (Código)",
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_bien_ajax"}),
    )

    nombre_bien = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"}),
    )
    marca = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        label="Marca",
    )

    modelo = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        label="Modelo",
    )

    serie = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        label="Serie / Chasis",
    )

    # Campo de búsqueda AJAX para el bien
    bien_ajax = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Buscar bien por código..."}
        ),
        label="Buscar Bien",
    )

    custodio = forms.ModelChoiceField(
        queryset=ResponsableCustodio.objects.all().order_by("nombre_completo"),
        widget=forms.Select(attrs={"class": "form-select select2-enable"}),
        label="Responsable / Custodio",
        empty_label="-- Seleccione un Funcionario --",
    )

    def clean(self):
        print("=== INICIANDO VALIDACIÓN DEL FORMULARIO SINIESTRO ===")
        cleaned_data = super().clean()
        print(f"Cleaned data inicial: {cleaned_data}")

        custodio = cleaned_data.get("custodio")
        bien = cleaned_data.get("bien")

        print(f"Custodio seleccionado: {custodio}")
        print(f"Bien seleccionado: {bien}")

        if custodio and bien:
            print(f"Verificando si el bien {bien} pertenece al custodio {custodio}")
            print(f"Bien.custodio: {bien.custodio}")
            print(f"Custodio: {custodio}")
            print(f"¿Son iguales?: {bien.custodio == custodio}")

            # Validar que el bien pertenezca realmente a ese custodio
            if bien.custodio != custodio:
                error_msg = f"Error de Integridad: El bien '{bien.detalle}' no está registrado a nombre del custodio {custodio.nombre_completo}."
                print(f"❌ ERROR DE VALIDACIÓN: {error_msg}")
                raise forms.ValidationError(error_msg)
            else:
                print("✅ Validación de integridad OK")
            # Validar que el bien esté activo
            if bien.estado_operativo == "INACTIVO":
                error_msg = f"El bien '{bien.detalle}' está inactivo y no se le puede registrar un siniestro."
                print(f"❌ ERROR DE VALIDACIÓN: {error_msg}")
                raise forms.ValidationError(error_msg)
        else:
            print("⚠️ Faltan custodio o bien para validar integridad")

        print("=== VALIDACIÓN DEL FORMULARIO COMPLETADA ===")
        return cleaned_data

    class Meta:
        model = Siniestro
        fields = "__all__"
        exclude = [
            "usuario_gestor",
            "fecha_notificacion",
            "estado_tramite",
            "valor_reclamo",
            "deducible_aplicado",
            "depreciacion",
            "valor_a_pagar",
            "valor_reclamo_estimado",
        ]
        widgets = {
            "fecha_siniestro": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "tipo_siniestro": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej. Choque, Robo, Incendio",
                }
            ),
            "ubicacion_bien": forms.TextInput(attrs={"class": "form-control"}),
            "causa_siniestro": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "nombre_bien": forms.TextInput(attrs={"class": "form-control"}),
            "poliza": forms.Select(attrs={"class": "form-select"}),
            "bien": forms.Select(attrs={"class": "form-select"}),
            "codigo_activo": forms.TextInput(attrs={"class": "form-control"}),
        }


class SiniestroPorPolizaForm(forms.ModelForm):
    # Campos virtuales para mostrar info del bien (No se guardan, solo lectura)
    nombre_bien = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "readonly": "readonly",
                "class": "form-control",
                "id": "id_nombre_bien",
            }
        ),
    )
    marca = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"readonly": "readonly", "class": "form-control", "id": "id_marca"}
        ),
    )
    modelo = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"readonly": "readonly", "class": "form-control", "id": "id_modelo"}
        ),
    )
    serie = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"readonly": "readonly", "class": "form-control", "id": "id_serie"}
        ),
    )

    # Campo para el buscador Select2
    bien_ajax = forms.CharField(
        label="Buscar Bien (Código)",
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_bien_ajax"}),
    )

    class Meta:
        model = Siniestro
        fields = [
            "custodio",
            "bien",
            "fecha_siniestro",
            "tipo_siniestro",
            "ubicacion_bien",
            "causa_siniestro",
        ]
        widgets = {
            "custodio": forms.Select(
                attrs={"id": "id_custodio", "class": "form-select"}
            ),
            "bien": forms.HiddenInput(
                attrs={"id": "id_bien"}
            ),  # El ID real que Django guardará
            "fecha_siniestro": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "causa_siniestro": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }


class SiniestroEditForm(forms.ModelForm):
    # Campos de solo lectura para información del bien
    marca = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        label="Marca",
    )
    modelo = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        label="Modelo",
    )
    serie = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "readonly": True}),
        label="Serie / Chasis",
    )

    # El buscador AJAX
    bien_ajax = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Buscar bien por código..."}
        ),
        label="Buscar Bien",
    )

    # Campo opcional para valor estimado
    valor_reclamo_estimado = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        label="Valor Reclamo Estimado",
    )

    # 1. Aseguramos que el campo custodio cargue la lista desde la BD
    custodio = forms.ModelChoiceField(
        queryset=ResponsableCustodio.objects.all().order_by("nombre_completo"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Responsable / Custodio",
        empty_label="-- Seleccione un Funcionario --",
    )

    def clean(self):
        print("=== INICIANDO VALIDACIÓN DEL FORMULARIO DE EDICIÓN SINIESTRO ===")
        cleaned_data = super().clean()
        print(f"Cleaned data inicial: {cleaned_data}")

        custodio = cleaned_data.get("custodio")
        bien = cleaned_data.get("bien")

        print(f"Custodio seleccionado: {custodio}")
        print(f"Bien seleccionado: {bien}")

        if custodio and bien:
            print(f"Verificando si el bien {bien} pertenece al custodio {custodio}")
            print(f"Bien.custodio: {bien.custodio}")
            print(f"Custodio: {custodio}")
            print(f"¿Son iguales?: {bien.custodio == custodio}")

            # Validar que el bien pertenezca realmente a ese custodio
            if bien.custodio != custodio:
                error_msg = f"Error de Integridad: El bien '{bien.detalle}' no está registrado a nombre del custodio {custodio.nombre_completo}."
                print(f"❌ ERROR DE VALIDACIÓN: {error_msg}")
                raise forms.ValidationError(error_msg)
            else:
                print("✅ Validación de integridad OK")
            # Validar que el bien esté activo
            if bien.estado_operativo == "INACTIVO":
                error_msg = f"El bien '{bien.detalle}' está inactivo y no se le puede registrar un siniestro."
                print(f"❌ ERROR DE VALIDACIÓN: {error_msg}")
                raise forms.ValidationError(error_msg)
        else:
            print("⚠️ Faltan custodio o bien para validar integridad")

        print("=== VALIDACIÓN DEL FORMULARIO DE EDICIÓN COMPLETADA ===")
        return cleaned_data

    class Meta(SiniestroForm.Meta):
        model = Siniestro

        # 2. Excluimos 'poliza' porque NO se debe cambiar a qué póliza pertenece el siniestro una vez creado.
        # También excluimos campos automáticos de auditoría.
        exclude = ["poliza", "usuario_gestor", "fecha_notificacion"]

        # 3. Definimos los widgets para que se vean bien con Bootstrap
        widgets = {
            "fecha_siniestro": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "tipo_siniestro": forms.TextInput(attrs={"class": "form-control"}),
            "ubicacion_bien": forms.TextInput(attrs={"class": "form-control"}),
            "causa_siniestro": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "nombre_bien": forms.TextInput(attrs={"class": "form-control"}),
            "bien": forms.Select(attrs={"class": "form-select"}),
            # Campos adicionales que SÍ se pueden editar en esta etapa
            "estado_tramite": forms.Select(attrs={"class": "form-select"}),
            "cobertura_aplicada": forms.TextInput(attrs={"class": "form-control"}),
            "valor_reclamo": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "deducible_aplicado": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "depreciacion": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "valor_a_pagar": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "valor_reclamo_estimado": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
        }


# Factura form
class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = [
            "poliza",
            "numero_factura",
            "documento_contable",
            "fecha_emision",
            "fecha_pago",
            "prima",
        ]

        widgets = {
            "fecha_emision": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "fecha_pago": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "poliza": forms.Select(attrs={"class": "form-select"}),
            "numero_factura": forms.TextInput(attrs={"class": "form-control"}),
            "documento_contable": forms.TextInput(attrs={"class": "form-control"}),
            "prima": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }
        labels = {
            "prima": "Valor de la Prima (Base)",
            "poliza": "Seleccionar Póliza Asociada",
        }


# Formulario para documentos de siniestro
from .models import DocumentoSiniestro


class DocumentoSiniestroForm(forms.ModelForm):
    class Meta:
        model = DocumentoSiniestro
        fields = ["tipo", "archivo", "descripcion"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "archivo": forms.FileInput(attrs={"class": "form-control"}),
            "descripcion": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Opcional"}
            ),
        }


class CustodioForm(forms.ModelForm):
    class Meta:
        model = ResponsableCustodio
        fields = ["nombre_completo", "identificacion", "correo", "departamento"]
        widgets = {
            "nombre_completo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre Apellido"}
            ),
            "identificacion": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Cédula/RUC"}
            ),
            "correo": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "email@utpl.edu.ec"}
            ),
            "departamento": forms.TextInput(attrs={"class": "form-control"}),
        }
        labels = {
            "identificacion": "Cédula o Identificación",
        }


class FiniquitoForm(forms.ModelForm):
    class Meta:
        model = Finiquito
        fields = [
            "id_finiquito",
            "fecha_finiquito",
            "valor_total_reclamo",
            "valor_deducible",
            "valor_depreciacion",
            "documento_firmado",
        ]
        widgets = {
            "fecha_finiquito": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "id_finiquito": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej. LIQ-2024-001"}
            ),
            "valor_total_reclamo": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "valor_deducible": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "valor_depreciacion": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "value": 0}
            ),
            "documento_firmado": forms.FileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "valor_total_reclamo": "Monto Bruto del Reclamo",
            "valor_deducible": "Deducible Aplicado (-)",
            "valor_depreciacion": "Depreciación (-)",
            "documento_firmado": "Acta de Finiquito Firmada (PDF)",
        }
