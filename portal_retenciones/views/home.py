# En: portal_retenciones/views/home.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from portal_retenciones.decorators import permission_required

# -- Vista para la página de login (Homepage)
def home_view(request):
    return render(request, 'login.html')


# -- Vista para el menú principal (ACTUALIZADO CON PERMISO)
@permission_required('portal_retenciones.can_view_menu')
def menu_view(request):
    return render(request, 'menu.html')