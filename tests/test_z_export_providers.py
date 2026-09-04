import json
from types import SimpleNamespace
from xml.etree import ElementTree

from rdmo_ts4nfdi.integrations.rdmo.exports import EXPORT_FORMAT


def test_json_and_xml_project_providers_return_downloads(monkeypatch):
    from rdmo_ts4nfdi.exports import (
        AnnotatedJSONExport,
        AnnotatedXMLExport,
        SimpleAnnotatedJSONExport,
    )

    payload = {
        'format': EXPORT_FORMAT,
        'schema_version': '1',
        'project': {'id': 5, 'title': 'Project'},
        'snapshot': None,
        'sections': [],
    }
    project = SimpleNamespace(title='Project')

    json_export = AnnotatedJSONExport('key', 'label', 'class')
    json_export.project = project
    monkeypatch.setattr(json_export, 'get_payload', lambda: payload)
    json_response = json_export.render()

    assert json.loads(json_response.content) == payload
    assert json_response['Content-Type'].startswith('application/json')
    assert 'Project-ts4nfdi-annotated.json' in json_response['Content-Disposition']

    simple_json_export = SimpleAnnotatedJSONExport('key', 'label', 'class')
    simple_json_export.project = project
    monkeypatch.setattr(simple_json_export, 'get_payload', lambda: payload)
    simple_json_response = simple_json_export.render()

    assert json.loads(simple_json_response.content) == []
    assert simple_json_response['Content-Type'].startswith('application/json')
    assert 'Project-ts4nfdi-simple-annotated.json' in simple_json_response['Content-Disposition']

    xml_export = AnnotatedXMLExport('key', 'label', 'class')
    xml_export.project = project
    monkeypatch.setattr(xml_export, 'get_payload', lambda: payload)
    xml_response = xml_export.render()

    assert ElementTree.fromstring(xml_response.content).tag == 'annotated-answers'
    assert xml_response['Content-Type'].startswith('application/xml')
    assert 'Project-ts4nfdi-annotated.xml' in xml_response['Content-Disposition']


def test_snapshot_provider_derives_project_and_pdf_uses_shared_payload(monkeypatch):
    from rdmo_ts4nfdi.exports import AnnotatedPDFExport, SimpleAnnotatedJSONExport

    project = SimpleNamespace(title='Current project')
    snapshot = SimpleNamespace(title='Release 1', project=project)
    payload = {'format': EXPORT_FORMAT, 'schema_version': '1', 'sections': []}
    export = AnnotatedPDFExport('key', 'label', 'class')
    export.snapshot = snapshot
    export.request = SimpleNamespace()
    monkeypatch.setattr(export, 'get_payload', lambda: payload)

    captured = {}

    def render_to_format(request, output_format, title, template, context):
        captured.update(
            request=request,
            output_format=output_format,
            title=title,
            template=template,
            context=context,
        )
        return 'pdf-response'

    monkeypatch.setattr('rdmo_ts4nfdi.exports.render_to_format', render_to_format)

    assert export.render() == 'pdf-response'
    assert captured['output_format'] == 'pdf'
    assert captured['title'] == 'Release 1'
    assert captured['template'] == 'rdmo_ts4nfdi/annotated_answers_export.html'
    assert captured['context']['project'] is project
    assert captured['context']['snapshot'] is snapshot
    assert captured['context']['export'] is payload

    simple_json_export = SimpleAnnotatedJSONExport('key', 'label', 'class')
    simple_json_export.snapshot = snapshot
    monkeypatch.setattr(simple_json_export, 'get_payload', lambda: payload)

    response = simple_json_export.render()

    assert json.loads(response.content) == []
    assert 'Release 1-ts4nfdi-simple-annotated.json' in response['Content-Disposition']
