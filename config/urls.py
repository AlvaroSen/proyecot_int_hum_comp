# En: config/urls.py

from django.contrib import admin
from django.urls import path

# Importamos los módulos de vistas
from portal_retenciones.views import home
from portal_retenciones.views.auth import auth as auth_views
from portal_retenciones.views import pages
from portal_retenciones.views import api  # Importamos el módulo api

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Sistema de Autenticación ---
    path('', home.home_view, name='home'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # --- Páginas de la Aplicación (Protegidas) ---
    path('menu/', home.menu_view, name='menu'),
    path('solicitud/nueva/', pages.nueva_solicitud_view, name='nueva_solicitud'),
    path('solicitudes/lista/', pages.lista_solicitudes_view, name='lista_solicitudes'),
    path('perfil/', pages.perfil_view, name='perfil'),
    
    # --- API para búsquedas ---
    path('search/clientes/', api.search_clientes, name='search_clientes'),
    
    # ▼▼▼ ¡NUEVA RUTA AÑADIDA! ▼▼▼
    # Esta ruta captura el ID del cliente desde la URL y lo pasa a la vista
    path('api/get-circuitos/<int:cliente_id>/', api.get_circuitos_por_cliente, name='get_circuitos_por_cliente'),
]