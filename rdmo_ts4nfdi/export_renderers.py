import json
from xml.etree import ElementTree

from rdmo_ts4nfdi.utils import is_http_iri


def render_annotated_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_simple_annotated_json(payload: dict) -> str:
    answers = []
    for section in payload.get('sections', []):
        for page in section.get('pages', []):
            for answer in page.get('answers', []):
                answers.append(
                    {
                        'question': answer['question']['text'],
                        'set': ' '.join(answer.get('set_labels', [])),
                        'values': [
                            {
                                'label': value['label'],
                                'iri': _annotation_http_iri(value.get('annotation')),
                            }
                            for value in answer.get('values', [])
                        ],
                    }
                )
    return json.dumps(answers, ensure_ascii=False, indent=2)


def _annotation_http_iri(annotation):
    iri = annotation.get('iri') if annotation else None
    return iri if is_http_iri(iri) else None


def render_annotated_xml(payload: dict) -> bytes:
    root = ElementTree.Element(
        'annotated-answers',
        {
            'format': str(payload['format']),
            'schema-version': str(payload['schema_version']),
        },
    )
    _append_project(root, payload['project'])
    if payload.get('snapshot'):
        _append_snapshot(root, payload['snapshot'])

    sections = ElementTree.SubElement(root, 'sections')
    for section_payload in payload.get('sections', []):
        section = ElementTree.SubElement(
            sections,
            'section',
            _attributes(section_payload, ('id', 'uri')),
        )
        _append_text(section, 'title', section_payload.get('title'))
        pages = ElementTree.SubElement(section, 'pages')
        for page_payload in section_payload.get('pages', []):
            page = ElementTree.SubElement(
                pages,
                'page',
                _attributes(page_payload, ('id', 'uri')),
            )
            _append_text(page, 'title', page_payload.get('title'))
            answers = ElementTree.SubElement(page, 'answers')
            for answer_payload in page_payload.get('answers', []):
                _append_answer(answers, answer_payload)

    ElementTree.indent(root, space='  ')
    return ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)


def _append_project(parent, payload):
    project = ElementTree.SubElement(parent, 'project', _attributes(payload, ('id',)))
    for key in ('title', 'description', 'catalog_uri', 'created', 'updated'):
        _append_text(project, key.replace('_', '-'), payload.get(key))


def _append_snapshot(parent, payload):
    snapshot = ElementTree.SubElement(parent, 'snapshot', _attributes(payload, ('id',)))
    for key in ('title', 'description', 'created', 'updated'):
        _append_text(snapshot, key, payload.get(key))


def _append_answer(parent, payload):
    answer = ElementTree.SubElement(
        parent,
        'answer',
        _attributes(payload, ('set_prefix', 'set_index'), hyphenate=True),
    )
    question_payload = payload['question']
    question = ElementTree.SubElement(
        answer,
        'question',
        _attributes(question_payload, ('id', 'uri')),
    )
    _append_text(question, 'text', question_payload.get('text'))
    _append_text(answer, 'attribute-uri', payload.get('attribute_uri'))
    set_labels = ElementTree.SubElement(answer, 'set-labels')
    for label in payload.get('set_labels', []):
        _append_text(set_labels, 'label', label)
    values = ElementTree.SubElement(answer, 'values')
    for value_payload in payload.get('values', []):
        _append_value(values, value_payload)


def _append_value(parent, payload):
    value = ElementTree.SubElement(
        parent,
        'value',
        _attributes(
            payload,
            ('id', 'collection_index', 'value_type'),
            hyphenate=True,
        ),
    )
    for key in ('text', 'label', 'unit'):
        _append_text(value, key, payload.get(key))

    option_payload = payload.get('option')
    if option_payload:
        option = ElementTree.SubElement(
            value,
            'option',
            _attributes(option_payload, ('uri',)),
        )
        _append_text(option, 'label', option_payload.get('label'))

    _append_text(value, 'external-id', payload.get('external_id'))
    if payload.get('annotation'):
        _append_annotation(value, payload['annotation'])
    if payload.get('file'):
        file = ElementTree.SubElement(
            value,
            'file',
            _attributes(payload['file'], ('url',)),
        )
        _append_text(file, 'name', payload['file'].get('name'))


def _append_annotation(parent, payload):
    annotation = ElementTree.SubElement(
        parent,
        'annotation',
        _attributes(payload, ('matcher_id', 'kind'), hyphenate=True),
    )
    for key in ('label', 'iri', 'badge_label', 'short_form', 'answer_id'):
        _append_text(annotation, key.replace('_', '-'), payload.get(key))
    _append_resource(annotation, 'source', payload.get('source'))
    _append_resource(annotation, 'terminology', payload.get('terminology'))


def _append_resource(parent, name, payload):
    if not payload:
        return
    resource = ElementTree.SubElement(parent, name)
    for key in ('id', 'label', 'iri', 'url', 'database', 'backend_type'):
        _append_text(resource, key.replace('_', '-'), payload.get(key))


def _attributes(payload, keys, *, hyphenate=False):
    attributes = {}
    for key in keys:
        value = payload.get(key)
        if value is not None and value != '':
            name = key.replace('_', '-') if hyphenate else key
            attributes[name] = str(value)
    return attributes


def _append_text(parent, name, value):
    if value is None or value == '':
        return
    element = ElementTree.SubElement(parent, name)
    element.text = str(value)
