# En: portal_retenciones/views/home.py

from django.shortcuts import render
# Importamos el decorador para proteger la vista
from django.contrib.auth.decorators import login_required

# Esta vista muestra el formulario de login
def home_view(request):
    return render(request, 'login.html')


# Vista para la página principal DESPUÉS de iniciar sesión (Menu/Inicio)
@login_required
def menu_view(request):
    # Renderiza el template menu.html que vamos a crear
    return render(request, 'menu.html')