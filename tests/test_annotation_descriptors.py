from dataclasses import replace
from types import SimpleNamespace

from rdmo_ts4nfdi.application.annotations import AnnotationService
from rdmo_ts4nfdi.domain import (
    AnnotationCandidate,
    AnnotationMatcher,
    InterviewAnswer,
    PresentationPolicy,
    QuestionContext,
    ResourceReference,
)


def make_question():
    return QuestionContext(
        question_id=7,
        question_uri='https://example.test/questions/format',
        attribute_id=11,
        attribute_uri='https://example.test/domain/format',
        optionset_uris=('https://example.test/options/formats',),
    )


def make_answer():
    return InterviewAnswer(
        question=make_question(),
        value_id=1,
        label='XML',
        identifier='http://edamontology.org/format_2332',
        set_prefix='0',
        set_index=0,
        collection_index=0,
    )


class Host:
    def project_id(self, project):
        return project.id

    def page_id(self, page):
        return page.id

    def page_answers(self, project, page):
        return iter((make_answer(),))

    def value_answers(self, project, value):
        return iter((make_answer(),))


class Targets:
    def __init__(self, source=None, terminology=None, *, mapping=False):
        self.source = source
        self.terminology = terminology
        self.mapping = mapping

    def resolve(self, answer, matcher):
        yield AnnotationCandidate(
            question=answer.question,
            value_id=answer.value_id,
            label=answer.label,
            iri=answer.identifier,
            set_prefix=answer.set_prefix,
            set_index=answer.set_index,
            collection_index=answer.collection_index,
            source=self.source,
            terminology=self.terminology,
            mapping_set_id='fairagro-data-generation' if self.mapping else None,
            mapping_set_version='draft.1' if self.mapping else None,
        )


class NeverMetadata:
    def resolve(self, candidate, matcher):
        raise AssertionError('list_page_v2 must not resolve Gateway metadata')


class NeverPresentation:
    def build(self, *args):
        raise AssertionError('list_page_v2 must not build detail presentation')


MATCHER = AnnotationMatcher(
    id='formats',
    question_uri='https://example.test/questions/format',
    attribute_uri='https://example.test/domain/format',
    optionset_uri='https://example.test/options/formats',
    resource_type='entity',
    presentation=PresentationPolicy(
        adapter='tss',
        component='entity-info',
        options=(('entity_type', 'class'),),
    ),
    source=ResourceReference(
        id='ebi',
        label='EBI',
        database='ebi',
        backend_type='ols2',
    ),
    badge_label='EDAM',
    ontology_id='edam',
    gateway_params=(
        ('database', 'ebi'),
        ('collectionId', 'public'),
        ('api_token', 'must-not-reach-the-browser'),
    ),
)


def make_service(targets=None, matcher=MATCHER):
    return AnnotationService(
        host=Host(),
        targets=targets or Targets(),
        metadata=NeverMetadata(),
        presentation=NeverPresentation(),
        matchers=(matcher,),
    )


def test_v1_annotation_list_stays_on_v1_shape():
    payload = make_service().list_page(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()
    annotation = payload['occurrences'][0]['annotations'][0]

    assert payload['api_version'] == '1'
    assert 'gateway_context' not in annotation
    assert 'presentation' not in annotation


def test_v2_annotation_list_exposes_browser_resolution_context():
    payload = make_service().list_page_v2(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()
    annotation = payload['occurrences'][0]['annotations'][0]

    assert payload['api_version'] == '2'
    assert annotation['gateway_context'] == {
        'ontology_id': 'edam',
        'database': 'ebi',
        'backend_type': 'ols2',
        'params': {'collectionId': 'public'},
    }
    assert annotation['presentation'] == {
        'adapter': 'tss',
        'component': 'entity-info',
        'options': {'entity_type': 'class'},
    }


def test_v2_annotation_list_does_not_expose_private_gateway_params():
    annotation = make_service().list_page_v2(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()['occurrences'][0]['annotations'][0]

    assert 'api_token' not in annotation['gateway_context']['params']


def test_v2_does_not_resolve_summary_metadata_even_when_matcher_requests_it():
    matcher = replace(MATCHER, resolve_summary_metadata=True)

    annotation = make_service(matcher=matcher).list_page_v2(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()['occurrences'][0]['annotations'][0]

    assert annotation['short_form'] is None
    assert annotation['source']['database'] == 'ebi'


def test_v2_annotation_list_contextualizes_semantic_mapping_targets_and_keeps_provenance():
    source = ResourceReference(
        id='agroportal',
        label='AgroPortal',
        database='agroportal',
        backend_type='ontoportal',
    )
    terminology = ResourceReference(
        id='INRAETHES',
        label='INRAE Thesaurus',
    )
    matcher = replace(
        MATCHER,
        source=None,
        ontology_id=None,
        gateway_params=(),
    )

    annotation = make_service(
        targets=Targets(source=source, terminology=terminology, mapping=True),
        matcher=matcher,
    ).list_page_v2(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()['occurrences'][0]['annotations'][0]

    assert annotation['source']['database'] == 'agroportal'
    assert annotation['terminology']['id'] == 'INRAETHES'
    assert annotation['mapping_set_id'] == 'fairagro-data-generation'
    assert annotation['mapping_set_version'] == 'draft.1'
    assert annotation['gateway_context'] == {
        'ontology_id': 'INRAETHES',
        'database': 'agroportal',
        'backend_type': 'ontoportal',
        'params': {},
    }


def test_v2_context_does_not_leak_between_candidates():
    class MultipleTargets:
        def resolve(self, answer, matcher):
            for source_id, terminology_id in (
                ('agroportal', 'INRAETHES'),
                ('ebi', 'edam'),
            ):
                yield AnnotationCandidate(
                    question=answer.question,
                    value_id=answer.value_id,
                    label=answer.label,
                    iri=f'https://example.test/{terminology_id}',
                    set_prefix=answer.set_prefix,
                    set_index=answer.set_index,
                    collection_index=answer.collection_index,
                    source=ResourceReference(
                        id=source_id,
                        database=source_id,
                        backend_type='ontoportal' if source_id == 'agroportal' else 'ols2',
                    ),
                    terminology=ResourceReference(id=terminology_id, label=terminology_id),
                )

    matcher = replace(MATCHER, source=None, ontology_id=None, gateway_params=())
    annotations = make_service(
        targets=MultipleTargets(),
        matcher=matcher,
    ).list_page_v2(
        SimpleNamespace(id=24),
        SimpleNamespace(id=341),
    ).to_dict()['occurrences'][0]['annotations']

    assert [annotation['gateway_context']['database'] for annotation in annotations] == [
        'agroportal',
        'ebi',
    ]
    assert [annotation['gateway_context']['ontology_id'] for annotation in annotations] == [
        'INRAETHES',
        'edam',
    ]
