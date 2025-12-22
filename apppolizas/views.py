from django.views.generic import FormView
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from .forms import LoginForm
from .services import AuthService
from django.views.generic import TemplateView

class LoginAnalistaView(FormView):
    template_name = 'login.html'
    form_class = LoginForm

    def post(self, request, *args, **kwargs):
        """
        Sobrescribimos el POST para responder con JSON para el manejo de JWT
        """
        form = self.get_form()
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            try:
                # Llamada al Servicio
                token = AuthService.login_analista(username, password)
                
                # Respuesta Exitosa con Token
                return JsonResponse({
                    'success': True,
                    'token': token,
                    'message': 'Inicio de sesión exitoso'
                }, status=200)

            except ValidationError as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=403)
        
        return JsonResponse({'success': False, 'error': 'Datos de formulario inválidos'}, status=400)



class DashboardAnalistaView(TemplateView):
    template_name = 'dashboard.html'        