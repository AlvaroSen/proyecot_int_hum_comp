# En: portal_retenciones/decorators.py

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import user_passes_test

def permission_required(perm):
    """
    Decora vistas para asegurar que el usuario tiene un permiso específico (ej: 'portal_retenciones.can_create_solicitud').
    Permite el acceso al superusuario.
    """
    def check_permission(user):
        # 1. Permite el acceso al superusuario
        if user.is_superuser:
            return True
        
        # 2. Verifica si el usuario tiene el permiso requerido
        if user.has_perm(perm):
            return True
        
        # 3. Si no cumple las condiciones, deniega el permiso
        raise PermissionDenied
    
    # user_passes_test se encarga de redirigir al LOGIN_URL si falla
    return user_passes_test(check_permission, login_url='/')