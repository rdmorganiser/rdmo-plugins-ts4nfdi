import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver

from rdmo.projects.models import Value

from rdmo_ts4nfdi.composition import build_option_external_id_projector

logger = logging.getLogger(__name__)


@receiver(
    pre_save,
    sender=Value,
    dispatch_uid='rdmo_ts4nfdi.project_semantic_option_external_id',
)
def project_semantic_option_external_id(sender, instance, raw=False, update_fields=None, **kwargs):
    """Add one configured semantic option IRI before a live value is stored."""

    if raw or instance.snapshot_id is not None:
        return

    previous_option_uri = None
    if instance.pk:
        previous = sender.objects.filter(pk=instance.pk).values('option__uri').first()
        if previous:
            previous_option_uri = previous['option__uri']

    option_uri = instance.option.uri if instance.option_id else None
    try:
        external_id = build_option_external_id_projector().project_value(
            option_uri=option_uri,
            external_id=instance.external_id,
            previous_option_uri=previous_option_uri,
        )
    except (LookupError, RuntimeError) as exc:
        # Terminology enrichment must never prevent RDMO from saving an answer.
        logger.warning('Could not project a semantic option external id: %s', exc)
        return

    if external_id == instance.external_id:
        return
    if update_fields is not None and 'external_id' not in update_fields:
        logger.warning(
            'Skipped semantic external-id projection for value=%s because external_id '
            'is absent from update_fields=%s',
            instance.pk,
            sorted(update_fields),
        )
        return

    instance.external_id = external_id
