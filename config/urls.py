# En: config/urls.py

from django.contrib import admin
from django.urls import path

# -- Importamos los módulos de vistas
from portal_retenciones.views import home
from portal_retenciones.views.auth import auth as auth_views
from portal_retenciones.views import pages
from portal_retenciones.views import api

urlpatterns = [
    path('admin/', admin.site.urls),

    # -- Autenticación
    path('', home.home_view, name='home'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # -- Páginas de la Aplicación
    path('menu/', home.menu_view, name='menu'),
    path('dashboard/', pages.dashboard_view, name='dashboard'), 
    
    path('solicitud/nueva/', pages.nueva_solicitud_view, name='nueva_solicitud'),
    path('solicitudes/lista/', pages.lista_solicitudes_view, name='lista_solicitudes'),
    path('personal/', pages.personal_view, name='personal'),
    
    # -- RUTAS DE DETALLE DE SOLICITUD
    path('solicitud/detalle/<int:solicitud_id>/', pages.solicitud_detalle_view, name='solicitud_detalle'),
    path('solicitud/<int:solicitud_id>/accion/', pages.procesar_accion_solicitud, name='procesar_accion_solicitud'),  # NUEVA RUTA
    
    path('gestion-personal/', pages.gestion_personal_view, name='gestion_personal'),
    path('perfil/', pages.perfil_view, name='perfil'),
    
    # -- API
    path('search/clientes/', api.search_clientes, name='search_clientes'),
    path('api/get-circuitos/<int:cliente_id>/', api.get_circuitos_por_cliente, name='get_circuitos_por_cliente'),
]