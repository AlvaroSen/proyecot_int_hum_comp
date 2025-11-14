# En: portal_retenciones/views/pages.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
import random

from ..models import (
    Cliente, 
    Circuito, 
    Solicitud, 
    EstadoAtencion, 
    NivelAprobacion, 
    EjecutivoRetencion, 
    AnalistaRetencion
)

# -- Vista: Nueva Solicitud
@login_required
def nueva_solicitud_view(request):
    
    # -- Lógica POST (Guardar formulario)
    if request.method == 'POST':
        
        try:
            with transaction.atomic():
                
                # -- Obtener datos del formulario
                cliente_id = request.POST.get('cliente_id')
                circuitos_ids_seleccionados = request.POST.getlist('circuitos_seleccionados')
                motivo = request.POST.get('motivo')
                observaciones = request.POST.get('observaciones')
                fecha_baja = request.POST.get('fecha')

                # -- Validaciones
                if not cliente_id:
                    raise Exception("Cliente no seleccionado. Por favor, búscalo y selecciónalo de la lista.")
                
                if not circuitos_ids_seleccionados:
                    raise Exception("Debes seleccionar al menos un circuito para la solicitud.")

                # -- Obtener instancias de Modelos
                cliente = Cliente.objects.get(id=cliente_id)
                estado_inicial = EstadoAtencion.objects.get(nombre_estado='Registrado')
                nivel_inicial = NivelAprobacion.objects.get(orden=1)
                
                # -- Asignación Aleatoria de personal
                ejecutivos_disponibles = list(EjecutivoRetencion.objects.filter(activo=True))
                analistas_disponibles = list(AnalistaRetencion.objects.filter(activo=True))
                
                if not ejecutivos_disponibles or not analistas_disponibles:
                    raise Exception("No hay personal activo disponible para asignar. (Correr seed_db)")

                ejecutivo_asignado = random.choice(ejecutivos_disponibles)
                analista_asignado = random.choice(analistas_disponibles)

                # -- Crear la Solicitud
                nueva_solicitud = Solicitud.objects.create(
                    cliente=cliente,
                    ejecutivo=ejecutivo_asignado,
                    analista=analista_asignado,
                    estado_actual=estado_inicial,
                    nivel_aprobacion=nivel_inicial,
                    descripcion=f"Motivo: {motivo}\nFecha Baja Solicitada: {fecha_baja}\n\nObservaciones:\n{observaciones}",
                    asignado_automaticamente=True
                )
                
                # -- Vincular los Circuitos seleccionados
                nueva_solicitud.circuitos.set(circuitos_ids_seleccionados)
                
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
# -- Vistas Placeholder
# -----------------------------------------------------------------

@login_required
def lista_solicitudes_view(request):
    # TODO: Mostrar la lista real de solicitudes
    return render(request, 'lista_solicitudes.html')


@login_required
def perfil_view(request):
    return render(request, 'perfil.html')