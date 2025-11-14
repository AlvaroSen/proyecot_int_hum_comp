# En: portal_retenciones/views/pages.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction  # <-- ¡Importante para un guardado seguro!
import random

# Importamos todos los modelos que vamos a necesitar
from ..models import (
    Cliente, 
    Circuito, # <-- Necesitamos este modelo ahora
    Solicitud, 
    EstadoAtencion, 
    NivelAprobacion, 
    EjecutivoRetencion, 
    AnalistaRetencion
)

# --- Vista para la página "Nueva Solicitud" ---
@login_required
def nueva_solicitud_view(request):
    
    # --- LÓGICA POST: CUANDO EL USUARIO ENVÍA EL FORMULARIO ---
    if request.method == 'POST':
        
        # Usamos transaction.atomic para asegurar que todo se guarde
        # correctamente, o nada se guarde si hay un error.
        try:
            with transaction.atomic():
                
                # 1. Obtener datos del formulario HTML
                cliente_id = request.POST.get('cliente_id')
                
                # Usamos .getlist() para obtener TODOS los checkboxes seleccionados
                circuitos_ids_seleccionados = request.POST.getlist('circuitos_seleccionados')
                
                motivo = request.POST.get('motivo')
                observaciones = request.POST.get('observaciones')
                fecha_baja = request.POST.get('fecha')

                # 2. Validaciones
                if not cliente_id:
                    raise Exception("Cliente no seleccionado. Por favor, búscalo y selecciónalo de la lista.")
                
                if not circuitos_ids_seleccionados:
                    raise Exception("Debes seleccionar al menos un circuito para la solicitud.")

                # 3. Obtener el Cliente
                cliente = Cliente.objects.get(id=cliente_id)

                # 4. Obtener Catálogos para asignación (Igual que antes)
                estado_inicial = EstadoAtencion.objects.get(nombre_estado='Registrado')
                nivel_inicial = NivelAprobacion.objects.get(orden=1)
                
                # 5. Asignación Aleatoria (Igual que antes)
                ejecutivos_disponibles = list(EjecutivoRetencion.objects.filter(activo=True))
                analistas_disponibles = list(AnalistaRetencion.objects.filter(activo=True))
                
                if not ejecutivos_disponibles or not analistas_disponibles:
                    raise Exception("No hay ejecutivos o analistas activos disponibles para asignar. (Correr seed_db)")

                ejecutivo_asignado = random.choice(ejecutivos_disponibles)
                analista_asignado = random.choice(analistas_disponibles)

                # 6. Crear la Solicitud (Paso 1 de 2)
                nueva_solicitud = Solicitud.objects.create(
                    cliente=cliente,
                    ejecutivo=ejecutivo_asignado,
                    analista=analista_asignado,
                    estado_actual=estado_inicial,
                    nivel_aprobacion=nivel_inicial,
                    descripcion=f"Motivo: {motivo}\nFecha Baja Solicitada: {fecha_baja}\n\nObservaciones:\n{observaciones}",
                    asignado_automaticamente=True
                )
                
                # 7. Vincular los Circuitos (Paso 2 de 2)
                # El método .set() maneja la tabla intermedia SolicitudCircuito automáticamente.
                nueva_solicitud.circuitos.set(circuitos_ids_seleccionados)
                
                # 8. Redirigir a la lista (¡Éxito!)
                return redirect('lista_solicitudes')

        # --- Manejo de Errores ---
        except (Cliente.DoesNotExist, EstadoAtencion.DoesNotExist, NivelAprobacion.DoesNotExist):
            contexto_error = {'error_formulario': 'Error de configuración. Faltan catálogos. (Correr seed_db)'}
            return render(request, 'nueva_solicitud.html', contexto_error)
        
        except Exception as e:
            # Esto atrapará nuestros errores de validación (ej. "Debes seleccionar un circuito")
            contexto_error = {'error_formulario': str(e)}
            return render(request, 'nueva_solicitud.html', contexto_error)

    # --- LÓGICA GET: CUANDO EL USUARIO SOLO CARGA LA PÁGINA ---
    return render(request, 'nueva_solicitud.html')


# -----------------------------------------------------------------
# --- OTRAS VISTAS (AÚN SON PLACEHOLDERS) ---
# -----------------------------------------------------------------

@login_required
def lista_solicitudes_view(request):
    # TODO: Más adelante, aquí buscaremos las solicitudes en la BD
    return render(request, 'lista_solicitudes.html')


@login_required
def perfil_view(request):
    return render(request, 'perfil.html')