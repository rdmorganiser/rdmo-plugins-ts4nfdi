from django.conf import settings
from django.http import HttpResponse
from django.utils.encoding import force_str

from rdmo.core.utils import render_to_format
from rdmo.projects.exports import Export

from rdmo_ts4nfdi.composition import build_annotation_service
from rdmo_ts4nfdi.export_renderers import (
    render_annotated_json,
    render_annotated_xml,
    render_simple_annotated_json,
)
from rdmo_ts4nfdi.integrations.rdmo.exports import RDMOAnnotatedAnswersBuilder


class AnnotatedExport(Export):
    extension = ''

    def get_subject(self):
        if self.snapshot is not None:
            return self.snapshot.project, self.snapshot
        return self.project, None

    def get_payload(self):
        project, snapshot = self.get_subject()
        return RDMOAnnotatedAnswersBuilder(
            build_annotation_service()
        ).build(project, snapshot)

    def get_title(self):
        project, snapshot = self.get_subject()
        return force_str(snapshot.title if snapshot is not None else project.title)

    def get_filename(self):
        return f'{self.get_title()}-ts4nfdi-annotated.{self.extension}'

    def response(self, content, content_type):
        response = HttpResponse(content, content_type=content_type)
        if settings.EXPORT_CONTENT_DISPOSITION == 'attachment':
            response['Content-Disposition'] = (
                f'attachment; filename="{self.get_filename()}"'
            )
        return response


class AnnotatedJSONExport(AnnotatedExport):
    extension = 'json'

    def render(self):
        return self.response(
            render_annotated_json(self.get_payload()),
            'application/json',
        )


class SimpleAnnotatedJSONExport(AnnotatedExport):
    extension = 'json'

    def get_filename(self):
        return f'{self.get_title()}-ts4nfdi-simple-annotated.json'

    def render(self):
        return self.response(
            render_simple_annotated_json(self.get_payload()),
            'application/json',
        )


class AnnotatedXMLExport(AnnotatedExport):
    extension = 'xml'

    def render(self):
        return self.response(
            render_annotated_xml(self.get_payload()),
            'application/xml',
        )


class AnnotatedPDFExport(AnnotatedExport):
    extension = 'pdf'

    def render(self):
        project, snapshot = self.get_subject()
        payload = self.get_payload()
        return render_to_format(
            self.request,
            'pdf',
            self.get_title(),
            'rdmo_ts4nfdi/annotated_answers_export.html',
            {
                'project': project,
                'snapshot': snapshot,
                'export': payload,
            },
        )
