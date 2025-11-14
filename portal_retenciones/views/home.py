# En: portal_retenciones/views/home.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# -- Vista para la página de login (Homepage)
def home_view(request):
    return render(request, 'login.html')


# -- Vista para el menú principal (requiere login)
@login_required
def menu_view(request):
    return render(request, 'menu.html')