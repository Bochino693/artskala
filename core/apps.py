from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Fotos guardadas no banco: ao apagar o registro, os bytes sem uso saem também.
        from .midia import ligar_limpeza
        ligar_limpeza()
