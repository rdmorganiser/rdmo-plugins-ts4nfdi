from django.apps import AppConfig


class RDMOTS4NFDIConfig(AppConfig):
    name = 'rdmo_ts4nfdi'
    verbose_name = 'RDMO TS4NFDI integration'

    def ready(self):
        from rdmo_ts4nfdi.integrations.rdmo import value_projection  # noqa: F401
