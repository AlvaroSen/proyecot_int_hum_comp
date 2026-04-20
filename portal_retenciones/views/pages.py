# En: portal_retenciones/views/pages.py

import csv
import logging

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from portal_retenciones.decorators import permission_required

# Importamos los modelos necesarios
from portal_retenciones.models import (
    Cliente,
    Solicitud,
    EjecutivoRetencion,
    AnalistaRetencion,
    Comentario,
    HistorialEstado,
    EstadoAtencion,
    NivelAprobacion,
    ConfiguracionAsignacion,
    SolicitudCircuito,
    TipoCaso,
    Veredicto,
    RegistroAsignacion,
    RolAsignacion,
    Circuito,
    MotivoAusencia,
)
from portal_retenciones import asignacion as asig

logger = logging.getLogger(__name__)


def _asignar_ejecutivo_round_robin_legacy():
    """DEPRECATED: usa portal_retenciones.asignacion.asignar en su lugar."""
    activos = list(
        EjecutivoRetencion.objects
        .filter(activo=True, disponible_asignacion=True)
        .order_by("id")
    )
    if not activos:
        return None

    config, _ = ConfiguracionAsignacion.objects.get_or_create(
        clave="last_ejecutivo_id",
        defaults={"valor": "0"},
    )
    last_id = int(config.valor or 0)
    siguientes = [e for e in activos if e.id > last_id]
    ejecutivo = siguientes[0] if siguientes else activos[0]
    config.valor = str(ejecutivo.id)
    config.save()
    return ejecutivo

# --- VISTAS DE PÁGINA EXISTENTES ---

@permission_required('portal_retenciones.can_create_solicitud')
def nueva_solicitud_view(request):
    """Muestra y procesa el formulario para crear una nueva solicitud."""
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        circuitos_ids = request.POST.getlist('circuitos_seleccionados')
        observaciones = (request.POST.get('observaciones') or '').strip() or None
        fecha_baja = request.POST.get('fecha_solicitud_baja') or None
        tipo_caso_id = request.POST.get('tipo_caso')

        try:
            if not cliente_id:
                raise ValidationError('Debes seleccionar un cliente.')
            if not circuitos_ids:
                raise ValidationError('Debes seleccionar al menos un circuito.')
            tipo_caso_obj = TipoCaso.objects.filter(id=tipo_caso_id, activo=True).first()
            if not tipo_caso_obj:
                raise ValidationError('Debes seleccionar un tipo de caso válido.')

            estado_nuevo = EstadoAtencion.objects.filter(codigo='NUEVO').first()
            if not estado_nuevo:
                raise ValidationError('No se encontró el estado inicial "NUEVO".')

            nivel = NivelAprobacion.objects.order_by('orden').first()
            if not nivel:
                raise ValidationError('No hay niveles de aprobación configurados.')

            # Calcular renta total para evaluar tope de carga en las estrategias.
            renta_total = (
                Circuito.objects.filter(id__in=circuitos_ids)
                .aggregate(total=Sum('renta_mensual'))['total']
                or 0
            )
            contexto = asig.SolicitudContexto(
                cliente_id=int(cliente_id),
                renta_total=renta_total,
                tipo_caso=tipo_caso_obj.codigo,
            )

            ejecutivo, detalle_ejec = asig.asignar(RolAsignacion.EJECUTIVO, contexto)
            if not ejecutivo:
                raise ValidationError(
                    'No hay ejecutivos activos disponibles para asignación. '
                    + detalle_ejec.get('razon', '')
                )

            analista, detalle_anal = asig.asignar(RolAsignacion.ANALISTA, contexto)
            if not analista:
                raise ValidationError(
                    'No hay analistas activos disponibles. '
                    + detalle_anal.get('razon', '')
                )

            with transaction.atomic():
                solicitud = Solicitud.objects.create(
                    cliente_id=cliente_id,
                    ejecutivo=ejecutivo,
                    analista=analista,
                    estado_actual=estado_nuevo,
                    nivel_aprobacion=nivel,
                    descripcion=observaciones,
                    fecha_solicitud_baja=fecha_baja,
                    tipo_caso=tipo_caso_obj,
                    asignado_automaticamente=True,
                    usuario_creador=request.user,
                )
                for cid in circuitos_ids:
                    SolicitudCircuito.objects.create(solicitud=solicitud, circuito_id=cid)
                RegistroAsignacion.objects.create(
                    solicitud=solicitud,
                    rol=RolAsignacion.EJECUTIVO,
                    estrategia=detalle_ejec.get('estrategia', ''),
                    persona_asignada_id=ejecutivo.id,
                    persona_asignada_nombre=ejecutivo.nombre,
                    detalle=detalle_ejec,
                    ejecutado_por=request.user,
                )
                RegistroAsignacion.objects.create(
                    solicitud=solicitud,
                    rol=RolAsignacion.ANALISTA,
                    estrategia=detalle_anal.get('estrategia', ''),
                    persona_asignada_id=analista.id,
                    persona_asignada_nombre=analista.nombre,
                    detalle=detalle_anal,
                    ejecutado_por=request.user,
                )

            messages.success(
                request,
                f'Solicitud #{solicitud.id} creada. Ejecutivo: {ejecutivo.nombre} · Analista: {analista.nombre}.',
            )
            return redirect('solicitud_detalle', solicitud_id=solicitud.id)

        except ValidationError as e:
            mensaje = '; '.join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f'No se pudo crear la solicitud: {mensaje}')
        except Exception:
            logger.exception('Error inesperado creando solicitud')
            messages.error(request, 'Error interno al crear la solicitud. Revisa los logs.')

    return render(request, 'nueva_solicitud.html', {
        'tipos_caso': TipoCaso.objects.filter(activo=True),
    })

COLUMNAS_ORDENABLES = {
    'id': 'id',
    'cliente': 'cliente__razon_social',
    'estado': 'estado_actual__nombre_estado',
    'ejecutivo': 'ejecutivo__nombre',
    'fecha_creacion': 'fecha_creacion',
    'tipo_caso': 'tipo_caso__codigo',
    'veredicto': 'veredicto',
}


@permission_required('portal_retenciones.can_view_solicitud_list')
def lista_solicitudes_view(request):
    """Lista de solicitudes con filtros, KPIs, paginación y export CSV."""
    q = (request.GET.get('q') or '').strip()
    estado_id = request.GET.get('estado') or ''
    tipo_caso = request.GET.get('tipo_caso') or ''
    veredicto = request.GET.get('veredicto') or ''
    ejecutivo_id = request.GET.get('ejecutivo') or ''
    fecha_desde = request.GET.get('fecha_desde') or ''
    fecha_hasta = request.GET.get('fecha_hasta') or ''
    ordenar = request.GET.get('ordenar') or '-fecha_creacion'

    qs = (
        Solicitud.objects
        .select_related('cliente', 'estado_actual', 'ejecutivo', 'analista', 'usuario_creador', 'tipo_caso')
        .annotate(
            num_circuitos=Count('circuitos', distinct=True),
            renta_total=Sum('circuitos__renta_mensual'),
        )
    )

    if q:
        qs = qs.filter(
            Q(cliente__razon_social__icontains=q)
            | Q(cliente__ruc__icontains=q)
            | Q(id__iexact=q.lstrip('SOLsol- '))
        )
    if estado_id:
        qs = qs.filter(estado_actual_id=estado_id)
    if tipo_caso:
        qs = qs.filter(tipo_caso__codigo=tipo_caso)
    if veredicto:
        qs = qs.filter(veredicto=veredicto)
    if ejecutivo_id:
        qs = qs.filter(ejecutivo_id=ejecutivo_id)
    if fecha_desde:
        qs = qs.filter(fecha_creacion__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_creacion__date__lte=fecha_hasta)

    # Ordenamiento seguro (solo columnas permitidas).
    columna_sort = ordenar.lstrip('-')
    if columna_sort in COLUMNAS_ORDENABLES:
        prefijo = '-' if ordenar.startswith('-') else ''
        qs = qs.order_by(prefijo + COLUMNAS_ORDENABLES[columna_sort])
    else:
        qs = qs.order_by('-fecha_creacion')

    # KPIs sobre el queryset filtrado.
    total_filtrado = qs.count()
    abiertas = qs.filter(veredicto=Veredicto.PENDIENTE).count()
    cerradas_qs = qs.exclude(veredicto=Veredicto.PENDIENTE)
    cerradas = cerradas_qs.count()
    retenidas = cerradas_qs.filter(veredicto=Veredicto.RETENIDO).count()
    tasa_retencion = round(retenidas / cerradas * 100, 1) if cerradas else 0

    sla_horas = getattr(settings, 'SOLICITUD_SLA_HORAS', 72)
    cerradas_dentro_sla = sum(1 for s in cerradas_qs if s.cumple_sla)
    sla_porcentaje = round(cerradas_dentro_sla / cerradas * 100, 1) if cerradas else 0

    # Export CSV (sin paginar).
    if request.GET.get('export') == 'csv':
        return _export_solicitudes_csv(qs)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page'))

    # Preservar querystring al paginar/ordenar.
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring.pop('ordenar', None)

    context = {
        'solicitudes': page.object_list,
        'page_obj': page,
        'paginator': paginator,
        'total_filtrado': total_filtrado,
        'kpis': {
            'abiertas': abiertas,
            'cerradas': cerradas,
            'tasa_retencion': tasa_retencion,
            'sla_porcentaje': sla_porcentaje,
            'sla_horas': sla_horas,
        },
        'filtros': {
            'q': q,
            'estado': estado_id,
            'tipo_caso': tipo_caso,
            'veredicto': veredicto,
            'ejecutivo': ejecutivo_id,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
        },
        'ordenar_actual': ordenar,
        'querystring_base': querystring.urlencode(),
        'estados_disponibles': EstadoAtencion.objects.order_by('nombre_estado'),
        'ejecutivos_disponibles': EjecutivoRetencion.objects.filter(activo=True).order_by('nombre'),
        'tipos_caso': TipoCaso.objects.filter(activo=True),
        'veredicto_choices': Veredicto.choices,
    }
    return render(request, 'lista_solicitudes.html', context)


def _export_solicitudes_csv(qs):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="solicitudes_{timezone.now():%Y%m%d_%H%M}.csv"'
    )
    # BOM para que Excel lo abra en UTF-8.
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Tipo Caso', 'Cliente', 'RUC', 'Estado', 'Veredicto',
        'Ejecutivo', 'Analista', 'Fecha Creación', 'Fecha Cierre',
        'TMG (horas)', 'Cumple SLA', '# Circuitos', 'Renta Total (S/)',
        'Usuario Creador',
    ])
    for s in qs:
        tmg_horas = ''
        if s.tiempo_gestion is not None:
            tmg_horas = round(s.tiempo_gestion.total_seconds() / 3600, 2)
        cumple_sla = ''
        if s.cumple_sla is not None:
            cumple_sla = 'Sí' if s.cumple_sla else 'No'
        writer.writerow([
            f'SOL-{s.id}',
            s.tipo_caso.nombre if s.tipo_caso_id else '',
            s.cliente.razon_social,
            s.cliente.ruc,
            s.estado_actual.nombre_estado,
            s.get_veredicto_display(),
            s.ejecutivo.nombre,
            s.analista.nombre,
            s.fecha_creacion.strftime('%Y-%m-%d %H:%M'),
            s.fecha_cierre.strftime('%Y-%m-%d %H:%M') if s.fecha_cierre else '',
            tmg_horas,
            cumple_sla,
            s.num_circuitos,
            f'{s.renta_total:.2f}' if s.renta_total is not None else '0.00',
            s.usuario_creador.get_username() if s.usuario_creador else '',
        ])
    return response

@permission_required('portal_retenciones.can_view_personal')
def personal_view(request):
    """Directorio de personal para quien registra casos.

    Vista read-only enfocada en disponibilidad. Sin datos operativos (carga,
    renta, tope) — eso es responsabilidad del analista en /gestion-personal/.
    """
    ejecutivos = EjecutivoRetencion.objects.all().order_by(
        '-activo', '-disponible_asignacion', 'nombre'
    )
    analistas = AnalistaRetencion.objects.all().order_by(
        '-activo', '-disponible_asignacion', 'nombre'
    )

    def _conteo(qs):
        total = qs.count()
        activos = qs.filter(activo=True).count()
        disponibles = qs.filter(activo=True, disponible_asignacion=True).count()
        return {'total': total, 'activos': activos, 'disponibles': disponibles}

    context = {
        'ejecutivos': ejecutivos,
        'analistas': analistas,
        'totales': {
            'ejecutivos': _conteo(EjecutivoRetencion.objects.all()),
            'analistas': _conteo(AnalistaRetencion.objects.all()),
        },
    }
    return render(request, 'personal.html', context)

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

    # Registros de auditoría de la asignación (ejecutivo + analista)
    registros_asignacion = solicitud.registros_asignacion.all()

    context = {
        'solicitud': solicitud,
        'circuitos_asociados': circuitos_asociados,
        'comentarios': comentarios,
        'historial_estado': historial_estado,
        'estados_disponibles': estados_disponibles,
        'registros_asignacion': registros_asignacion,
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
                usuario=request.user,
                comentario=comentario_texto
            )
            messages.success(request, 'Comentario agregado exitosamente.')
        else:
            messages.warning(request, 'El comentario no puede estar vacío.')
    
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
                        usuario_cambio=request.user
                    )
                    
                    # Actualizar el estado actual de la solicitud
                    solicitud.estado_actual = nuevo_estado
                    solicitud.save()
                    
                    messages.success(request, f'Estado cambiado a: {nuevo_estado.nombre_estado}')
                else:
                    messages.info(request, 'El estado seleccionado es el mismo que el actual.')
                    
            except EstadoAtencion.DoesNotExist:
                messages.error(request, 'Estado no válido.')
        else:
            messages.warning(request, 'Debe seleccionar un estado.')
    
    # Redirigir de vuelta a la página de detalle
    return redirect('solicitud_detalle', solicitud_id=solicitud_id)


@login_required
def gestion_personal_view(request):
    """Configura estrategias y parámetros de asignación por rol.

    Acceso:
      - Ejecutivos: solo quienes tengan `can_configure_asignacion_ejecutivos` (grupo Analistas + superusers).
      - Analistas: solo quienes tengan `can_configure_asignacion_analistas` (superusers).
    """
    puede_ejecutivos = request.user.has_perm('portal_retenciones.can_configure_asignacion_ejecutivos')
    puede_analistas = request.user.has_perm('portal_retenciones.can_configure_asignacion_analistas')

    if not (puede_ejecutivos or puede_analistas):
        messages.error(request, 'No tienes permisos para configurar la asignación.')
        return redirect('menu')

    if request.method == 'POST':
        rol_form = request.POST.get('rol')
        if rol_form == RolAsignacion.EJECUTIVO and not puede_ejecutivos:
            messages.error(request, 'No puedes configurar la estrategia de ejecutivos.')
            return redirect('gestion_personal')
        if rol_form == RolAsignacion.ANALISTA and not puede_analistas:
            messages.error(request, 'No puedes configurar la estrategia de analistas.')
            return redirect('gestion_personal')

        try:
            with transaction.atomic():
                # Actualizar estrategia activa.
                nueva_estrategia = request.POST.get('estrategia')
                if nueva_estrategia not in dict(asig.EstrategiaAsignacion.choices):
                    raise ValidationError('Estrategia inválida.')
                clave_estrategia = (
                    'estrategia_ejecutivo' if rol_form == RolAsignacion.EJECUTIVO
                    else 'estrategia_analista'
                )
                asig.set_parametro(clave_estrategia, nueva_estrategia)

                # Actualizar parámetros por persona.
                Modelo = EjecutivoRetencion if rol_form == RolAsignacion.EJECUTIVO else AnalistaRetencion
                for persona in Modelo.objects.all():
                    prefix = f'{rol_form.lower()}_{persona.id}'
                    peso = request.POST.get(f'{prefix}_peso')
                    tope = request.POST.get(f'{prefix}_tope')
                    activo = request.POST.get(f'{prefix}_activo') == 'on'
                    disponible = request.POST.get(f'{prefix}_disponible') == 'on'

                    motivo_id = request.POST.get(f'{prefix}_motivo') or None

                    if peso is not None:
                        persona.peso_asignacion = max(0, int(peso or 0))
                    persona.max_carga_renta = float(tope) if tope else None
                    persona.activo = activo
                    persona.disponible_asignacion = disponible
                    # Si está disponible, no tiene sentido guardar motivo.
                    persona.motivo_no_disponible_id = None if disponible or not motivo_id else int(motivo_id)
                    persona.save()

            messages.success(request, f'Configuración de {rol_form.lower()}s actualizada correctamente.')
            return redirect('gestion_personal')
        except (ValidationError, ValueError) as e:
            mensaje = '; '.join(e.messages) if hasattr(e, 'messages') else str(e)
            messages.error(request, f'No se pudo guardar: {mensaje}')
        except Exception:
            logger.exception('Error guardando configuración de asignación')
            messages.error(request, 'Error interno al guardar la configuración.')

    # Datos para render.
    estrategia_ejecutivo_actual = asig.obtener_estrategia_activa(RolAsignacion.EJECUTIVO)
    estrategia_analista_actual = asig.obtener_estrategia_activa(RolAsignacion.ANALISTA)

    contexto_preview = asig.SolicitudContexto(cliente_id=0, renta_total=0, tipo_caso='RETENCION')
    preview_ejec, _ = asig.previsualizar(RolAsignacion.EJECUTIVO, contexto_preview)
    preview_anal, _ = asig.previsualizar(RolAsignacion.ANALISTA, contexto_preview)

    estrategias = [
        {
            'codigo': cod,
            'label': label,
            'descripcion': asig.ESTRATEGIA_DESCRIPCIONES.get(cod, ''),
        }
        for cod, label in asig.EstrategiaAsignacion.choices
    ]

    context = {
        'puede_ejecutivos': puede_ejecutivos,
        'puede_analistas': puede_analistas,
        'estrategias': estrategias,
        'estrategia_ejecutivo_actual': estrategia_ejecutivo_actual,
        'estrategia_analista_actual': estrategia_analista_actual,
        'ejecutivos': EjecutivoRetencion.objects.all().select_related('motivo_no_disponible').order_by('nombre'),
        'analistas': AnalistaRetencion.objects.all().select_related('motivo_no_disponible').order_by('nombre'),
        'preview_ejec': preview_ejec,
        'preview_anal': preview_anal,
        'motivos': MotivoAusencia.objects.filter(activo=True),
    }
    return render(request, 'gestion_personal.html', context)

@login_required
def perfil_view(request):
    """Muestra la información de perfil del usuario logeado."""
    return render(request, 'perfil.html', {})


# --- VISTA DE DASHBOARD ---
@login_required
@permission_required('portal_retenciones.can_view_menu')
def dashboard_view(request):
    """Dashboard de retenciones con KPIs de negocio, alertas y gráficos accionables.

    El filtro `periodo` (GET) recalcula todas las métricas sobre una ventana de tiempo.
    Las queries usan FKs/flags (veredicto, estado_actual.es_final, tipo_caso FK) en vez
    de strings hardcodeados, así que los nombres de estados pueden cambiar sin romper
    el dashboard.
    """
    from datetime import timedelta
    import json

    periodo = request.GET.get('periodo', '90')  # default: 90 días
    desde = None
    if periodo != 'all':
        try:
            desde = timezone.now() - timedelta(days=int(periodo))
        except ValueError:
            desde = timezone.now() - timedelta(days=90)
            periodo = '90'

    qs = Solicitud.objects.all()
    if desde:
        qs = qs.filter(fecha_creacion__gte=desde)

    # === KPIs de negocio ================================================
    total_solicitudes = qs.count()
    abiertas_qs = qs.filter(veredicto=Veredicto.PENDIENTE)
    cerradas_qs = qs.exclude(veredicto=Veredicto.PENDIENTE)
    abiertas = abiertas_qs.count()
    cerradas = cerradas_qs.count()
    retenidas = cerradas_qs.filter(veredicto=Veredicto.RETENIDO).count()

    tasa_retencion = round(retenidas / cerradas * 100, 1) if cerradas else 0

    sla_horas = getattr(settings, 'SOLICITUD_SLA_HORAS', 72)
    sla_segundos = sla_horas * 3600

    cerradas_con_cierre = list(cerradas_qs.filter(fecha_cierre__isnull=False))
    tmg_horas = 0.0
    ns = 0
    if cerradas_con_cierre:
        duraciones = [(s.fecha_cierre - s.fecha_creacion).total_seconds() for s in cerradas_con_cierre]
        tmg_horas = round(sum(duraciones) / len(duraciones) / 3600, 1)
        ns = round(sum(1 for d in duraciones if d <= sla_segundos) / len(duraciones) * 100, 1)

    con_primera_respuesta = qs.filter(comentarios__isnull=False).distinct().count()
    na = round(con_primera_respuesta / total_solicitudes * 100, 1) if total_solicitudes else 0

    total_clientes = Cliente.objects.count()

    # === Alertas ========================================================
    ahora = timezone.now()
    casos_fuera_sla = sum(
        1 for s in abiertas_qs.only('fecha_creacion')
        if (ahora - s.fecha_creacion).total_seconds() > sla_segundos
    )
    casos_viejos = abiertas_qs.filter(fecha_creacion__lt=ahora - timedelta(days=7)).count()

    # === Gráficos ======================================================
    veredicto_display = dict(Veredicto.choices)
    veredictos_data = qs.values('veredicto').annotate(cantidad=Count('id')).order_by('-cantidad')
    veredictos_labels = [veredicto_display.get(v['veredicto'], v['veredicto']) for v in veredictos_data]
    veredictos_valores = [v['cantidad'] for v in veredictos_data]

    estados_data = (
        qs.values('estado_actual__nombre_estado', 'estado_actual__es_final')
        .annotate(cantidad=Count('id')).order_by('-cantidad')
    )
    estados_labels = [e['estado_actual__nombre_estado'] for e in estados_data]
    estados_valores = [e['cantidad'] for e in estados_data]

    motivos_data = (
        cerradas_qs.filter(veredicto=Veredicto.NO_RETENIDO, motivo_cierre__isnull=False)
        .values('motivo_cierre__descripcion')
        .annotate(cantidad=Count('id'))
        .order_by('-cantidad')[:5]
    )
    motivos_labels = [m['motivo_cierre__descripcion'] for m in motivos_data]
    motivos_valores = [m['cantidad'] for m in motivos_data]

    ejecutivos_perf = []
    for e in EjecutivoRetencion.objects.filter(activo=True):
        e_cerradas = cerradas_qs.filter(ejecutivo=e)
        total_e = e_cerradas.count()
        if total_e > 0:
            retenidas_e = e_cerradas.filter(veredicto=Veredicto.RETENIDO).count()
            ejecutivos_perf.append({
                'nombre': e.nombre,
                'tasa': round(retenidas_e / total_e * 100, 1),
                'total': total_e,
            })
    ejecutivos_perf.sort(key=lambda x: -x['tasa'])
    ejec_perf_labels = [e['nombre'] for e in ejecutivos_perf[:5]]
    ejec_perf_valores = [e['tasa'] for e in ejecutivos_perf[:5]]

    # Tendencia últimos 6 meses (independiente del filtro periodo).
    fecha_inicio_tend = ahora - timedelta(days=180)
    tend_data = (
        Solicitud.objects.filter(fecha_creacion__gte=fecha_inicio_tend)
        .extra(select={'mes': "strftime('%%Y-%%m', fecha_creacion)"})
        .values('mes').annotate(cantidad=Count('id'))
        .order_by('mes')
    )
    meses_labels = [t['mes'] for t in tend_data]
    meses_valores = [t['cantidad'] for t in tend_data]

    tipos_data = qs.values('tipo_caso__nombre').annotate(cantidad=Count('id')).order_by('-cantidad')
    tipos_labels = [t['tipo_caso__nombre'] for t in tipos_data]
    tipos_valores = [t['cantidad'] for t in tipos_data]

    context = {
        'periodo': periodo,
        'periodo_opciones': [
            ('30', 'Últimos 30 días'),
            ('90', 'Últimos 90 días'),
            ('180', 'Últimos 6 meses'),
            ('365', 'Últimos 12 meses'),
            ('all', 'Todo el histórico'),
        ],
        # KPIs de negocio
        'tasa_retencion': tasa_retencion,
        'tmg_horas': tmg_horas,
        'ns': ns,
        'na': na,
        'sla_horas': sla_horas,
        # Volumen
        'total_clientes': total_clientes,
        'total_solicitudes': total_solicitudes,
        'solicitudes_abiertas': abiertas,
        'solicitudes_cerradas': cerradas,
        # Alertas
        'casos_fuera_sla': casos_fuera_sla,
        'casos_viejos': casos_viejos,
        # Charts (JSON)
        'veredictos_labels': json.dumps(veredictos_labels),
        'veredictos_valores': json.dumps(veredictos_valores),
        'estados_labels': json.dumps(estados_labels),
        'estados_valores': json.dumps(estados_valores),
        'motivos_labels': json.dumps(motivos_labels),
        'motivos_valores': json.dumps(motivos_valores),
        'ejec_perf_labels': json.dumps(ejec_perf_labels),
        'ejec_perf_valores': json.dumps(ejec_perf_valores),
        'meses_labels': json.dumps(meses_labels),
        'meses_valores': json.dumps(meses_valores),
        'tipos_labels': json.dumps(tipos_labels),
        'tipos_valores': json.dumps(tipos_valores),
    }

    return render(request, 'dashboard.html', context)