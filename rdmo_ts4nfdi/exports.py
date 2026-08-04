import json

from django.conf import settings
from django.http import HttpResponse

from rdmo.projects.exports import Export

from rdmo_ts4nfdi.composition import build_annotation_service
from rdmo_ts4nfdi.export_renderers import render_semantic_xml


class SemanticJSONExport(Export):
    """Export normalized TS4NFDI annotations without changing RDMO's formats."""

    def render(self):
        payload = build_annotation_service().export_project(self.project).to_dict()
        response = HttpResponse(
            json.dumps(payload, ensure_ascii=False, indent=2),
            content_type='application/json',
        )
        if settings.EXPORT_CONTENT_DISPOSITION == 'attachment':
            response['Content-Disposition'] = (
                f'attachment; filename="{self.project.title}-ts4nfdi.json"'
            )
        return response


class SemanticXMLExport(Export):
    """Export the same semantic annotation contract as explicit XML."""

    def render(self):
        payload = build_annotation_service().export_project(self.project).to_dict()
        response = HttpResponse(
            render_semantic_xml(payload),
            content_type='application/xml',
        )
        if settings.EXPORT_CONTENT_DISPOSITION == 'attachment':
            response['Content-Disposition'] = (
                f'attachment; filename="{self.project.title}-ts4nfdi.xml"'
            )
        return response
