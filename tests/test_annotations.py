from dataclasses import replace
from types import SimpleNamespace

from rdmo_ts4nfdi.application import AnnotationService, SemanticAnnotationTargetResolver
from rdmo_ts4nfdi.domain import (
    AnnotationMatcher,
    InterviewAnswer,
    PresentationDescriptor,
    PresentationPolicy,
    QuestionContext,
    ResolvedMetadata,
    ResourceReference,
    SemanticOption,
    SemanticOptionSet,
    SemanticTarget,
)
from rdmo_ts4nfdi.export_renderers import render_semantic_xml
from rdmo_ts4nfdi.presentation import AnnotationPresentationRegistry


def make_question(question_id=7):
    return QuestionContext(
        question_id=question_id,
        question_uri='https://example.test/questions/format',
        attribute_id=11,
        attribute_uri='https://example.test/domain/format',
        optionset_uris=('https://example.test/options/formats',),
    )


def make_answer(value_id=1, set_prefix='0', set_index=0):
    return InterviewAnswer(
        question=make_question(),
        value_id=value_id,
        label='XML',
        identifier='http://edamontology.org/format_2332',
        set_prefix=set_prefix,
        set_index=set_index,
        collection_index=value_id - 1,
    )


def make_matcher():
    return AnnotationMatcher(
        id='formats',
        question_uri='https://example.test/questions/format',
        attribute_uri='https://example.test/domain/format',
        optionset_uri='https://example.test/options/formats',
        resource_type='entity',
        presentation=PresentationPolicy(adapter='tss', component='entity-info'),
        source=ResourceReference(id='ebi', label='EBI', database='ebi'),
        badge_label='EDAM',
        ontology_id='edam',
        gateway_params=(('database', 'ebi'),),
    )


class Host:
    def __init__(self, answers):
        self.answers = answers

    def project_id(self, project):
        return project.id

    def page_id(self, page):
        return page.id

    def project_title(self, project):
        return project.title

    def project_catalog_uri(self, project):
        return project.catalog_uri

    def project_pages(self, project):
        return iter(project.pages)

    def page_answers(self, project, page):
        return iter(self.answers)

    def value_answers(self, project, value):
        return (answer for answer in self.answers if answer.value_id == value.id)


class Registry:
    def __init__(self, mapping_sets=()):
        self.mapping_sets = {mapping_set.id: mapping_set for mapping_set in mapping_sets}

    def get(self, mapping_set_id):
        return self.mapping_sets[mapping_set_id]


class Metadata:
    def resolve(self, candidate, matcher):
        return ResolvedMetadata(
            label=candidate.label,
            definitions=('eXtensible Markup Language format.',),
            ontology_id=matcher.ontology_id,
        )


class Presentation:
    def build(self, project_id, annotation, metadata, matcher):
        return PresentationDescriptor(
            adapter=matcher.presentation.adapter,
            component=matcher.presentation.component,
            props={'projectId': project_id, 'iri': annotation.iri},
        )


def make_service(answers, mapping_sets=(), matcher=None):
    return AnnotationService(
        host=Host(answers),
        targets=SemanticAnnotationTargetResolver(Registry(mapping_sets)),
        metadata=Metadata(),
        presentation=Presentation(),
        matchers=(matcher or make_matcher(),),
    )


def test_page_annotations_group_candidates_by_question_occurrence():
    service = make_service(
        (
            make_answer(value_id=1, set_prefix='0', set_index=0),
            make_answer(value_id=2, set_prefix='0', set_index=0),
            make_answer(value_id=3, set_prefix='0', set_index=1),
        )
    )

    payload = service.list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()

    assert payload['api_version'] == '1'
    assert [occurrence['key'] for occurrence in payload['occurrences']] == [
        '7:0:0',
        '7:0:1',
    ]
    assert [annotation['value_id'] for annotation in payload['occurrences'][0]['annotations']] == [
        1,
        2,
    ]


def test_page_annotation_summary_can_be_enriched_with_gateway_metadata():
    class SummaryMetadata:
        def resolve(self, candidate, matcher):
            return ResolvedMetadata(
                short_form='4813',
                source=ResourceReference(
                    id='agroportal',
                    label='agroportal',
                    url='https://data.agroportal.eu',
                ),
                terminology=ResourceReference(id='THESAGRO', label='THESAGRO'),
            )

    matcher = replace(
        make_matcher(),
        source=None,
        ontology_id=None,
        badge_label='Terminology',
        gateway_params=(),
        resolve_summary_metadata=True,
    )
    answer = replace(
        make_answer(),
        label='Chocolate',
        identifier='http://sistemas.agricultura.gov.br/tematres/vocab/thesagro/4813',
    )
    service = AnnotationService(
        host=Host((answer,)),
        targets=SemanticAnnotationTargetResolver(Registry()),
        metadata=SummaryMetadata(),
        presentation=Presentation(),
        matchers=(matcher,),
    )

    summary = service.list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()['occurrences'][0]['annotations'][0]

    assert summary['short_form'] == '4813'
    assert summary['source']['id'] == 'agroportal'
    assert summary['terminology']['id'] == 'THESAGRO'


def test_provider_backed_ontology_accepts_an_opaque_provider_identifier():
    matcher = replace(
        make_matcher(),
        resource_type='ontology',
        provider_key='collection-terminologies',
        presentation=PresentationPolicy(adapter='native'),
        source=None,
        ontology_id=None,
        gateway_params=(),
    )
    answer = replace(
        make_answer(),
        label='AGROVOC',
        identifier='agrovoc',
    )

    payload = make_service((answer,), matcher=matcher).list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()

    annotation = payload['occurrences'][0]['annotations'][0]
    assert annotation['label'] == 'AGROVOC'
    assert annotation['iri'] == 'agrovoc'
    assert annotation['kind'] == 'ontology'


def test_unconfigured_opaque_identifier_is_not_annotated():
    answer = replace(make_answer(), identifier='not-an-iri')
    resolver = SemanticAnnotationTargetResolver(Registry())

    assert list(resolver.resolve(answer, make_matcher())) == []


def test_project_annotation_export_keeps_selected_and_semantic_identifiers():
    mapping_set = SemanticOptionSet(
        id='fairagro-data-generation',
        version='draft.1',
        options=(
            SemanticOption(
                id='experiment_data',
                uri='https://example.test/options/experiment_data',
                labels=(('en', 'Field trials'),),
                targets=(
                    SemanticTarget(
                        id='field-experiment',
                        iri='https://example.test/concepts/field-experiment',
                        label='field experiment',
                        relation='close',
                        source=ResourceReference(id='example', label='Example source'),
                        terminology=ResourceReference(id='example-terms', label='Example terminology'),
                    ),
                ),
            ),
        ),
    )
    matcher = replace(
        make_matcher(),
        mapping_set_id=mapping_set.id,
        presentation=PresentationPolicy(adapter='native'),
        source=None,
        ontology_id=None,
        gateway_params=(),
    )
    answer = replace(
        make_answer(),
        label='Field trials',
        identifier='https://example.test/options/experiment_data',
    )
    service = make_service((answer,), (mapping_set,), matcher)
    project = SimpleNamespace(
        id=24,
        title='Semantic project',
        catalog_uri='https://example.test/catalog',
        pages=(SimpleNamespace(id=341),),
    )

    payload = service.export_project(project).to_dict()
    annotation = payload['pages'][0]['occurrences'][0]['annotations'][0]

    assert payload['title'] == 'Semantic project'
    assert payload['catalog_uri'] == 'https://example.test/catalog'
    assert annotation['answer_id'] == 'https://example.test/options/experiment_data'
    assert annotation['iri'] == 'https://example.test/concepts/field-experiment'
    assert annotation['mapping_set_id'] == 'fairagro-data-generation'
    assert annotation['mapping_set_version'] == 'draft.1'

    xml = render_semantic_xml(payload).decode()
    assert '<answer_id>https://example.test/options/experiment_data</answer_id>' in xml
    assert '<iri>https://example.test/concepts/field-experiment</iri>' in xml
    assert '<mapping_set_version>draft.1</mapping_set_version>' in xml


def test_annotation_detail_is_composed_from_independent_adapters():
    service = make_service((make_answer(),))

    payload = service.detail(
        SimpleNamespace(id=24),
        SimpleNamespace(id=1),
        matcher_id='formats',
    ).to_dict()

    assert payload['label'] == 'XML'
    assert payload['definitions'] == ['eXtensible Markup Language format.']
    assert payload['source']['database'] == 'ebi'
    assert payload['presentation'] == {
        'adapter': 'tss',
        'component': 'entity-info',
        'props': {
            'projectId': 24,
            'iri': 'http://edamontology.org/format_2332',
        },
    }


def test_annotation_detail_falls_back_when_metadata_adapter_fails():
    class BrokenMetadata:
        def resolve(self, candidate, matcher):
            raise RuntimeError('Gateway unavailable')

    service = AnnotationService(
        host=Host((make_answer(),)),
        targets=SemanticAnnotationTargetResolver(Registry()),
        metadata=BrokenMetadata(),
        presentation=Presentation(),
        matchers=(make_matcher(),),
    )

    payload = service.detail(
        SimpleNamespace(id=24),
        SimpleNamespace(id=1),
    ).to_dict()

    assert payload['metadata_status'] == 'unavailable'
    assert payload['label'] == 'XML'
    assert payload['ontology_id'] == 'edam'


def test_semantic_option_mapping_expands_answer_identity_into_annotation_target():
    source = ResourceReference(
        id='agroportal',
        label='AgroPortal',
        database='agroportal',
        backend_type='ontoportal',
    )
    terminology = ResourceReference(id='INRAETHES', label='INRAE Thesaurus')
    mapping_set = SemanticOptionSet(
        id='fairagro-data-generation',
        version='draft.1',
        options=(
            SemanticOption(
                id='experiment_data',
                uri='https://example.test/options/experiment_data',
                labels=(('en', 'Field trials'),),
                targets=(
                    SemanticTarget(
                        id='inrae-field-experiment',
                        iri='http://opendata.inrae.fr/thesaurusINRAE/c_17625',
                        label='field experiment',
                        relation='close',
                        source=source,
                        terminology=terminology,
                    ),
                ),
            ),
        ),
    )
    matcher = replace(
        make_matcher(),
        mapping_set_id='fairagro-data-generation',
        presentation=PresentationPolicy(adapter='native'),
        source=None,
        ontology_id=None,
        gateway_params=(),
    )
    answer = replace(
        make_answer(),
        label='Field trials',
        identifier='https://example.test/options/experiment_data',
    )
    service = make_service((answer,), (mapping_set,), matcher)

    summary = service.list_page(SimpleNamespace(id=24), SimpleNamespace(id=341)).to_dict()['occurrences'][0][
        'annotations'
    ][0]
    detail = service.detail(
        SimpleNamespace(id=24),
        SimpleNamespace(id=1),
        matcher_id='formats',
        target_id='inrae-field-experiment',
    ).to_dict()

    assert summary['label'] == 'Field trials'
    assert summary['iri'] == 'http://opendata.inrae.fr/thesaurusINRAE/c_17625'
    assert summary['target_id'] == 'inrae-field-experiment'
    assert summary['target_label'] == 'field experiment'
    assert summary['mapping_relation'] == 'close'
    assert summary['mapping_set_id'] == 'fairagro-data-generation'
    assert summary['mapping_set_version'] == 'draft.1'
    assert summary['source']['database'] == 'agroportal'
    assert summary['terminology']['id'] == 'INRAETHES'
    assert detail['label'] == 'field experiment'
    assert detail['ontology_id'] == 'INRAETHES'


def test_tss_presentation_descriptor_keeps_gateway_source_parameters():
    matcher = replace(
        make_matcher(),
        presentation=PresentationPolicy(
            adapter='tss',
            component='entity-info',
            options=(('entity_type', 'class'),),
        ),
    )
    annotation = (
        make_service((make_answer(),))
        .list_page(
            SimpleNamespace(id=24),
            SimpleNamespace(id=341),
        )
        .occurrences[0]
        .annotations[0]
    )

    descriptor = (
        AnnotationPresentationRegistry()
        .build(
            24,
            annotation,
            ResolvedMetadata(ontology_id='edam'),
            matcher,
        )
        .to_dict()
    )

    assert descriptor['adapter'] == 'tss'
    assert descriptor['component'] == 'entity-info'
    assert descriptor['props']['parameter'] == 'database=ebi'
    assert descriptor['props']['entityType'] == 'class'
    assert 'useLegacy' not in descriptor['props']


def test_custom_presentation_descriptor_passes_matcher_options_to_browser():
    matcher = replace(
        make_matcher(),
        presentation=PresentationPolicy(
            adapter='fairagro-concept-card',
            component='compact',
            options=(
                ('accent', 'green'),
                ('show_source', True),
            ),
        ),
    )
    annotation = (
        make_service((make_answer(),))
        .list_page(
            SimpleNamespace(id=24),
            SimpleNamespace(id=341),
        )
        .occurrences[0]
        .annotations[0]
    )

    descriptor = (
        AnnotationPresentationRegistry()
        .build(
            24,
            annotation,
            ResolvedMetadata(ontology_id='edam'),
            matcher,
        )
        .to_dict()
    )

    assert descriptor == {
        'adapter': 'fairagro-concept-card',
        'component': 'compact',
        'props': {
            'accent': 'green',
            'show_source': True,
        },
    }
