# En: portal_retenciones/views/home.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from portal_retenciones.decorators import permission_required

# -- Importamos los modelos que necesitamos para la lógica
from portal_retenciones.models import Solicitud, EjecutivoRetencion, EstadoAtencion


# -- Vista para la página de login (Homepage)
def home_view(request):
    return render(request, 'login.html')


# -- Vista para el menú principal (ACTUALIZADO CON NOTIFICACIÓN DE TAREAS)
@permission_required('portal_retenciones.can_view_menu')
def menu_view(request):
    
    # 1. Lógica de Notificación (Solo para Ejecutivo Retención)
    if request.user.groups.filter(name='Ejecutivo Retencion').exists():
        try:
            # Buscamos la instancia de EjecutivoRetencion (se asume sincronización ID/ID)
            ejecutivo = EjecutivoRetencion.objects.get(id=request.user.id)
            
            # --- NUEVA LÓGICA: Contar solicitudes activas y asignadas ---
            # Asumimos que 'Registrado' y 'En Análisis' son estados activos/pendientes.
            solicitudes_pendientes_count = Solicitud.objects.filter(
                ejecutivo=ejecutivo,
                estado_actual__nombre_estado__in=['Registrado', 'En Análisis']
            ).count()
            
            if solicitudes_pendientes_count > 0:
                messages.info(request, 
                    f"¡Bienvenido, {request.user.first_name or request.user.username}! Tienes {solicitudes_pendientes_count} solicitudes pendientes de gestión."
                )
            # --- FIN NUEVA LÓGICA ---
                    
        except EjecutivoRetencion.DoesNotExist:
            # Si el usuario es ER pero el registro no está en la tabla de roles
            pass 

    return render(request, 'menu.html')