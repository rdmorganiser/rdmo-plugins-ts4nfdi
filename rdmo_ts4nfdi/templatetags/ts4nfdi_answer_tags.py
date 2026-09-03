import logging

from django import template

from rdmo_ts4nfdi.utils import is_http_iri

logger = logging.getLogger(__name__)
register = template.Library()


def build_answer_link_map(project, snapshot=None):
    """Return stored, matched entity IRIs keyed by RDMO value id."""
    # Keep composition lazy so importing the template library does not require
    # a configured RDMO settings object (useful for plugin and template tests).
    from rdmo_ts4nfdi.composition import build_annotation_service

    service = build_annotation_service()
    links = {}
    for page in project.catalog.pages:
        payload = service.list_page_v2(project, page, snapshot=snapshot)
        for occurrence in payload.occurrences:
            for descriptor in occurrence.annotations:
                annotation = descriptor.annotation
                if annotation.kind == 'entity' and is_http_iri(annotation.iri):
                    links[annotation.value_id] = annotation.iri
    return links


@register.simple_tag
def ts4nfdi_answer_links(project, snapshot=None):
    """Build a fail-safe link map for an RDMO answers render."""
    try:
        return build_answer_link_map(project, snapshot or None)
    except Exception:
        logger.exception(
            'Could not build TS4NFDI answer links for project=%s.',
            getattr(project, 'pk', getattr(project, 'id', None)),
        )
        return {}


@register.simple_tag
def ts4nfdi_answer_iri(links, value_id):
    try:
        return links.get(value_id)
    except AttributeError:
        return None
