from django.core.management.base import BaseCommand, CommandError

from rdmo_ts4nfdi.upstream import DEFAULT_OPENAPI_URL, check_gateway_contract


class Command(BaseCommand):
    help = 'Check that the live TS4NFDI Gateway exposes the routes used by this plugin.'

    def add_arguments(self, parser):
        parser.add_argument('--openapi-url', default=DEFAULT_OPENAPI_URL)

    def handle(self, *args, **options):
        try:
            message = check_gateway_contract(options['openapi_url'])
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(message))
