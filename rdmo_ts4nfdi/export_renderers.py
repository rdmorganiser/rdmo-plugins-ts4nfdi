from xml.etree import ElementTree


def render_semantic_xml(payload: dict) -> bytes:
    root = ElementTree.Element(
        'ts4nfdi-semantic-project',
        {'api_version': str(payload.get('api_version', '1'))},
    )
    _append_text(root, 'project_id', payload.get('project_id'))
    _append_text(root, 'title', payload.get('title'))
    _append_text(root, 'catalog_uri', payload.get('catalog_uri'))

    pages = ElementTree.SubElement(root, 'pages')
    for page_payload in payload.get('pages', []):
        page = ElementTree.SubElement(
            pages,
            'page',
            {'id': str(page_payload.get('page_id', ''))},
        )
        for occurrence_payload in page_payload.get('occurrences', []):
            occurrence = ElementTree.SubElement(
                page,
                'occurrence',
                {
                    'key': str(occurrence_payload.get('key', '')),
                    'question_id': str(occurrence_payload.get('question_id', '')),
                    'set_prefix': str(occurrence_payload.get('set_prefix', '')),
                    'set_index': str(occurrence_payload.get('set_index', '')),
                },
            )
            _append_text(occurrence, 'question_uri', occurrence_payload.get('question_uri'))
            _append_text(occurrence, 'attribute_id', occurrence_payload.get('attribute_id'))
            for annotation_payload in occurrence_payload.get('annotations', []):
                _append_annotation(occurrence, annotation_payload)

    ElementTree.indent(root, space='  ')
    return ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)


def _append_annotation(parent, payload: dict) -> None:
    annotation = ElementTree.SubElement(
        parent,
        'annotation',
        {
            'value_id': str(payload.get('value_id', '')),
            'collection_index': str(payload.get('collection_index', '')),
            'matcher_id': str(payload.get('matcher_id', '')),
            'kind': str(payload.get('kind', '')),
        },
    )
    for key in (
        'label',
        'answer_id',
        'target_id',
        'target_label',
        'iri',
        'mapping_relation',
        'curation_status',
        'mapping_set_id',
        'mapping_set_version',
    ):
        _append_text(annotation, key, payload.get(key))
    _append_resource(annotation, 'source', payload.get('source'))
    _append_resource(annotation, 'terminology', payload.get('terminology'))


def _append_resource(parent, name: str, payload: dict | None) -> None:
    if not payload:
        return
    resource = ElementTree.SubElement(parent, name)
    for key in ('id', 'label', 'iri', 'url', 'database', 'backend_type'):
        _append_text(resource, key, payload.get(key))


def _append_text(parent, name: str, value) -> None:
    if value is None or value == '':
        return
    element = ElementTree.SubElement(parent, name)
    element.text = str(value)
