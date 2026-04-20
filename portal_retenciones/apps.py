from django.apps import AppConfig
from django.db.models.signals import post_migrate


def crear_grupo_analistas(sender, **kwargs):
    """Asegura que el grupo 'Analistas' exista con sus permisos tras cada migrate.

    Se ejecuta vía post_migrate porque los permisos se generan después de las
    migraciones de la app y no están disponibles durante RunPython.
    """
    if sender.name != "portal_retenciones":
        return

    from django.contrib.auth.models import Group, Permission

    grupo, _ = Group.objects.get_or_create(name="Analistas")
    codenames = [
        "can_configure_asignacion_ejecutivos",
        "can_view_menu",
        "can_view_solicitud_list",
        "can_view_personal",
        "can_create_solicitud",
    ]
    for codename in codenames:
        perm = Permission.objects.filter(codename=codename).first()
        if perm:
            grupo.permissions.add(perm)


class PortalRetencionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal_retenciones"

    def ready(self):
        post_migrate.connect(crear_grupo_analistas, sender=self)
