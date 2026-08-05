from rdmo_ts4nfdi.application import SemanticOptionExternalIdProjector
from rdmo_ts4nfdi.domain import (
    OptionExternalIdProjectionPolicy,
    ResourceReference,
    SemanticOption,
    SemanticOptionSet,
    SemanticTarget,
)


class Registry:
    def __init__(self, *mapping_sets):
        self.mapping_sets = {mapping_set.id: mapping_set for mapping_set in mapping_sets}

    def get(self, mapping_set_id):
        return self.mapping_sets[mapping_set_id]


def target(identifier, iri, *, relation='close', status='draft'):
    return SemanticTarget(
        id=identifier,
        iri=iri,
        label=identifier,
        relation=relation,
        curation_status=status,
        source=ResourceReference(id='source', label='Source'),
        terminology=ResourceReference(id='terms', label='Terms'),
    )


def option(identifier, *targets):
    return SemanticOption(
        id=identifier,
        uri=f'https://example.test/options/{identifier}',
        labels=(('en', identifier),),
        targets=targets,
    )


def projector(*options):
    mapping_set = SemanticOptionSet(
        id='example',
        version='1',
        options=options,
    )
    policy = OptionExternalIdProjectionPolicy(
        enabled=True,
        mapping_set_ids=('example',),
        relations=frozenset({'exact', 'close'}),
        curation_statuses=frozenset({'draft', 'reviewed'}),
    )
    return SemanticOptionExternalIdProjector(Registry(mapping_set), policy), mapping_set


def test_provider_option_uri_is_projected_to_single_concept_iri():
    semantic_option = option(
        'field-trials',
        target('field-experiment', 'https://example.test/concepts/field-experiment'),
    )
    value_projector, _mapping_set = projector(semantic_option)

    assert value_projector.project_value(
        option_uri=None,
        external_id=semantic_option.uri,
    ) == 'https://example.test/concepts/field-experiment'

    assert value_projector.option_identifier(
        semantic_option.uri
    ) == 'https://example.test/concepts/field-experiment'


def test_fixed_option_keeps_option_identity_and_adds_external_id():
    semantic_option = option('field-trials', target('field-experiment', 'https://example.test/concepts/field'))
    value_projector, _mapping_set = projector(semantic_option)

    assert value_projector.project_value(
        option_uri=semantic_option.uri,
        external_id='',
    ) == 'https://example.test/concepts/field'


def test_fixed_option_does_not_replace_an_unrelated_external_id():
    semantic_option = option('field-trials', target('field-experiment', 'https://example.test/concepts/field'))
    value_projector, _mapping_set = projector(semantic_option)

    assert value_projector.project_value(
        option_uri=semantic_option.uri,
        external_id='https://other.test/user-supplied-id',
    ) == 'https://other.test/user-supplied-id'


def test_fixed_option_change_replaces_the_previous_managed_external_id():
    previous = option('field-trials', target('field-experiment', 'https://example.test/concepts/field'))
    current = option('laboratory', target('laboratory', 'https://example.test/concepts/laboratory'))
    value_projector, _mapping_set = projector(previous, current)

    assert value_projector.project_value(
        option_uri=current.uri,
        external_id='https://example.test/concepts/field',
        previous_option_uri=previous.uri,
    ) == 'https://example.test/concepts/laboratory'


def test_unmapped_and_composed_provider_options_keep_their_local_identifier():
    unmapped = option('unmapped')
    composed = option(
        'composed',
        target('first', 'https://example.test/concepts/first'),
        target('second', 'https://example.test/concepts/second'),
    )
    value_projector, _mapping_set = projector(unmapped, composed)

    assert value_projector.project_provider_external_id(unmapped.uri) == unmapped.uri
    assert value_projector.project_provider_external_id(composed.uri) == composed.uri
    assert value_projector.option_identifier(unmapped.uri) == unmapped.uri
    assert value_projector.option_identifier(composed.uri) == composed.uri


def test_mapping_set_resolves_a_projected_single_target_identifier():
    semantic_option = option('field-trials', target('field-experiment', 'https://example.test/concepts/field'))
    _value_projector, mapping_set = projector(semantic_option)

    assert mapping_set.get('https://example.test/concepts/field') == semantic_option


def test_projection_policy_filters_relation_and_curation_status():
    related = option(
        'related',
        target('related', 'https://example.test/concepts/related', relation='related'),
    )
    deprecated = option(
        'deprecated',
        target('deprecated', 'https://example.test/concepts/deprecated', status='deprecated'),
    )
    value_projector, _mapping_set = projector(related, deprecated)

    assert value_projector.project_provider_external_id(related.uri) == related.uri
    assert value_projector.project_provider_external_id(deprecated.uri) == deprecated.uri
