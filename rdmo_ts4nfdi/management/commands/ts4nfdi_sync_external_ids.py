from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import now

from rdmo.projects.models import Project, Value

from rdmo_ts4nfdi.composition import build_option_external_id_projector


class Command(BaseCommand):
    help = 'Project configured single-concept semantic options into live RDMO value external IDs.'

    def add_arguments(self, parser):
        parser.add_argument('--project', type=int, required=True, help='RDMO project id to update')
        parser.add_argument('--dry-run', action='store_true', help='show the number of changes without writing them')

    def handle(self, *args, **options):
        project_id = options['project']
        dry_run = options['dry_run']
        if not Project.objects.filter(pk=project_id).exists():
            raise CommandError(f'Project {project_id} does not exist.')

        try:
            projector = build_option_external_id_projector()
        except (LookupError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc
        if not projector.policy.enabled:
            raise CommandError('TS4NFDI option external-id projection is disabled.')

        values = (
            Value.objects.filter(project_id=project_id, snapshot=None)
            .select_related('option')
            .order_by('pk')
        )
        external_id_max_length = Value._meta.get_field('external_id').max_length
        changes = []
        for value in values.iterator():
            option_uri = value.option.uri if value.option_id else None
            projected = projector.project_value(
                option_uri=option_uri,
                external_id=value.external_id,
                previous_option_uri=option_uri,
            )
            if projected == value.external_id:
                continue
            if len(projected) > external_id_max_length:
                self.stderr.write(
                    self.style.WARNING(
                        f'Skipping value {value.pk}: projected IRI exceeds external_id max length.'
                    )
                )
                continue
            changes.append((value.pk, value.external_id, projected))

        if not dry_run:
            with transaction.atomic():
                timestamp = now()
                for value_id, _old_external_id, projected in changes:
                    Value.objects.filter(pk=value_id).update(
                        external_id=projected,
                        updated=timestamp,
                    )

        action = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{action} {len(changes)} value(s) in project {project_id}.'))
