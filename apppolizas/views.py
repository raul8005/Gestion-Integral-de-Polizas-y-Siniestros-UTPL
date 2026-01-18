import json

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View, DetailView
from datetime import date

from xhtml2pdf import pisa

from apppolizas.models import Poliza, Siniestro, Factura, DocumentoSiniestro, ResponsableCustodio, Bien
from django.views.generic import DetailView

from django.db.models import Q

from .forms import PolizaForm, SiniestroPorPolizaForm, SiniestroForm, SiniestroEditForm, FacturaForm, DocumentoSiniestroForm, CustodioForm, FiniquitoForm
from .repositories import SiniestroRepository, UsuarioRepository, FiniquitoRepository
from .services import AuthService, PolizaService, SiniestroService, FacturaService, DocumentoService, CustodioService, FiniquitoService, NotificacionService, BienService


# =====================================================
# LOGOUT
# =====================================================
@csrf_exempt
def logout_view(request):
    logout(request)
    return JsonResponse({'success': True})


# =====================================================
# LOGIN
# =====================================================
class LoginView(View):
    template_name = 'login.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        try:
            username = request.POST.get('username')
            password = request.POST.get('password')

            if not username or not password:
                return JsonResponse(
                    {'success': False, 'error': 'Usuario y contraseña requeridos'},
                    status=400
                )

            user, rol = AuthService.login_universal(username, password)
            login(request, user)

            redirect_url = (
                '/administrador/dashboard/'
                if rol == 'admin'
                else '/dashboard-analista/'
            )

            return JsonResponse({'success': True, 'redirect_url': redirect_url})

        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=401)

        except Exception as e:
            print('ERROR LOGIN:', e)
            return JsonResponse(
                {'success': False, 'error': 'Error interno del servidor'},
                status=500
            )


# =====================================================
# DASHBOARD ADMIN
# =====================================================
class DashboardAdminView(LoginRequiredMixin, TemplateView):
    template_name = 'administrador/dashboard_admin.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'admin':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_usuarios'] = UsuarioRepository.get_all_usuarios().count()
        context['total_polizas'] = PolizaService.listar_polizas().count()
        return context


class AdminUsuariosView(LoginRequiredMixin, TemplateView):
    template_name = 'administrador/usuarios.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'admin':
            return redirect('usuarios')
        return super().dispatch(request, *args, **kwargs)


# =====================================================
# DASHBOARD ANALISTA
# =====================================================
class DashboardAnalistaView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard_analista.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_admin')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_activas'] = PolizaService.contar_polizas_activas()
        context['total_vencidas'] = PolizaService.contar_polizas_vencidas()
        context['total_siniestros'] = SiniestroService.listar_todos().count()
        context['total_facturas'] = FacturaService.listar_facturas().count()
        context['ultimos_siniestros'] = SiniestroService.listar_todos().order_by('-fecha_siniestro')[:5]
        return context

# =====================================================
# API USUARIOS (SOLO ADMIN)
# =====================================================
@method_decorator(csrf_exempt, name='dispatch')
class UsuarioCRUDView(LoginRequiredMixin, View):

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'admin':
            return JsonResponse(
                {'error': 'No tienes permisos de administrador'},
                status=403
            )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, usuario_id=None):
        if usuario_id:
            usuario = UsuarioRepository.get_by_id(usuario_id)
            if not usuario:
                return JsonResponse({'error': 'Usuario no encontrado'}, status=404)

            data = {
                'id': usuario.id,
                'username': usuario.username,
                'email': usuario.email,
                'rol': usuario.rol,
                'cedula': usuario.cedula,
                'estado': usuario.estado
            }
            return JsonResponse(data)

        usuarios = UsuarioRepository.get_all_usuarios()
        data = list(
            usuarios.values('id', 'username', 'email', 'rol', 'cedula', 'estado')
        )
        return JsonResponse(data, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
            user = UsuarioRepository.create_usuario(data)
            return JsonResponse(
                {'success': True, 'message': 'Usuario creado', 'id': user.id},
                status=201
            )
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def put(self, request, usuario_id):
        try:
            data = json.loads(request.body)
            usuario = UsuarioRepository.update_usuario(usuario_id, data)
            return JsonResponse(
                {'success': True, 'message': f'Usuario {usuario.username} actualizado'}
            )
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    def delete(self, request, usuario_id):
        try:
            UsuarioRepository.delete_usuario(usuario_id)
            return JsonResponse({'success': True, 'message': 'Usuario eliminado'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


# =====================================================
# PÓLIZAS (SOLO ANALISTA)
# =====================================================
class PolizaListView(LoginRequiredMixin, View):
    template_name = 'polizas.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        polizas = PolizaService.listar_polizas()
        form = PolizaForm()
        return render(
            request,
            self.template_name,
            {'polizas': polizas, 'form': form}
        )

    def post(self, request):
        form = PolizaForm(request.POST)
        if form.is_valid():
            try:
                # 1. Obtenemos los datos del formulario
                datos_poliza = form.cleaned_data
                
                # 2. ¡EL CAMBIO CLAVE! Inyectamos el usuario logueado
                datos_poliza['usuario_gestor'] = request.user 
                
                # 3. Llamamos al servicio con los datos completos
                PolizaService.crear_poliza(datos_poliza)
                
                messages.success(request, 'Póliza creada exitosamente')
                return redirect('polizas_list')
            except Exception as e:
                messages.error(request, str(e))

        polizas = PolizaService.listar_polizas()
        return render(
            request,
            self.template_name,
            {'polizas': polizas, 'form': form}
        )


class PolizaUpdateView(LoginRequiredMixin, View):
    template_name = 'poliza_edit.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        poliza = PolizaService.obtener_poliza(pk)
        form = PolizaForm(instance=poliza)
        return render(
            request,
            self.template_name,
            {'form': form, 'poliza': poliza}
        )

    def post(self, request, pk):
        poliza = PolizaService.obtener_poliza(pk)
        form = PolizaForm(request.POST, instance=poliza)

        if form.is_valid():
            PolizaService.actualizar_poliza(pk, form.cleaned_data)
            messages.success(request, 'Póliza actualizada')
            return redirect('polizas_list')

        messages.error(request, 'Corrige los errores del formulario')
        return render(
            request,
            self.template_name,
            {'form': form, 'poliza': poliza}
        )


class PolizaDeleteView(LoginRequiredMixin, View):

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        PolizaService.eliminar_poliza(pk)
        messages.success(request, 'Póliza eliminada')
        return redirect('polizas_list')
    
class PolizaDetailView(LoginRequiredMixin, DetailView):
    model = Poliza
    template_name = 'poliza_detail.html'
    context_object_name = 'poliza'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['siniestros'] = SiniestroService.listar_por_poliza(self.object.id)
        return context


#------------------------------------------------------
# SINESTRO 
#------------------------------------------------------
class SiniestroListView(LoginRequiredMixin, View):
    template_name = 'siniestros.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        siniestros = SiniestroService.listar_todos()

        return render(request, self.template_name, {
            'siniestros': siniestros,
            'total_siniestros': siniestros.count(),
            'total_polizas': siniestros.values('poliza').distinct().count(),
            'form': SiniestroForm(),
        })

    # views.py (SiniestroListView)
    def post(self, request, *args, **kwargs):
        form = SiniestroForm(request.POST)
        if form.is_valid():
            try:
                # CORRECCIÓN: El nombre del parámetro debe ser poliza_id
                SiniestroService.crear_siniestro(
                    poliza=form.cleaned_data['poliza'], # <--- Aquí estaba el error
                    data=form.cleaned_data,
                    usuario=request.user
                )
                messages.success(request, "Siniestro creado")
                return redirect('siniestros')
            except ValidationError as e:
                messages.error(request, str(e))




class SiniestroPorPolizaView(LoginRequiredMixin, View):
    template_name = 'siniestros.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, poliza_id):
        poliza = PolizaService.obtener_poliza(poliza_id)
        siniestros = SiniestroService.listar_por_poliza(poliza_id)

        return render(request, self.template_name, {
            'poliza': poliza,
            'siniestros': siniestros,
            'form': SiniestroPorPolizaForm(),
        })

    def post(self, request, poliza_id):
        poliza = PolizaService.obtener_poliza(poliza_id)
        form = SiniestroPorPolizaForm(request.POST)

        if form.is_valid():
            SiniestroService.crear_siniestro(
                poliza=poliza,
                data=form.cleaned_data,
                usuario=request.user
            )
            messages.success(request, 'Siniestro registrado correctamente')
            return redirect('siniestros_por_poliza', poliza_id=poliza_id)

        siniestros = SiniestroService.listar_por_poliza(poliza_id)
        return render(request, self.template_name, {
            'poliza': poliza,
            'siniestros': siniestros,
            'form': form
        })


class SiniestroDetailView(LoginRequiredMixin, DetailView):
    model = Siniestro
    template_name = 'siniestro_detail.html'
    context_object_name = 'siniestro'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # --- Tu lógica actual ---
        context['siniestros_relacionados'] = SiniestroService.listar_por_poliza(
            self.object.poliza.id
        ).exclude(id=self.object.id)

        # --- Nueva lógica para Expediente Digital ---
        # 1. Agregamos el formulario para subir archivos (debes importarlo)
        context['form_documento'] = DocumentoSiniestroForm()
        
        # 2. Listamos los documentos guardados en MinIO para este siniestro
        context['documentos'] = DocumentoService.listar_evidencias(self.object.id)
        
        return context

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)
    

class SiniestroEditView(LoginRequiredMixin, View):
    template_name = 'siniestro_edit.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        # Usamos el repositorio para obtener los datos
        siniestro = SiniestroRepository.get_by_id(pk)
        if not siniestro:
            return redirect('siniestros')
            
        form = SiniestroEditForm(instance=siniestro)
        return render(request, self.template_name, {'form': form, 'siniestro': siniestro})

    def post(self, request, pk):
        siniestro_instancia = SiniestroRepository.get_by_id(pk)
        
        # Pasamos request.FILES por si algún día permites subir archivos aquí
        form = SiniestroEditForm(request.POST, request.FILES, instance=siniestro_instancia)

        if form.is_valid():
            try:
                # Si usas ModelForm, a veces basta con form.save(), 
                # pero respetamos tu servicio:
                SiniestroService.actualizar_siniestro(pk, form.cleaned_data)
                
                messages.success(request, 'Siniestro actualizado correctamente')
                
                # REDIRECCIÓN: Aquí es donde te enviamos al detalle tras guardar
                return redirect('siniestro_detail', pk=pk)
                
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            # === AQUÍ ESTABA EL PROBLEMA ===
            # Antes solo hacías print(form.errors). Ahora enviamos el mensaje al usuario.
            messages.error(request, "No se pudo guardar. Verifique que el Bien pertenezca al Custodio seleccionado.")
        
        return render(request, self.template_name, {'form': form, 'siniestro': siniestro_instancia})

class SiniestroDeleteView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        siniestro = Siniestro.objects.get(pk=pk)
        siniestro.delete()
        messages.success(request, 'Siniestro eliminado correctamente')
        return redirect('siniestros')

#------------------------------------------------------
# Factura
#------------------------------------------------------

# 1. Listar Facturas
def lista_facturas(request):
    """
    Muestra el historial usando el Servicio (Capa de Negocio).
    """
    # YA NO USAMOS: Factura.objects.all()
    # USAMOS EL SERVICIO:
    facturas = FacturaService.listar_facturas()
    return render(request, 'lista_facturas.html', {'facturas': facturas})

# 2. Registrar Nueva Factura
def crear_factura(request):
    """
    Crea la factura enviando los datos limpios al Servicio.
    """
    if request.method == 'POST':
        form = FacturaForm(request.POST)
        if form.is_valid():
            try:
                # YA NO USAMOS: form.save()
                # USAMOS EL SERVICIO pasando los datos limpios (diccionario):
                FacturaService.crear_factura(form.cleaned_data)
                
                messages.success(request, "Factura registrada y calculada correctamente.")
                return redirect('lista_facturas')
            except ValidationError as e:
                messages.error(request, f"Error de validación: {e}")
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado: {e}")
        else:
            messages.error(request, "Error en el formulario. Verifica los datos.")
    else:
        form = FacturaForm()
    
    return render(request, 'form_factura.html', {'form': form})

# 3. Generar PDF de Factura
def generar_pdf_factura(request, factura_id):
    # Usamos el servicio para obtener la factura (incluye validación de existencia)
    try:
        factura = FacturaService.obtener_factura(factura_id)
    except ValidationError:
        return HttpResponse("La factura no existe", status=404)
    
    template_path = 'factura_pdf.html'
    context = {'factura': factura}
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="factura_{factura.numero_factura}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse(f'Error al generar PDF: <pre>{html}</pre>')
    
    return response





# Vistas para gestión de documentos de siniestro
class SubirEvidenciaView(LoginRequiredMixin, View):
    
    def post(self, request, siniestro_id):
        form = DocumentoSiniestroForm(request.POST, request.FILES) # ¡Importante request.FILES!
        
        if form.is_valid():
            try:
                DocumentoService.subir_evidencia(
                    siniestro_id=siniestro_id,
                    data_form=form.cleaned_data,
                    archivo=request.FILES['archivo'],
                    usuario=request.user
                )
                messages.success(request, "Documento subido correctamente a MinIO.")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, "Error al subir el archivo.")
        else:
            messages.error(request, "Error en el formulario.")
            
        # Redirigir de vuelta al detalle del siniestro
        return redirect('siniestro_detail', pk=siniestro_id)
    

class SiniestroDeleteEvidenciaView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        # Buscamos el documento o damos error 404 si no existe
        documento = get_object_or_404(DocumentoSiniestro, pk=pk)
        
        # Guardamos el ID del siniestro para volver ahí después de borrar
        siniestro_id = documento.siniestro.id
        
        # Eliminamos el registro (y el archivo si está configurado en signals)
        documento.delete()
        
        messages.success(request, 'Documento eliminado correctamente del expediente.')
        return redirect('siniestro_detail', pk=siniestro_id)
    

# 1. LISTADO DE CUSTODIOS (Pantalla Principal)
class CustodioListView(LoginRequiredMixin, View):
    template_name = 'custodios.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Solo obtenemos la lista para pintarla en el template
        custodios = CustodioService.listar_custodios()
        return render(request, self.template_name, {
            'custodios': custodios
        })

# 2. DETALLE DE CUSTODIO (API JSON para el Modal)
class CustodioDetailApiView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            custodio = CustodioService.obtener_custodio(pk)
            data = {
                'nombre': custodio.nombre_completo,
                'identificacion': custodio.identificacion,
                'correo': custodio.correo,
                'departamento': custodio.departamento,
                'ciudad': custodio.ciudad if custodio.ciudad else 'N/A',
                'edificio': custodio.edificio if custodio.edificio else 'N/A',
                'puesto': custodio.puesto if custodio.puesto else 'N/A',
            }
            return JsonResponse({'success': True, 'data': data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=404)

# 3. LISTADO DE BIENES DE UN CUSTODIO (Nueva Pantalla)
class BienesPorCustodioView(LoginRequiredMixin, View):
    template_name = 'bienes_custodio.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.rol != 'analista':
            return redirect('dashboard_analista')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, custodio_id):
        try:
            custodio = CustodioService.obtener_custodio(custodio_id)
            bienes = BienService.listar_por_custodio(custodio_id)
            
            return render(request, self.template_name, {
                'custodio': custodio,
                'bienes': bienes
            })
        except ValidationError:
            messages.error(request, "Custodio no encontrado")
            return redirect('custodios_list')

# 4. DETALLE DE BIEN (API JSON para el Modal)
class BienDetailApiView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            bien = BienService.obtener_detalle_bien(pk)
            data = {
                'codigo': bien.codigo,
                'detalle': bien.detalle,
                'marca': bien.marca if bien.marca else 'N/A',
                'modelo': bien.modelo if bien.modelo else 'N/A',
                'serie': bien.serie if bien.serie else 'N/A',
                'estado_fisico': bien.get_estado_fisico_display(), # Obtiene el texto (Bueno/Regular/Malo)
                'baan_v': bien.baan_v if bien.baan_v else 'N/A'
            }
            return JsonResponse({'success': True, 'data': data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=404)

class FiniquitoCreateView(LoginRequiredMixin, View):
    template_name = 'finiquito_create.html'

    def get(self, request, siniestro_id):
        print(f"--- DEBUG: Entrando al GET de FiniquitoCreateView para Siniestro {siniestro_id} ---")
        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        print(f"--- DEBUG: Resultado de búsqueda siniestro: {siniestro} ---")

        # SEGURIDAD 1: Verificar que el siniestro existe
        if not siniestro:
            print(f"--- DEBUG: Siniestro {siniestro_id} no existe ---")
            messages.error(request, "El siniestro no existe.")
            return redirect('siniestros')

        # SEGURIDAD 2: Verificar estado o existencia de finiquito
        ya_tiene_finiquito = FiniquitoRepository.get_by_siniestro(siniestro_id)
        print(f"--- DEBUG: ¿Ya tiene finiquito? {ya_tiene_finiquito} ---")

        if siniestro.estado_tramite == 'LIQUIDADO' or ya_tiene_finiquito:
            print(f"--- DEBUG: Siniestro {siniestro_id} ya liquidado o con finiquito existente ---")
            messages.warning(request, "Este siniestro ya ha sido liquidado y no permite nuevas acciones.")
            return redirect('siniestro_detail', pk=siniestro_id)

        # Si pasa las validaciones, mostramos el formulario
        form = FiniquitoForm(initial={'fecha_finiquito': date.today()})
        print(f"--- DEBUG: Mostrando formulario de finiquito para siniestro {siniestro_id} ---")
        return render(request, self.template_name, {
            'form': form,
            'siniestro': siniestro
        })

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
                    archivo_firmado=request.FILES.get('documento_firmado'),
                    usuario=request.user
                )
                print(f"--- DEBUG: Finiquito creado correctamente: {finiquito} ---")
                messages.success(request, f"Siniestro Liquidado. Valor a Pagar: ${finiquito.valor_final_pago}")
                return redirect('siniestro_detail', pk=siniestro_id)

            except ValidationError as e:
                print(f"--- DEBUG: Error de validación al liquidar siniestro {siniestro_id}: {e} ---")
                messages.error(request, str(e))
        else:
            print(f"--- DEBUG: Errores del formulario: {form.errors} ---")

        siniestro = SiniestroRepository.get_by_id(siniestro_id)
        print(f"--- DEBUG: Renderizando nuevamente formulario por error en POST para siniestro {siniestro_id} ---")
        return render(request, self.template_name, {'form': form, 'siniestro': siniestro})
    
# ---------------------------------------------
# NOTIFICACIONES
# ---------------------------------------------

def lista_notificaciones(request):
    """Muestra todas las alertas del usuario logueado"""
    # Asumiendo que usas el login_universal y 'request.user' tiene el usuario
    # Si tu usuario está en request.session['usuario_id'], ajusta esto.
    # Usaremos request.user suponiendo autenticación estándar de Django:
    
    notificaciones = NotificacionService.listar_mis_notificaciones(request.user)
    
    return render(request, 'lista_notificaciones.html', {
        'notificaciones': notificaciones
    })

def marcar_notificacion_leida(request, notificacion_id):
    """Acción para marcar leída y redirigir"""
    NotificacionService.leer_notificacion(notificacion_id, request.user)
    messages.success(request, "Notificación marcada como leída.")
    return redirect('lista_notificaciones')


def buscar_custodios_ajax(request):
    term = request.GET.get('term', '')  # Lo que escribe el usuario
    custodios = ResponsableCustodio.objects.filter(
        Q(nombre_completo__icontains=term) | 
        Q(identificacion__icontains=term)
    )[:20]  # Limitamos a 20 resultados para rapidez
    
    results = []
    for c in custodios:
        results.append({
            'id': c.id,
            'text': f"{c.nombre_completo} ({c.identificacion})"
        })
    return JsonResponse({'results': results})

# Vista para buscar Bienes (Por Código) y devolver detalles
def buscar_bienes_ajax(request):
    term = request.GET.get('term', '')
    # Buscamos por código o descripción
    bienes = Bien.objects.filter(
        Q(codigo__icontains=term) | 
        Q(detalle__icontains=term)
    )[:20]
    
    results = []
    for b in bienes:
        # Construimos la ubicación basada en el custodio (ya que el bien hereda ubicación)
        ubicacion_txt = f"{b.custodio.edificio or ''} - {b.custodio.puesto or ''}"
        
        results.append({
            'id': b.id,
            'text': f"{b.codigo} - {b.detalle[:40]}...",
            # Datos extra para el autorrellenado:
            'nombre_completo': b.detalle,
            'ubicacion': ubicacion_txt
        })
    return JsonResponse({'results': results})