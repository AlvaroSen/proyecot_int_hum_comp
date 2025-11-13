# En: config/urls.py

from django.contrib import admin
from django.urls import path

# Importamos los módulos de vistas
from portal_retenciones.views import home
from portal_retenciones.views.auth import auth as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # '/' -> Muestra la página de login (index.html)
    path('', home.home_view, name='home'),
    
    # '/menu/' -> Muestra la página de Menú (protegida)
    path('menu/', home.menu_view, name='menu'), # <-- ¡NUEVA RUTA!

    # '/login/' -> Procesa el envío del formulario (no muestra página)
    path('login/', auth_views.login_view, name='login'),

    # '/logout/' -> Cierra la sesión
    path('logout/', auth_views.logout_view, name='logout'),
]