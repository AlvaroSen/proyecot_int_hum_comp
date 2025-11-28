# En: portal_retenciones/views/pages.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from portal_retenciones.decorators import permission_required

# Importamos solo los modelos necesarios para las 4 métricas principales
from portal_retenciones.models import (
    Cliente, 
    Solicitud, 
    EjecutivoRetencion, 
    AnalistaRetencion,
    # Ya no es necesaria la importación de 'Count'
)

# --- VISTAS DE PÁGINA EXISTENTES (SIN CAMBIOS) ---

@permission_required('portal_retenciones.can_create_solicitud')
def nueva_solicitud_view(request):
    """Muestra el formulario para crear una nueva solicitud."""
    return render(request, 'nueva_solicitud.html', {})

@permission_required('portal_retenciones.can_view_solicitud_list')
def lista_solicitudes_view(request):
    """Muestra la lista de todas las solicitudes."""
    solicitudes = Solicitud.objects.all().order_by('-fecha_creacion')
    return render(request, 'lista_solicitudes.html', {'solicitudes': solicitudes})

@permission_required('portal_retenciones.can_view_personal')
def personal_view(request):
    """Muestra la lista de personal activo (Ejecutivos y Analistas)."""
    ejecutivos = EjecutivoRetencion.objects.filter(activo=True)
    analistas = AnalistaRetencion.objects.filter(activo=True)
    return render(request, 'personal.html', {'ejecutivos': ejecutivos, 'analistas': analistas})

@login_required
def solicitud_detalle_view(request, solicitud_id):
    """Muestra el detalle y la trazabilidad de una solicitud específica."""
    solicitud = get_object_or_404(Solicitud, id=solicitud_id)
    return render(request, 'solicitud_detalle.html', {'solicitud': solicitud})

@permission_required('portal_retenciones.can_manage_personnel')
def gestion_personal_view(request):
    """Muestra la interfaz para gestionar la asignación de personal a roles."""
    return render(request, 'gestion_personal.html', {})

@login_required
def perfil_view(request):
    """Muestra la información de perfil del usuario logeado."""
    return render(request, 'perfil.html', {})


# --- VISTA DE DASHBOARD (SIMPLIFICADA) ---
@login_required
@permission_required('portal_retenciones.can_view_menu')
def dashboard_view(request):
    """Calcula y muestra las métricas clave del portal (solo totales)."""
    
    # 1. Conteo de Clientes
    total_clientes = Cliente.objects.count()

    # 2. Conteo de Solicitudes Totales
    total_solicitudes = Solicitud.objects.count()

    # 3. Solicitudes Pendientes
    solicitudes_pendientes = Solicitud.objects.filter(
        estado_actual__nombre_estado__in=['Registrado', 'En Análisis']
    ).count()

    # 4. Solicitudes Resueltas (por resta)
    solicitudes_resueltas = total_solicitudes - solicitudes_pendientes

    context = {
        'total_clientes': total_clientes,
        'total_solicitudes': total_solicitudes,
        'solicitudes_pendientes': solicitudes_pendientes,
        'solicitudes_resueltas': solicitudes_resueltas,
        # Ya NO se incluye 'distribucion_estado_list'
    }

    return render(request, 'dashboard.html', context)