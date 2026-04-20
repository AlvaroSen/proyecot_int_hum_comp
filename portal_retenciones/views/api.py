import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from ..models import Cliente, Circuito

logger = logging.getLogger(__name__)


@login_required
def search_clientes(request):
    # -- Busca por parámetro 'q' en la URL
    query = request.GET.get('q', None)
    clientes_filtrados = []
    
    if query:
        # -- Filtra por razón social (icontains) y limita a 10
        clientes = Cliente.objects.filter(razon_social__icontains=query)[:10] 
        
        for cliente in clientes:
            clientes_filtrados.append({
                'id': cliente.id,
                'nombre': cliente.razon_social,
                'ruc': cliente.ruc
            })
            
    return JsonResponse({'clientes': clientes_filtrados})


# -- API: Obtener circuitos de un cliente específico
@login_required
def get_circuitos_por_cliente(request, cliente_id):
    try:
        circuitos = Circuito.objects.filter(cliente_id=cliente_id).select_related('tipo_servicio')
        circuitos_data = [
            {
                'id': c.id,
                'nombre_circuito': c.nombre_circuito,
                'tipo_servicio': c.tipo_servicio.nombre if c.tipo_servicio_id else None,
                'renta_mensual': c.renta_mensual,
            }
            for c in circuitos
        ]
        return JsonResponse({'circuitos': circuitos_data})
    except Exception:
        logger.exception("Error listando circuitos para cliente_id=%s", cliente_id)
        return JsonResponse({'error': 'No se pudieron obtener los circuitos'}, status=500)