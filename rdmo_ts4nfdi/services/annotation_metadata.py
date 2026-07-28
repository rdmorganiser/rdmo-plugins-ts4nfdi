from rdmo_ts4nfdi.providers.utils import get_first_value, get_value, get_values


def build_source_metadata(matcher, result=None):
    configured_source = matcher.get('source') or {}
    result = result or {}

    source_id = configured_source.get('id') or get_first_value(
        result,
        ('source_name', 'sourceName'),
    )
    source_url = configured_source.get('url') or get_first_value(result, ('source',))
    source_label = configured_source.get('label') or source_id

    if not any((source_id, source_label, source_url)):
        return None

    return {
        'id': source_id,
        'label': source_label,
        'database': configured_source.get('database') or source_id,
        'backend_type': (
            configured_source.get('backend_type')
            or get_first_value(result, ('backend_type', 'backendType'))
        ),
        'url': source_url,
    }


def build_terminology_metadata(matcher, result=None):
    result = result or {}
    terminology_id = (
        get_first_value(result, ('ontologyId', 'ontology_id', 'ontology'))
        or matcher.get('ontology_id')
    )
    terminology_iri = get_first_value(
        result,
        ('ontologyIri', 'ontology_iri'),
    )
    terminology_label = matcher.get('badge_label') or terminology_id

    if not any((terminology_id, terminology_iri, terminology_label)):
        return None

    return {
        'id': terminology_id,
        'label': terminology_label,
        'iri': terminology_iri,
    }


def normalize_entity_metadata(result, matcher):
    definitions = get_values(
        result,
        ('definition', 'definitions', 'descriptions', 'description'),
    )
    synonyms = get_values(
        result,
        ('synonym', 'synonyms', 'alternativeLabels', 'alternative_labels'),
    )
    entity_types = get_values(result, ('type',))

    obsolete_value = get_value(result, 'isObsolete')
    if obsolete_value is None:
        obsolete_value = get_value(result, 'obsolete')

    return {
        'label': get_first_value(result, ('label', 'prefLabel')),
        'description': definitions[0] if definitions else None,
        'definitions': definitions,
        'synonyms': synonyms,
        'short_form': get_first_value(result, ('shortForm', 'short_form', 'obo_id')),
        'entity_types': entity_types,
        'obsolete': normalize_boolean(obsolete_value),
        'ontology_id': (
            get_first_value(result, ('ontologyId', 'ontology_name', 'ontology_id'))
            or matcher.get('ontology_id')
        ),
        'source': build_source_metadata(matcher, result),
        'terminology': build_terminology_metadata(matcher, result),
    }


def normalize_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes'}:
            return True
        if normalized in {'false', '0', 'no'}:
            return False
    return None
