# En: portal_retenciones/views/api.py

from django.http import JsonResponse
from ..models import Cliente, Circuito  # <-- ¡Importamos Circuito!

# -----------------------------------------------------------------
# FUNCIÓN 1: Buscar Clientes (Esta ya la teníamos)
# -----------------------------------------------------------------
def search_clientes(request):
    """
    Una vista que busca clientes por razón social y devuelve JSON.
    Se activa con un parámetro GET 'q'.
    Ej: /search/clientes/?q=Empresa
    """
    query = request.GET.get('q', None)
    clientes_filtrados = []
    
    if query:
        clientes = Cliente.objects.filter(razon_social__icontains=query)[:10] 
        
        for cliente in clientes:
            clientes_filtrados.append({
                'id': cliente.id,
                'nombre': cliente.razon_social,
                'ruc': cliente.ruc
            })
            
    return JsonResponse({'clientes': clientes_filtrados})


# -----------------------------------------------------------------
# FUNCIÓN 2: Obtener Circuitos (¡Esta es la nueva!)
# -----------------------------------------------------------------
def get_circuitos_por_cliente(request, cliente_id):
    """
    Una vista que devuelve todos los circuitos de un cliente específico.
    Se activa por la URL: /api/get-circuitos/<cliente_id>/
    """
    circuitos_data = []
    try:
        # 1. Buscar los circuitos que pertenecen a este cliente
        circuitos = Circuito.objects.filter(cliente_id=cliente_id)
        
        # 2. Convertirlos al formato JSON que espera el JavaScript
        for circuito in circuitos:
            circuitos_data.append({
                'id': circuito.id,
                'nombre_circuito': circuito.nombre_circuito,
                'tipo_servicio': circuito.tipo_servicio,
                'renta_mensual': circuito.renta_mensual
            })
        
        # 3. Devolver la lista
        return JsonResponse({'circuitos': circuitos_data})

    except Exception as e:
        # Manejar errores (ej. un cliente_id que no existe)
        return JsonResponse({'error': str(e)}, status=404)