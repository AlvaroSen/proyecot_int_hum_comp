from django.http import JsonResponse
from ..models import Cliente, Circuito

# -- API: Búsqueda de clientes (autocomplete)
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
def get_circuitos_por_cliente(request, cliente_id):
    circuitos_data = []
    try:
        # -- Busca todos los circuitos asociados al cliente_id
        circuitos = Circuito.objects.filter(cliente_id=cliente_id)
        
        # -- Convierte los objetos a un formato JSON simple
        for circuito in circuitos:
            circuitos_data.append({
                'id': circuito.id,
                'nombre_circuito': circuito.nombre_circuito,
                'tipo_servicio': circuito.tipo_servicio,
                'renta_mensual': circuito.renta_mensual
            })
        
        return JsonResponse({'circuitos': circuitos_data})

    except Exception as e:
        # -- Manejo de errores
        return JsonResponse({'error': str(e)}, status=404)