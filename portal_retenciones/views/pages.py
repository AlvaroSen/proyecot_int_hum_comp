# En: portal_retenciones/views/pages.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.db import IntegrityError
from django.http import Http404 # <-- ¡IMPORTACIÓN NECESARIA!
from django.utils import timezone # <-- ¡IMPORTACIÓN NECESARIA!
import random

from portal_retenciones.decorators import permission_required

from ..models import (
    Cliente, 
    Circuito, 
    Solicitud, 
    EstadoAtencion, 
    NivelAprobacion, 
    EjecutivoRetencion, 
    AnalistaRetencion,
    ConfiguracionAsignacion,
    Comentario, # <-- ¡MODELO NECESARIO PARA EL DETALLE!
    HistorialEstado # <-- ¡MODELO NECESARIO PARA EL DETALLE Y AUDITORÍA!
)

# --- Función auxiliar para la gestión de personal ---
def _get_user_key(user):
    """Returns user email or a safe, unique placeholder if email is empty."""
    # Retorna el email si existe, o un placeholder único si el email es vacío
    return user.email if user.email else f'{user.username}@temp.local'

# -----------------------------------------------------------------
# -- Lógica Round-Robin: Encontrar el siguiente ejecutivo
# -----------------------------------------------------------------
def get_next_ejecutivo():
    # 1. Obtener todos los ejecutivos activos, ordenados por ID
    ejecutivos_activos = EjecutivoRetencion.objects.filter(activo=True).order_by('id')
    
    if not ejecutivos_activos.exists():
        raise Exception("No hay ejecutivos activos disponibles para asignar.")

    # 2. Obtener el ID del último ejecutivo asignado
    config, created = ConfiguracionAsignacion.objects.get_or_create(
        clave='last_ejecutivo_id', 
        defaults={'valor': 0} # 0 si es la primera vez
    )
    last_id = config.valor
    
    # 3. Buscar el siguiente ejecutivo en la secuencia (ID > last_id)
    next_ejecutivo = ejecutivos_activos.filter(id__gt=last_id).first()
    
    # 4. Si no se encuentra (llegamos al final de la lista), volvemos al inicio
    if not next_ejecutivo:
        next_ejecutivo = ejecutivos_activos.first()
        
    # 5. Actualizar la configuración con el ID del ejecutivo elegido
    config.valor = next_ejecutivo.id
    config.save()
    
    return next_ejecutivo


# -----------------------------------------------------------------
# -- Vista: Nueva Solicitud
# -----------------------------------------------------------------
@permission_required('portal_retenciones.can_create_solicitud') 
def nueva_solicitud_view(request):
    
    # -- Lógica POST (Guardar formulario)
    if request.method == 'POST':
        
        try:
            with transaction.atomic():
                
                # -- Obtener datos del formulario
                cliente_id = request.POST.get('cliente_id')
                circuitos_ids_seleccionados = request.POST.getlist('circuitos_seleccionados')
                observaciones = request.POST.get('observaciones')
                fecha_solicitud_baja = request.POST.get('fecha_solicitud_baja')

                # -- Validaciones
                if not cliente_id:
                    raise Exception("Cliente no seleccionado. Por favor, búscalo y selecciónalo de la lista.")
                
                if not circuitos_ids_seleccionados:
                    raise Exception("Debes seleccionar al menos un circuito para la solicitud.")
                
                if not fecha_solicitud_baja:
                     raise Exception("Debe seleccionar una Fecha de Solicitud de Baja.")

                # -- Obtener instancias de Modelos
                cliente = Cliente.objects.get(id=cliente_id)
                estado_inicial = EstadoAtencion.objects.get(nombre_estado='Registrado')
                nivel_inicial = NivelAprobacion.objects.get(orden=1)
                
                # -- Asignación Round-Robin
                ejecutivo_asignado = get_next_ejecutivo()
                
                # -- Asignación Aleatoria de Analista
                analistas_disponibles = list(AnalistaRetencion.objects.filter(activo=True))
                if not analistas_disponibles:
                    raise Exception("No hay analistas activos disponibles para asignar.")
                analista_asignado = random.choice(analistas_disponibles)

                # -- Crear la Solicitud
                nueva_solicitud = Solicitud.objects.create(
                    cliente=cliente,
                    ejecutivo=ejecutivo_asignado,
                    analista=analista_asignado,
                    estado_actual=estado_inicial,
                    nivel_aprobacion=nivel_inicial,
                    descripcion=observaciones,
                    fecha_solicitud_baja=fecha_solicitud_baja,
                    asignado_automaticamente=True,
                    usuario_creador=request.user
                )
                
                # -- Vincular los Circuitos seleccionados
                nueva_solicitud.circuitos.set(circuitos_ids_seleccionados)
                
                # -- Mensaje de éxito
                messages.success(request, 
                    f'¡Solicitud SOL-{nueva_solicitud.id} creada y asignada a {ejecutivo_asignado.nombre}!'
                )
                
                # -- Redirigir a la lista
                return redirect('lista_solicitudes')

        # -- Manejo de Errores
        except (Cliente.DoesNotExist, EstadoAtencion.DoesNotExist, NivelAprobacion.DoesNotExist):
            contexto_error = {'error_formulario': 'Error de configuración. Faltan catálogos. (Correr seed_db)'}
            return render(request, 'nueva_solicitud.html', contexto_error)
        
        except Exception as e:
            contexto_error = {'error_formulario': str(e)}
            return render(request, 'nueva_solicitud.html', contexto_error)

    # -- Lógica GET (Mostrar formulario vacío)
    return render(request, 'nueva_solicitud.html')


# -----------------------------------------------------------------
# -- Vista: Lista de Solicitudes (FILTRADO POR ROL)
# -----------------------------------------------------------------
@permission_required('portal_retenciones.can_view_solicitud_list') 
def lista_solicitudes_view(request):
    
    # -- Query base: Obtenemos todas las solicitudes
    solicitudes_query = Solicitud.objects.all()
    
    # -- Lógica de Filtrado por Rol
    if not request.user.is_superuser:
        
        # 1. Identificadores de Rol
        is_ejecutivo_comercial = request.user.groups.filter(name='Ejecutivo Comercial').exists()
        is_ejecutivo_retencion = request.user.groups.filter(name='Ejecutivo Retencion').exists()
        
        # -- FILTRO 1: Ejecutivo Comercial (Ve solo las que creó)
        if is_ejecutivo_comercial:
            solicitudes_query = solicitudes_query.filter(usuario_creador=request.user)
            
        # -- FILTRO 2: Ejecutivo de Retención (Ve solo las que le asignaron)
        elif is_ejecutivo_retencion:
            try:
                # BUSCAMOS AL EJECUTIVO POR SU ID (Sincronizado con auth_user.id)
                ejecutivo_logueado = EjecutivoRetencion.objects.get(id=request.user.id) 
                
                # Filtramos las solicitudes donde este ejecutivo es el asignado
                solicitudes_query = solicitudes_query.filter(ejecutivo=ejecutivo_logueado)
                
            except EjecutivoRetencion.DoesNotExist:
                # Si el ID no coincide con un Ejecutivo, muestra la advertencia.
                solicitudes_query = Solicitud.objects.none()
                messages.warning(request, "Usted tiene el rol de Ejecutivo de Retención pero su ID de usuario no está registrado en la tabla de personal.")
        
    # -- Aplicar orden y pasar al template
    solicitudes = solicitudes_query.order_by('-fecha_creacion')
    
    context = {
        'solicitudes': solicitudes,
    }
    
    return render(request, 'lista_solicitudes.html', context)


# -----------------------------------------------------------------
# -- Vista: Detalle de Solicitud (NUEVA FUNCIÓN Y LÓGICA)
# -----------------------------------------------------------------
@permission_required('portal_retenciones.can_view_solicitud_list')
def solicitud_detalle_view(request, solicitud_id):
    
    # 1. Obtenemos la solicitud específica
    try:
        solicitud = Solicitud.objects.get(id=solicitud_id)
    except Solicitud.DoesNotExist:
        raise Http404("Solicitud no encontrada.")

    # 2. Lógica de CAMBIO DE ESTADO A 'EN ANÁLISIS' (En Proceso)
    # Solo cambiamos si el estado actual es 'Registrado'
    if solicitud.estado_actual.nombre_estado == 'Registrado':
        
        try:
            with transaction.atomic():
                # Obtenemos el nuevo estado
                nuevo_estado = EstadoAtencion.objects.get(nombre_estado='En Análisis') 
                
                # Guardamos el historial del cambio (Auditoría)
                HistorialEstado.objects.create(
                    solicitud=solicitud,
                    estado_anterior=solicitud.estado_actual,
                    estado_nuevo=nuevo_estado,
                    fecha_cambio=timezone.now(),
                    usuario_cambio=request.user.username 
                )
                
                # Actualizamos la solicitud
                solicitud.estado_actual = nuevo_estado
                solicitud.save()
                
                messages.info(request, f"El estado de la Solicitud SOL-{solicitud_id} ha sido actualizado a 'En Análisis' (En Proceso).")
                
        except EstadoAtencion.DoesNotExist:
             messages.error(request, "Error de configuración: El estado 'En Análisis' no existe en la base de datos. Ejecute la migración de datos iniciales.")
        except Exception as e:
             messages.error(request, f"Error al cambiar el estado: {str(e)}")


    # 3. Obtenemos todos los datos para el template
    context = {
        'solicitud': solicitud,
        'circuitos_asociados': solicitud.circuitos.all(), 
        'comentarios': solicitud.comentario_set.all().order_by('fecha_comentario'),
        'historial_estado': HistorialEstado.objects.filter(solicitud=solicitud).order_by('-fecha_cambio')
    }
    
    return render(request, 'solicitud_detalle.html', context)


# -----------------------------------------------------------------
# -- Vista: Personal
# -----------------------------------------------------------------
@permission_required('portal_retenciones.can_view_personal')
def personal_view(request):
    
    # -- Obtenemos el personal activo
    ejecutivos_activos = EjecutivoRetencion.objects.filter(activo=True)
    analistas_activos = AnalistaRetencion.objects.filter(activo=True)
    
    context = {
        'ejecutivos_activos': ejecutivos_activos,
        'analistas_activos': analistas_activos
    }
    
    return render(request, 'personal.html', context)


# -----------------------------------------------------------------
# -- Vista: Gestión de Personal
# -----------------------------------------------------------------
@permission_required('portal_retenciones.can_manage_personnel') 
def gestion_personal_view(request):
    
    # -- Lógica POST: Asignar/Retirar Roles
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action') 
        
        try:
            user_to_modify = User.objects.get(id=user_id)
            
            # --- Generación de clave de email y nombre para los modelos de personal ---
            user_key = _get_user_key(user_to_modify)
            user_name = user_to_modify.get_full_name() or user_to_modify.username
            # --------------------------------------------------------------------------
            
            if action == 'assign_ejecutivo':
                EjecutivoRetencion.objects.get_or_create(
                    id=user_id, # Usamos el ID del usuario como clave primaria del Ejecutivo
                    defaults={'nombre': user_name, 'email': user_key}
                )
                messages.success(request, f'{user_name} asignado como Ejecutivo de Retención.')
            elif action == 'remove_ejecutivo':
                EjecutivoRetencion.objects.filter(id=user_id).delete()
                messages.success(request, f'{user_name} removido de Ejecutivo de Retención.')
            elif action == 'assign_analista':
                AnalistaRetencion.objects.get_or_create(
                    id=user_id, # Usamos el ID del usuario como clave primaria del Analista
                    defaults={'nombre': user_name, 'email': user_key}
                )
                messages.success(request, f'{user_name} asignado como Analista de Retención.')
            elif action == 'remove_analista':
                AnalistaRetencion.objects.filter(id=user_id).delete()
                messages.success(request, f'{user_name} removido de Analista de Retención.')
            
            return redirect('gestion_personal')
            
        except User.DoesNotExist:
            messages.error(request, 'Error: Usuario no encontrado.')
        except IntegrityError:
             messages.error(request, 'Error de integridad: El ID ya existe. Revise la base de datos.')
        except Exception as e:
            messages.error(request, f'Error al modificar el rol: {str(e)}')
            
    # -- Lógica GET: Mostrar tabla de usuarios
    
    usuarios = User.objects.all().order_by('username')
    
    # Obtenemos los IDs de los usuarios ya asignados a roles
    ejecutivos_ids = EjecutivoRetencion.objects.values_list('id', flat=True)
    analistas_ids = AnalistaRetencion.objects.values_list('id', flat=True)
    
    # Construimos la lista de usuarios con sus roles
    usuarios_con_roles = []
    for user in usuarios:
        
        usuarios_con_roles.append({
            'user': user,
            'is_ejecutivo': user.id in ejecutivos_ids,
            'is_analista': user.id in analistas_ids,
        })
    
    context = {
        'usuarios_con_roles': usuarios_con_roles
    }
    
    return render(request, 'gestion_personal.html', context)


# -----------------------------------------------------------------
# -- Vista: Perfil
# -----------------------------------------------------------------
@login_required
def perfil_view(request):
    return render(request, 'perfil.html')