from django.core.management.base import BaseCommand, CommandError

from rdmo_ts4nfdi.upstream import (
    DEFAULT_GATEWAY_URL,
    DEFAULT_OPENAPI_URL,
    check_gateway_contract,
    check_gateway_live_contract,
)


class Command(BaseCommand):
    help = 'Check that the live TS4NFDI Gateway exposes the routes used by this plugin.'

    def add_arguments(self, parser):
        parser.add_argument('--openapi-url', default=DEFAULT_OPENAPI_URL)
        parser.add_argument('--gateway-url', default=DEFAULT_GATEWAY_URL)
        parser.add_argument(
            '--origin',
            help='RDMO browser origin to use for the optional direct-mode CORS assertion',
        )
        parser.add_argument(
            '--live',
            action='store_true',
            help='probe public Gateway responses and CORS used by the example configuration',
        )

    def handle(self, *args, **options):
        try:
            message = (
                check_gateway_live_contract(options['gateway_url'], options['origin'])
                if options['live']
                else check_gateway_contract(options['openapi_url'])
            )
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(message))
