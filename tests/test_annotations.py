from dataclasses import replace
from types import SimpleNamespace

from rdmo_ts4nfdi.application import AnnotationService, AnnotationTargetResolver
from rdmo_ts4nfdi.application.entitysets import GatewayEntitySetProvenanceResolver
from rdmo_ts4nfdi.domain import (
    AnnotationMatcher,
    InterviewAnswer,
    PresentationDescriptor,
    PresentationPolicy,
    QuestionContext,
    ResolvedMetadata,
    ResourceReference,
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


def make_service(answers, matcher=None):
    return AnnotationService(
        host=Host(answers),
        targets=AnnotationTargetResolver(),
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
    assert [occurrence['key'] for occurrence in payload['occurrences']] == ['7:0:0', '7:0:1']
    assert [annotation['value_id'] for annotation in payload['occurrences'][0]['annotations']] == [1, 2]


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
        targets=AnnotationTargetResolver(),
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
    answer = replace(make_answer(), label='AGROVOC', identifier='agrovoc')

    annotation = make_service((answer,), matcher=matcher).list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()['occurrences'][0]['annotations'][0]

    assert annotation['label'] == 'AGROVOC'
    assert annotation['iri'] == 'agrovoc'
    assert annotation['kind'] == 'ontology'


def test_unconfigured_opaque_identifier_is_not_annotated():
    answer = replace(make_answer(), identifier='not-an-iri')
    assert list(AnnotationTargetResolver().resolve(answer, make_matcher())) == []


def test_project_annotation_export_keeps_selected_entity_iri():
    answer = replace(
        make_answer(),
        label='field experiment',
        identifier='http://opendata.inrae.fr/thesaurusINRAE/c_17625',
    )
    project = SimpleNamespace(
        id=24,
        title='Semantic project',
        catalog_uri='https://example.test/catalog',
        pages=(SimpleNamespace(id=341),),
    )

    payload = make_service((answer,)).export_project(project).to_dict()
    annotation = payload['pages'][0]['occurrences'][0]['annotations'][0]

    assert payload['title'] == 'Semantic project'
    assert payload['catalog_uri'] == 'https://example.test/catalog'
    assert annotation['answer_id'] == answer.identifier
    assert annotation['iri'] == answer.identifier

    xml = render_semantic_xml(payload).decode()
    assert f'<answer_id>{answer.identifier}</answer_id>' in xml
    assert f'<iri>{answer.identifier}</iri>' in xml


def test_annotation_detail_is_composed_from_independent_adapters():
    payload = make_service((make_answer(),)).detail(
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
        'props': {'projectId': 24, 'iri': 'http://edamontology.org/format_2332'},
    }


def test_annotation_detail_falls_back_when_metadata_adapter_fails():
    class BrokenMetadata:
        def resolve(self, candidate, matcher):
            raise RuntimeError('Gateway unavailable')

    service = AnnotationService(
        host=Host((make_answer(),)),
        targets=AnnotationTargetResolver(),
        metadata=BrokenMetadata(),
        presentation=Presentation(),
        matchers=(make_matcher(),),
    )

    payload = service.detail(SimpleNamespace(id=24), SimpleNamespace(id=1)).to_dict()

    assert payload['metadata_status'] == 'unavailable'
    assert payload['label'] == 'XML'
    assert payload['ontology_id'] == 'edam'


def test_entityset_provenance_uses_upstream_entry_without_metadata_normalization():
    class Gateway:
        def __init__(self):
            self.calls = []

        def get(self, path):
            self.calls.append(path)
            return (
                [
                    {
                        'id': 'fairagro-options',
                        'entities': [
                            {
                                'uri': 'http://purl.obolibrary.org/obo/NCIT_C180602',
                                'label': [{'value': 'Workshop', 'lang': 'en'}],
                                'definition': [{'value': 'A focused educational program.', 'lang': 'en'}],
                                'terminology': 'ncit',
                                'provider': 'tib',
                            },
                        ],
                    },
                ],
                False,
            )

    matcher = replace(
        make_matcher(),
        provider_key='ts4nfdi_entitysets',
        entityset_id='fairagro-options',
        entityset_endpoint='entitysets',
        source=None,
        ontology_id=None,
        gateway_params=(),
        presentation=PresentationPolicy(adapter='native'),
    )
    answer = replace(
        make_answer(),
        label='Workshop',
        identifier='http://purl.obolibrary.org/obo/NCIT_C180602',
    )
    annotation, resolved_matcher = make_service((answer,), matcher=matcher).value_annotation(
        SimpleNamespace(id=24),
        SimpleNamespace(id=1),
        matcher_id='formats',
    )
    gateway = Gateway()
    payload = GatewayEntitySetProvenanceResolver(
        gateway,
        sources={
            'tib': {
                'id': 'tib',
                'label': 'TIB Terminology Service',
                'database': 'tib',
                'backend_type': 'ols2',
                'url': 'https://api.terminology.tib.eu/api/v2',
            },
        },
    ).resolve(annotation, resolved_matcher).to_dict()

    assert gateway.calls == ['entitysets']
    assert payload['definitions'] == ['A focused educational program.']
    assert payload['source']['database'] == 'tib'
    assert payload['terminology'] == {
        'id': 'ncit',
        'label': 'ncit',
        'iri': None,
        'url': None,
        'database': None,
        'backend_type': None,
    }
    assert payload['gateway_context'] == {
        'ontology_id': 'ncit',
        'database': 'tib',
        'backend_type': 'ols2',
        'params': {},
    }
    assert payload['presentation'] == {
        'adapter': 'tss',
        'component': 'entity-info',
        'options': {},
    }


def test_entityset_provenance_retains_a_native_detail_for_non_ols_sources():
    class Gateway:
        def get(self, path):
            assert path == 'entitysets'
            return (
                [
                    {
                        'id': 'fairagro-options',
                        'entities': [
                            {
                                'uri': 'http://aims.fao.org/aos/agrovoc/c_37359',
                                'definition': [{'value': 'Image-processing definition.', 'lang': 'en'}],
                                'terminology': 'agrovoc',
                                'provider': 'agrovoc',
                            },
                        ],
                    },
                ],
                False,
            )

    matcher = replace(
        make_matcher(),
        entityset_id='fairagro-options',
        entityset_endpoint='entitysets',
        source=None,
        ontology_id=None,
        gateway_params=(),
    )
    answer = replace(
        make_answer(),
        label='image processing',
        identifier='http://aims.fao.org/aos/agrovoc/c_37359',
    )
    annotation, resolved_matcher = make_service((answer,), matcher=matcher).value_annotation(
        SimpleNamespace(id=24),
        SimpleNamespace(id=1),
    )
    payload = GatewayEntitySetProvenanceResolver(
        Gateway(),
        sources={
            'agrovoc': {
                'id': 'agrovoc',
                'label': 'FAO AGROVOC service',
                'database': 'agrovoc',
                'backend_type': 'skosmos',
                'url': 'https://agrovoc.fao.org/browse/rest/v1',
            },
        },
    ).resolve(annotation, resolved_matcher).to_dict()

    assert payload['definitions'] == ['Image-processing definition.']
    assert payload['presentation'] == {
        'adapter': 'native',
        'component': None,
        'options': {},
    }


def test_tss_presentation_descriptor_keeps_gateway_source_parameters():
    matcher = replace(
        make_matcher(),
        presentation=PresentationPolicy(
            adapter='tss',
            component='entity-info',
            options=(('entity_type', 'class'),),
        ),
    )
    annotation = make_service((make_answer(),)).list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).occurrences[0].annotations[0]

    descriptor = AnnotationPresentationRegistry().build(
        24,
        annotation,
        ResolvedMetadata(ontology_id='edam'),
        matcher,
    ).to_dict()

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
            options=(('accent', 'green'), ('show_source', True)),
        ),
    )
    annotation = make_service((make_answer(),)).list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).occurrences[0].annotations[0]

    descriptor = AnnotationPresentationRegistry().build(
        24,
        annotation,
        ResolvedMetadata(ontology_id='edam'),
        matcher,
    ).to_dict()

    assert descriptor == {
        'adapter': 'fairagro-concept-card',
        'component': 'compact',
        'props': {'accent': 'green', 'show_source': True},
    }
