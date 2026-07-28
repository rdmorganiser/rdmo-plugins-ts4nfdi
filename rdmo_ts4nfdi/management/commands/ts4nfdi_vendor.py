import tarfile

from django.core.management.base import BaseCommand, CommandError

from rdmo_ts4nfdi.upstream import run_vendor_action


class Command(BaseCommand):
    help = 'Update or verify the vendored TS4NFDI Terminology Service Suite browser bundle.'

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument('--latest', action='store_true', help='install the current npm latest release')
        selection.add_argument('--tss-version', help='install one exact npm release')
        selection.add_argument('--check', action='store_true', help='verify local asset hashes without network access')
        selection.add_argument('--check-latest', action='store_true', help='fail if npm publishes a newer release')

    def handle(self, *args, **options):
        try:
            messages = run_vendor_action(
                latest=options['latest'],
                version=options['tss_version'],
                check=options['check'],
                check_latest=options['check_latest'],
            )
        except (KeyError, OSError, RuntimeError, tarfile.TarError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        for message in messages:
            self.stdout.write(self.style.SUCCESS(message))
