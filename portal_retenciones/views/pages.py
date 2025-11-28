# En: portal_retenciones/views/pages.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from portal_retenciones.decorators import permission_required
from django.utils import timezone

# Importamos los modelos necesarios
from portal_retenciones.models import (
    Cliente, 
    Solicitud, 
    EjecutivoRetencion, 
    AnalistaRetencion,
    Comentario,
    HistorialEstado,
    EstadoAtencion,
)

# --- VISTAS DE PÁGINA EXISTENTES ---

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
    
    # Obtener los circuitos asociados a la solicitud
    circuitos_asociados = solicitud.circuitos.all()
    
    # Obtener comentarios ordenados por fecha (más reciente primero)
    comentarios = Comentario.objects.filter(solicitud=solicitud).order_by('-fecha_comentario')
    
    # Obtener historial de estados ordenados por fecha (más reciente primero)
    historial_estado = HistorialEstado.objects.filter(solicitud=solicitud).order_by('-fecha_cambio')
    
    # Obtener todos los estados disponibles para el selector
    estados_disponibles = EstadoAtencion.objects.all()
    
    context = {
        'solicitud': solicitud,
        'circuitos_asociados': circuitos_asociados,
        'comentarios': comentarios,
        'historial_estado': historial_estado,
        'estados_disponibles': estados_disponibles,
    }
    
    return render(request, 'solicitud_detalle.html', context)


@login_required
def procesar_accion_solicitud(request, solicitud_id):
    """Procesa las acciones sobre una solicitud: agregar comentario o cambiar estado."""
    
    if request.method != 'POST':
        return redirect('solicitud_detalle', solicitud_id=solicitud_id)
    
    solicitud = get_object_or_404(Solicitud, id=solicitud_id)
    
    # Determinar qué acción se está ejecutando
    accion = request.POST.get('accion')
    
    # --- ACCIÓN: Agregar Comentario ---
    if accion == 'agregar_comentario':
        comentario_texto = request.POST.get('comentario', '').strip()
        
        if comentario_texto:
            Comentario.objects.create(
                solicitud=solicitud,
                usuario=f"{request.user.first_name} {request.user.last_name}" or request.user.username,
                comentario=comentario_texto
            )
            messages.success(request, '✅ Comentario agregado exitosamente.')
        else:
            messages.warning(request, '⚠️ El comentario no puede estar vacío.')
    
    # --- ACCIÓN: Cambiar Estado ---
    elif accion == 'cambiar_estado':
        nuevo_estado_id = request.POST.get('nuevo_estado')
        
        if nuevo_estado_id:
            try:
                nuevo_estado = EstadoAtencion.objects.get(id=nuevo_estado_id)
                estado_anterior = solicitud.estado_actual
                
                # Solo registrar si el estado cambió
                if nuevo_estado.id != estado_anterior.id:
                    # Crear registro en el historial
                    HistorialEstado.objects.create(
                        solicitud=solicitud,
                        estado_anterior=estado_anterior,
                        estado_nuevo=nuevo_estado,
                        usuario_cambio=f"{request.user.first_name} {request.user.last_name}" or request.user.username
                    )
                    
                    # Actualizar el estado actual de la solicitud
                    solicitud.estado_actual = nuevo_estado
                    solicitud.save()
                    
                    messages.success(request, f'✅ Estado cambiado a: {nuevo_estado.nombre_estado}')
                else:
                    messages.info(request, 'ℹ️ El estado seleccionado es el mismo que el actual.')
                    
            except EstadoAtencion.DoesNotExist:
                messages.error(request, '❌ Estado no válido.')
        else:
            messages.warning(request, '⚠️ Debe seleccionar un estado.')
    
    # Redirigir de vuelta a la página de detalle
    return redirect('solicitud_detalle', solicitud_id=solicitud_id)


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
    }

    return render(request, 'dashboard.html', context)