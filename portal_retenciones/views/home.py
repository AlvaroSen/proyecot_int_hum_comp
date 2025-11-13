# En: portal_retenciones/views/home.py

from django.shortcuts import render
# Importamos el decorador para proteger la vista
from django.contrib.auth.decorators import login_required

# Esta vista no cambia, solo muestra el formulario de login (index.html)
def home_view(request):
    return render(request, 'index.html')


# --- ¡NUEVA VISTA! ---
# Esta vista es para la página principal DESPUÉS de iniciar sesión
# @login_required: Django automáticamente redirige al usuario al
#                  login si intenta acceder a esta página sin sesión.
@login_required
def menu_view(request):
    # Renderiza la plantilla Menu.html
    return render(request, 'Menu.html')