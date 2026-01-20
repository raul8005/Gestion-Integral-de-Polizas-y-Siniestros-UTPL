import json
from datetime import date

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, TemplateView, View
from xhtml2pdf import pisa

from apppolizas.models import (Bien, DocumentoSiniestro, Factura, Poliza,
                               ResponsableCustodio, Siniestro)

from .forms import (CustodioForm, DocumentoSiniestroForm, FacturaForm,
                    FiniquitoForm, PolizaForm, SiniestroEditForm,
                    SiniestroForm, SiniestroPorPolizaForm)
from .repositories import (FiniquitoRepository, SiniestroRepository,
                           UsuarioRepository)
from .services import (AuthService, BienService, CustodioService,
                       DocumentoService, FacturaService, FiniquitoService,
                       NotificacionService, PolizaService, SiniestroService)


# =====================================================
# LOGOUT
# =====================================================
@csrf_exempt
def logout_view(request):
    logout(request)
    return JsonResponse({"success": True})


# =====================================================
# LOGIN
# =====================================================
class LoginView(View):
    template_name = "login.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        try:
            username = request.POST.get("username")
            password = request.POST.get("password")

            if not username or not password:
                return JsonResponse(
                    {"success": False, "error": "Usuario y contraseña requeridos"},
                    status=400,
                )

            user, rol = AuthService.login_universal(username, password)
            login(request, user)

            redirect_url = (
                "/administrador/dashboard/"
                if rol == "admin"
                else "/dashboard-analista/"
            )

            return JsonResponse({"success": True, "redirect_url": redirect_url})

        except ValidationError as e:
            return JsonResponse({"success": False, "error": str(e)}, status=401)

        except Exception as e:
            print("ERROR LOGIN:", e)
            return JsonResponse(
                {"success": False, "error": "Error interno del servidor"}, status=500
            )


# =====================================================
# DASHBOARD ADMIN
# =====================================================
class DashboardAdminView(LoginRequiredMixin, TemplateView):
    template_name = "administrador/dashboard_admin.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "admin":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_usuarios"] = UsuarioRepository.get_all_usuarios().count()
        context["total_polizas"] = PolizaService.listar_polizas().count()
        return context


class AdminUsuariosView(LoginRequiredMixin, TemplateView):
    template_name = "administrador/usuarios.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "admin":
            return redirect("usuarios")
        return super().dispatch(request, *args, **kwargs)


# =====================================================
# DASHBOARD ANALISTA
# =====================================================
class DashboardAnalistaView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard_analista.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_admin")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_activas"] = PolizaService.contar_polizas_activas()
        context["total_vencidas"] = PolizaService.contar_polizas_vencidas()
        context["total_siniestros"] = SiniestroService.listar_todos().count()
        context["total_facturas"] = FacturaService.listar_facturas().count()
        context["ultimos_siniestros"] = SiniestroService.listar_todos().order_by(
            "-fecha_siniestro"
        )[:5]
        return context


# =====================================================
# API USUARIOS (SOLO ADMIN)
# =====================================================
@method_decorator(csrf_exempt, name="dispatch")
class UsuarioCRUDView(LoginRequiredMixin, View):

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "admin":
            return JsonResponse(
                {"error": "No tienes permisos de administrador"}, status=403
            )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, usuario_id=None):
        if usuario_id:
            usuario = UsuarioRepository.get_by_id(usuario_id)
            if not usuario:
                return JsonResponse({"error": "Usuario no encontrado"}, status=404)

            data = {
                "id": usuario.id,
                "username": usuario.username,
                "email": usuario.email,
                "rol": usuario.rol,
                "cedula": usuario.cedula,
                "estado": usuario.estado,
            }
            return JsonResponse(data)

        usuarios = UsuarioRepository.get_all_usuarios()
        data = list(
            usuarios.values("id", "username", "email", "rol", "cedula", "estado")
        )
        return JsonResponse(data, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
            user = UsuarioRepository.create_usuario(data)
            return JsonResponse(
                {"success": True, "message": "Usuario creado", "id": user.id},
                status=201,
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    def put(self, request, usuario_id):
        try:
            data = json.loads(request.body)
            usuario = UsuarioRepository.update_usuario(usuario_id, data)
            return JsonResponse(
                {"success": True, "message": f"Usuario {usuario.username} actualizado"}
            )
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)

    def delete(self, request, usuario_id):
        try:
            UsuarioRepository.delete_usuario(usuario_id)
            return JsonResponse({"success": True, "message": "Usuario eliminado"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)


# =====================================================
# PÓLIZAS (SOLO ANALISTA)
# =====================================================
class PolizaListView(LoginRequiredMixin, View):
    template_name = "polizas.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        polizas = PolizaService.listar_polizas()
        form = PolizaForm()
        return render(request, self.template_name, {"polizas": polizas, "form": form})

    def post(self, request):
        form = PolizaForm(request.POST)
        if form.is_valid():
            try:
                # 1. Obtenemos los datos del formulario
                datos_poliza = form.cleaned_data

                # 2. ¡EL CAMBIO CLAVE! Inyectamos el usuario logueado
                datos_poliza["usuario_gestor"] = request.user

                # 3. Llamamos al servicio con los datos completos
                PolizaService.crear_poliza(datos_poliza)

                messages.success(request, "Póliza creada exitosamente")
                return redirect("polizas_list")
            except Exception as e:
                messages.error(request, str(e))

        polizas = PolizaService.listar_polizas()
        return render(request, self.template_name, {"polizas": polizas, "form": form})


class PolizaUpdateView(LoginRequiredMixin, View):
    template_name = "poliza_edit.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        poliza = PolizaService.obtener_poliza(pk)
        form = PolizaForm(instance=poliza)
        return render(request, self.template_name, {"form": form, "poliza": poliza})

    def post(self, request, pk):
        poliza = PolizaService.obtener_poliza(pk)
        form = PolizaForm(request.POST, instance=poliza)

        if form.is_valid():
            PolizaService.actualizar_poliza(pk, form.cleaned_data)
            messages.success(request, "Póliza actualizada")
            return redirect("polizas_list")

        messages.error(request, "Corrige los errores del formulario")
        return render(request, self.template_name, {"form": form, "poliza": poliza})


class PolizaDeleteView(LoginRequiredMixin, View):

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        PolizaService.eliminar_poliza(pk)
        messages.success(request, "Póliza eliminada")
        return redirect("polizas_list")


class PolizaDetailView(LoginRequiredMixin, DetailView):
    model = Poliza
    template_name = "poliza_detail.html"
    context_object_name = "poliza"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["siniestros"] = SiniestroService.listar_por_poliza(self.object.id)
        return context


# ------------------------------------------------------
# SINESTRO
# ------------------------------------------------------
class SiniestroListView(LoginRequiredMixin, View):
    template_name = "siniestros.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        siniestros = SiniestroService.listar_todos()
        query = request.GET.get("q")
        if query:
            siniestros = siniestros.filter(
                Q(custodio__nombre_completo__icontains=query)
                | Q(custodio__identificacion__icontains=query)
            )

        return render(
            request,
            self.template_name,
            {
                "siniestros": siniestros,
                "total_siniestros": siniestros.count(),
                "total_polizas": siniestros.values("poliza").distinct().count(),
                "form": SiniestroForm(),
            },
        )

    # views.py (SiniestroListView)
    def post(self, request, *args, **kwargs):
        print("=== INICIANDO CREACIÓN DE SINIESTRO ===")
        print(f"POST data recibido: {request.POST}")

        form = SiniestroForm(request.POST)
        print(f"Formulario creado: {form}")
        print(f"Formulario es válido?: {form.is_valid()}")

        if not form.is_valid():
            print(f"ERRORES DEL FORMULARIO: {form.errors}")
            print(f"ERRORES NO CAMPO: {form.non_field_errors()}")

        if form.is_valid():
            try:
                print("✅ Formulario válido - Intentando crear siniestro...")
                print(f"Datos limpios: {form.cleaned_data}")

                # Filtrar solo los campos que el modelo Siniestro espera
                datos_siniestro = {
                    "poliza": form.cleaned_data["poliza"],
                    "custodio": form.cleaned_data["custodio"],
                    "bien": form.cleaned_data["bien"],
                    "fecha_siniestro": form.cleaned_data["fecha_siniestro"],
                    "tipo_siniestro": form.cleaned_data["tipo_siniestro"],
                    "ubicacion_bien": form.cleaned_data["ubicacion_bien"],
                    "causa_siniestro": form.cleaned_data["causa_siniestro"],
                }

                print(f"Datos filtrados para Siniestro: {datos_siniestro}")

                # CORRECCIÓN: El nombre del parámetro debe ser poliza_id
                siniestro_creado = SiniestroService.crear_siniestro(
                    poliza=form.cleaned_data["poliza"],  # <--- Aquí estaba el error
                    data=datos_siniestro,  # <-- Pasar datos filtrados
                    usuario=request.user,
                )
                print(f"✅ Siniestro creado exitosamente: {siniestro_creado}")
                messages.success(request, "Siniestro creado")
                return redirect("siniestros")
            except ValidationError as e:
                print(f"❌ Error de validación al crear siniestro: {e}")
                messages.error(request, str(e))
            except Exception as e:
                print(f"❌ Error inesperado al crear siniestro: {e}")
                messages.error(request, f"Error inesperado: {str(e)}")
        else:
            # Si el formulario no es válido, enviamos un mensaje de alerta
            print("❌ Formulario inválido - Mostrando error al usuario")
            messages.error(
                request,
                "Error en el formulario. Verifique que el activo pertenezca al custodio.",
            )

        # IMPORTANTE: Volver a renderizar la página con el formulario que tiene los errores
        print("🔄 Renderizando página con formulario y errores...")
        siniestros = SiniestroService.listar_todos()
        return render(
            request,
            self.template_name,
            {
                "siniestros": siniestros,
                "total_siniestros": siniestros.count(),
                "total_polizas": siniestros.values("poliza").distinct().count(),
                "form": form,  # Este 'form' ahora contiene los mensajes de error
            },
        )


class SiniestroPorPolizaView(LoginRequiredMixin, View):
    template_name = "siniestros.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, poliza_id):
        poliza = PolizaService.obtener_poliza(poliza_id)
        siniestros = SiniestroService.listar_por_poliza(poliza_id)

        return render(
            request,
            self.template_name,
            {
                "poliza": poliza,
                "siniestros": siniestros,
                "form": SiniestroPorPolizaForm(),
            },
        )

    def post(self, request, poliza_id):
        poliza = PolizaService.obtener_poliza(poliza_id)
        form = SiniestroPorPolizaForm(request.POST)

        if form.is_valid():
            SiniestroService.crear_siniestro(
                poliza=poliza, data=form.cleaned_data, usuario=request.user
            )
            messages.success(request, "Siniestro registrado correctamente")
            return redirect("siniestros_por_poliza", poliza_id=poliza_id)

        siniestros = SiniestroService.listar_por_poliza(poliza_id)
        return render(
            request,
            self.template_name,
            {"poliza": poliza, "siniestros": siniestros, "form": form},
        )


class SiniestroDetailView(LoginRequiredMixin, DetailView):
    model = Siniestro
    template_name = "siniestro_detail.html"
    context_object_name = "siniestro"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- Lógica para la barra de progreso ---
        progress_map = {
            "REPORTADO": 25,
            "ENVIADO_ASEGURADORA": 60,
            "REPARACION": 80,
            "LIQUIDADO": 100,
        }
        siniestro = self.get_object()
        context["progress_percentage"] = progress_map.get(siniestro.estado_tramite, 0)
        context["estado_display"] = siniestro.get_estado_tramite_display()

        # --- Tu lógica actual ---
        context["siniestros_relacionados"] = SiniestroService.listar_por_poliza(
            self.object.poliza.id
        ).exclude(id=self.object.id)

        # --- Nueva lógica para Expediente Digital ---
        # 1. Agregamos el formulario para subir archivos (debes importarlo)
        context["form_documento"] = DocumentoSiniestroForm()

        # 2. Listamos los documentos guardados en MinIO para este siniestro
        context["documentos"] = DocumentoService.listar_evidencias(self.object.id)

        return context

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)


class SiniestroEditView(LoginRequiredMixin, View):
    template_name = "siniestro_edit.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        print("=== INICIANDO EDICIÓN DE SINIESTRO ===")
        print(f"Siniestro ID solicitado: {pk}")

        # Usamos el repositorio para obtener los datos
        siniestro = SiniestroRepository.get_by_id(pk)
        if not siniestro:
            print(f"❌ Siniestro {pk} no encontrado")
            return redirect("siniestros")

        print(f"✅ Siniestro encontrado: {siniestro}")
        print(f"  - Póliza: {siniestro.poliza.numero_poliza}")
        print(f"  - Custodio actual: {siniestro.custodio}")
        print(f"  - Bien actual: {siniestro.bien}")

        # Pre-poblamos campos que no están directamente en el modelo Siniestro
        initial_data = {}
        if siniestro.bien:
            initial_data = {
                "marca": siniestro.bien.marca,
                "modelo": siniestro.bien.modelo,
                "serie": siniestro.bien.serie,
                "bien_ajax": f"{siniestro.bien.codigo} - {siniestro.bien.detalle}",
            }
            print(f"📋 Datos iniciales preparados: {initial_data}")

        form = SiniestroEditForm(instance=siniestro, initial=initial_data)
        print(f"📝 Formulario de edición creado")
        return render(
            request, self.template_name, {"form": form, "siniestro": siniestro}
        )

    def post(self, request, pk):
        print("=== INICIANDO ACTUALIZACIÓN DE SINIESTRO ===")
        print(f"Siniestro ID solicitado: {pk}")
        print(f"POST data recibido: {request.POST}")

        siniestro_instancia = SiniestroRepository.get_by_id(pk)
        if not siniestro_instancia:
            print(f"❌ Siniestro {pk} no encontrado para actualizar")
            return redirect("siniestros")

        print(f"✅ Siniestro encontrado para actualizar: {siniestro_instancia}")

        # Pasamos request.FILES por si algún día permites subir archivos aquí
        form = SiniestroEditForm(
            request.POST, request.FILES, instance=siniestro_instancia
        )
        print(f"📝 Formulario de edición creado: {form}")
        print(f"📝 Formulario es válido?: {form.is_valid()}")

        if not form.is_valid():
            print(f"❌ ERRORES DEL FORMULARIO: {form.errors}")
            print(f"❌ ERRORES NO CAMPO: {form.non_field_errors()}")

        if form.is_valid():
            try:
                print("✅ Formulario válido - Intentando actualizar siniestro...")
                print(f"📋 Datos limpios: {form.cleaned_data}")

                # Validación específica para edición
                custodio = form.cleaned_data.get("custodio")
                bien = form.cleaned_data.get("bien")

                if custodio and bien:
                    print(
                        f"🔍 Verificando integridad - Custodio: {custodio}, Bien: {bien}"
                    )
                    print(f"🔍 Bien.custodio: {bien.custodio}")
                    print(f"🔍 ¿Son iguales?: {bien.custodio == custodio}")

                    if bien.custodio != custodio:
                        error_msg = f"Error de Integridad: El bien '{bien.detalle}' no está registrado a nombre del custodio {custodio.nombre_completo}."
                        print(f"❌ ERROR DE VALIDACIÓN: {error_msg}")
                        messages.error(request, error_msg)
                        return render(
                            request,
                            self.template_name,
                            {"form": form, "siniestro": siniestro_instancia},
                        )
                    else:
                        print("✅ Validación de integridad OK")

                # Si usas ModelForm, a veces basta con form.save(),
                # pero respetamos tu servicio:
                print("🔄 Llamando al servicio de actualización...")
                siniestro_actualizado = SiniestroService.actualizar_siniestro(
                    pk, form.cleaned_data
                )
                print(f"✅ Siniestro actualizado exitosamente: {siniestro_actualizado}")

                messages.success(request, "Siniestro actualizado correctamente")

                # REDIRECCIÓN: Aquí es donde te enviamos al detalle tras guardar
                return redirect("siniestro_detail", pk=pk)

            except ValidationError as e:
                print(f"❌ Error de validación al actualizar siniestro: {e}")
                messages.error(request, str(e))
            except Exception as e:
                print(f"❌ Error inesperado al actualizar siniestro: {e}")
                messages.error(request, f"Error inesperado: {str(e)}")
        else:
            # === AQUÍ ESTABA EL PROBLEMA ===
            # Antes solo hacías print(form.errors). Ahora enviamos el mensaje al usuario.
            print("❌ Formulario inválido - Mostrando error al usuario")
            messages.error(
                request,
                "No se pudo guardar. Verifique que el Bien pertenezca al Custodio seleccionado.",
            )

        print("🔄 Renderizando página de edición con formulario y errores...")
        return render(
            request,
            self.template_name,
            {"form": form, "siniestro": siniestro_instancia},
        )


class SiniestroDeleteView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        siniestro = Siniestro.objects.get(pk=pk)
        siniestro.delete()
        messages.success(request, "Siniestro eliminado correctamente")
        return redirect("siniestros")


# ------------------------------------------------------
# Factura
# ------------------------------------------------------


# 1. Listar Facturas
def lista_facturas(request):
    """
    Muestra el historial usando el Servicio (Capa de Negocio).
    """
    # YA NO USAMOS: Factura.objects.all()
    # USAMOS EL SERVICIO:
    facturas = FacturaService.listar_facturas()
    return render(request, "lista_facturas.html", {"facturas": facturas})


# 2. Registrar Nueva Factura
def crear_factura(request):
    """
    Crea la factura enviando los datos limpios al Servicio.
    """
    if request.method == "POST":
        form = FacturaForm(request.POST)
        if form.is_valid():
            try:
                # YA NO USAMOS: form.save()
                # USAMOS EL SERVICIO pasando los datos limpios (diccionario):
                FacturaService.crear_factura(form.cleaned_data)

                messages.success(
                    request, "Factura registrada y calculada correctamente."
                )
                return redirect("lista_facturas")
            except ValidationError as e:
                messages.error(request, f"Error de validación: {e}")
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
        else:
            messages.error(request, "Error en el formulario. Verifica los datos.")
    else:
        form = FacturaForm()

    return render(request, "form_factura.html", {"form": form})


# 3. Generar PDF de Factura
def generar_pdf_factura(request, factura_id):
    # Usamos el servicio para obtener la factura (incluye validación de existencia)
    try:
        factura = FacturaService.obtener_factura(factura_id)
    except ValidationError:
        return HttpResponse("La factura no existe", status=404)

    template_path = "factura_pdf.html"
    context = {"factura": factura}

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="factura_{factura.numero_factura}.pdf"'
    )

    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse(f"Error al generar PDF: <pre>{html}</pre>")

    return response


# Vistas para gestión de documentos de siniestro
class SubirEvidenciaView(LoginRequiredMixin, View):

    def post(self, request, siniestro_id):
        form = DocumentoSiniestroForm(
            request.POST, request.FILES
        )  # ¡Importante request.FILES!

        if form.is_valid():
            try:
                DocumentoService.subir_evidencia(
                    siniestro_id=siniestro_id,
                    data_form=form.cleaned_data,
                    archivo=request.FILES["archivo"],
                    usuario=request.user,
                )
                messages.success(request, "Documento subido correctamente a MinIO.")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, "Error al subir el archivo.")
        else:
            messages.error(request, "Error en el formulario.")

        # Redirigir de vuelta al detalle del siniestro
        return redirect("siniestro_detail", pk=siniestro_id)


class SiniestroDeleteEvidenciaView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        # Buscamos el documento o damos error 404 si no existe
        documento = get_object_or_404(DocumentoSiniestro, pk=pk)

        # Guardamos el ID del siniestro para volver ahí después de borrar
        siniestro_id = documento.siniestro.id

        # Eliminamos el registro (y el archivo si está configurado en signals)
        documento.delete()

        messages.success(request, "Documento eliminado correctamente del expediente.")
        return redirect("siniestro_detail", pk=siniestro_id)


# 1. LISTADO DE CUSTODIOS (Pantalla Principal)
class CustodioListView(LoginRequiredMixin, View):
    template_name = "custodios.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Solo obtenemos la lista para pintarla en el template
        custodios = CustodioService.listar_custodios()
        return render(request, self.template_name, {"custodios": custodios})


# 2. DETALLE DE CUSTODIO (API JSON para el Modal)
class CustodioDetailApiView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            custodio = CustodioService.obtener_custodio(pk)
            data = {
                "nombre": custodio.nombre_completo,
                "identificacion": custodio.identificacion,
                "correo": custodio.correo,
                "departamento": custodio.departamento,
                "ciudad": custodio.ciudad if custodio.ciudad else "N/A",
                "edificio": custodio.edificio if custodio.edificio else "N/A",
                "puesto": custodio.puesto if custodio.puesto else "N/A",
            }
            return JsonResponse({"success": True, "data": data})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=404)


# 3. LISTADO DE BIENES DE UN CUSTODIO (Nueva Pantalla)
class BienesPorCustodioView(LoginRequiredMixin, View):
    template_name = "bienes_custodio.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != "analista":
            return redirect("dashboard_analista")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, custodio_id):
        try:
            custodio = CustodioService.obtener_custodio(custodio_id)
            bienes = BienService.listar_por_custodio(custodio_id)

            return render(
                request, self.template_name, {"custodio": custodio, "bienes": bienes}
            )
        except ValidationError:
            messages.error(request, "Custodio no encontrado")
            return redirect("custodios_list")


# 4. DETALLE DE BIEN (API JSON para el Modal)
class BienDetailApiView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            bien = BienService.obtener_detalle_bien(pk)
            data = {
                "codigo": bien.codigo,
                "detalle": bien.detalle,
                "marca": bien.marca if bien.marca else "N/A",
                "modelo": bien.modelo if bien.modelo else "N/A",
                "serie": bien.serie if bien.serie else "N/A",
                "estado_fisico": bien.get_estado_fisico_display(),  # Obtiene el texto (Bueno/Regular/Malo)
                "baan_v": bien.baan_v if bien.baan_v else "N/A",
            }
            return JsonResponse({"success": True, "data": data})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=404)


class FiniquitoCreateView(LoginRequiredMixin, View):
    template_name = "finiquito_create.html"

    def get(self, request, siniestro_id):
        print(
            f"--- DEBUG: Entrando al GET de FiniquitoCreateView para Siniestro {siniestro_id} ---"
        )
        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        print(f"--- DEBUG: Resultado de búsqueda siniestro: {siniestro} ---")

        # SEGURIDAD 1: Verificar que el siniestro existe
        if not siniestro:
            print(f"--- DEBUG: Siniestro {siniestro_id} no existe ---")
            messages.error(request, "El siniestro no existe.")
            return redirect("siniestros")

        # SEGURIDAD 2: Verificar estado o existencia de finiquito
        ya_tiene_finiquito = FiniquitoRepository.get_by_siniestro(siniestro_id)
        print(f"--- DEBUG: ¿Ya tiene finiquito? {ya_tiene_finiquito} ---")

        if siniestro.estado_tramite == "LIQUIDADO" or ya_tiene_finiquito:
            print(
                f"--- DEBUG: Siniestro {siniestro_id} ya liquidado o con finiquito existente ---"
            )
            messages.warning(
                request,
                "Este siniestro ya ha sido liquidado y no permite nuevas acciones.",
            )
            return redirect("siniestro_detail", pk=siniestro_id)

        # Si pasa las validaciones, mostramos el formulario
        form = FiniquitoForm(initial={"fecha_finiquito": date.today()})
        print(
            f"--- DEBUG: Mostrando formulario de finiquito para siniestro {siniestro_id} ---"
        )
        return render(
            request, self.template_name, {"form": form, "siniestro": siniestro}
        )

    def post(self, request, siniestro_id):
        print(f"--- DEBUG: Recibiendo POST para Siniestro {siniestro_id} ---")
        form = FiniquitoForm(request.POST, request.FILES)
        print(f"--- DEBUG: Datos recibidos en POST: {request.POST} ---")
        print(f"--- DEBUG: Archivos recibidos en POST: {request.FILES} ---")

        if form.is_valid():
            print(f"--- DEBUG: Formulario válido para Siniestro {siniestro_id} ---")
            try:
                # Llamamos al servicio para calcular y guardar
                finiquito = FiniquitoService.liquidar_siniestro(
                    siniestro_id=siniestro_id,
                    data=form.cleaned_data,
                    archivo_firmado=request.FILES.get("documento_firmado"),
                    usuario=request.user,
                )
                print(f"--- DEBUG: Finiquito creado correctamente: {finiquito} ---")
                messages.success(
                    request,
                    f"Siniestro Liquidado. Valor a Pagar: ${finiquito.valor_final_pago}",
                )
                return redirect("siniestro_detail", pk=siniestro_id)

            except ValidationError as e:
                print(
                    f"--- DEBUG: Error de validación al liquidar siniestro {siniestro_id}: {e} ---"
                )
                messages.error(request, str(e))
        else:
            print(f"--- DEBUG: Errores del formulario: {form.errors} ---")

        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        print(
            f"--- DEBUG: Renderizando nuevamente formulario por error en POST para siniestro {siniestro_id} ---"
        )
        return render(
            request, self.template_name, {"form": form, "siniestro": siniestro}
        )


class RepararSiniestroView(LoginRequiredMixin, View):
    def post(self, request, pk):
        siniestro = get_object_or_404(Siniestro, pk=pk)
        resultado = request.POST.get("resultado")

        if siniestro.estado_tramite != "ENVIADO_ASEGURADORA":
            messages.warning(
                request,
                "Esta acción solo se puede realizar cuando el siniestro ha sido enviado a la aseguradora.",
            )
            return redirect("siniestro_detail", pk=pk)

        if resultado == "ARREGLADO":
            siniestro.estado_tramite = "REPARACION"
            siniestro.resultado = "ARREGLADO"
            siniestro.save()
            messages.success(
                request,
                f"El bien '{siniestro.bien.detalle}' ha sido marcado como arreglado.",
            )

        elif resultado == "REEMPLAZADO":
            serie = request.POST.get("serie")
            marca = request.POST.get("marca")
            modelo = request.POST.get("modelo")

            if not all([serie, marca, modelo]):
                messages.error(
                    request,
                    "Debe proporcionar todos los datos para el reemplazo del bien.",
                )
                return redirect("siniestro_detail", pk=pk)

            with transaction.atomic():  # Wrap the replacement logic in a transaction
                # Lógica para reemplazar el bien
                bien_antiguo = siniestro.bien
                bien_antiguo.estado_operativo = "INACTIVO"
                bien_antiguo.save()

                # Crear un nuevo bien con datos actualizados
                nuevo_codigo = f"{bien_antiguo.codigo}-R"

                nuevo_bien = Bien.objects.create(
                    custodio=bien_antiguo.custodio,
                    codigo=nuevo_codigo,
                    baan_v=bien_antiguo.baan_v,
                    detalle=f"Reemplazo de: {bien_antiguo.detalle}",
                    serie=serie,
                    modelo=modelo,
                    marca=marca,
                    estado_fisico="B",
                    estado_operativo="ACTIVO",
                )

                # Actualizar el siniestro para que apunte al nuevo bien
                siniestro.bien = nuevo_bien
                siniestro.estado_tramite = "REPARACION"
                siniestro.resultado = "REEMPLAZADO"
                siniestro.save()
                messages.success(
                    request,
                    f"El bien '{bien_antiguo.detalle}' ha sido reemplazado por '{nuevo_bien.detalle}'.",
                )

        else:
            messages.error(request, "Acción no válida.")

        return redirect("siniestro_detail", pk=pk)


class EnviarAseguradoraView(LoginRequiredMixin, View):
    def post(self, request, pk):
        siniestro = get_object_or_404(Siniestro, pk=pk)
        if siniestro.estado_tramite == "REPORTADO":
            siniestro.estado_tramite = "ENVIADO_ASEGURADORA"
            siniestro.save()
            messages.success(request, "El siniestro ha sido enviado a la aseguradora.")
        else:
            messages.warning(
                request,
                "Esta acción no se puede realizar en el estado actual del siniestro.",
            )
        return redirect("siniestro_detail", pk=pk)


# ---------------------------------------------
# NOTIFICACIONES
# ---------------------------------------------


def lista_notificaciones(request):
    """Muestra todas las alertas del usuario logueado"""
    # Asumiendo que usas el login_universal y 'request.user' tiene el usuario
    # Si tu usuario está en request.session['usuario_id'], ajusta esto.
    # Usaremos request.user suponiendo autenticación estándar de Django:

    notificaciones = NotificacionService.listar_mis_notificaciones(request.user)

    return render(
        request, "lista_notificaciones.html", {"notificaciones": notificaciones}
    )


def marcar_notificacion_leida(request, notificacion_id):
    """Acción para marcar leída y redirigir"""
    NotificacionService.leer_notificacion(notificacion_id, request.user)
    messages.success(request, "Notificación marcada como leída.")
    return redirect("lista_notificaciones")


def buscar_custodios_ajax(request):
    term = request.GET.get("term", "")
    # Buscamos por nombre o cédula
    custodios = ResponsableCustodio.objects.filter(
        nombre_completo__icontains=term
    ) | ResponsableCustodio.objects.filter(identificacion__icontains=term)

    results = [
        {"id": c.id, "text": f"{c.nombre_completo} ({c.identificacion})"}
        for c in custodios[:10]
    ]
    return JsonResponse({"results": results})


# Vista para buscar Bienes (Por Código) y devolver detalles
def buscar_bienes_ajax(request):
    term = request.GET.get("term", "")
    custodio_id = request.GET.get("custodio_id")  # Viene del JS como string o vacío

    query = Q(estado_operativo="ACTIVO") & (
        Q(codigo__icontains=term) | Q(detalle__icontains=term)
    )
    bienes = Bien.objects.filter(query)

    if custodio_id and custodio_id.isdigit():  # Validación de seguridad
        bienes = bienes.filter(custodio_id=int(custodio_id))

    results = []
    for b in bienes:
        results.append(
            {
                "id": b.id,
                "text": f"{b.codigo} - {b.detalle[:40]}",
                # Atributos extra para el autorrellenado en el frontend
                "nombre_completo": b.detalle,
                "marca": b.marca or "N/A",
                "modelo": b.modelo or "N/A",
                "serie": b.serie or "N/A",
                "ubicacion": (
                    f"{b.custodio.edificio} - {b.custodio.puesto}"
                    if b.custodio.puesto
                    else ""
                ),
            }
        )
    return JsonResponse({"results": results})
