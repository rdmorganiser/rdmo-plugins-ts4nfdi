import logging

from django.http import Http404

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rdmo.projects.models import Project, Value

from rdmo_ts4nfdi.composition import build_annotation_service
from rdmo_ts4nfdi.integrations.ts4nfdi.gateway import (
    GatewayClient,
    GatewayError,
    GatewayRequestError,
    filter_gateway_query,
)

logger = logging.getLogger(__name__)


class ProjectAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_project(self, project_id):
        try:
            return Project.objects.filter_user(self.request.user).get(pk=project_id)
        except Project.DoesNotExist as exc:
            raise Http404 from exc


class AnnotationListView(ProjectAPIView):
    def get(self, request, project_id):
        project = self.get_project(project_id)
        page_id = request.query_params.get('page')
        if not page_id or project.catalog is None:
            raise Http404

        project.catalog.prefetch_elements()
        page = project.catalog.get_page(page_id)
        if page is None:
            raise Http404

        return Response(build_annotation_service().list_page(project, page).to_dict())


class AnnotationDetailView(ProjectAPIView):
    def get(self, request, project_id, value_id):
        project = self.get_project(project_id)
        try:
            value = (
                Value.objects.filter_user(request.user)
                .select_related('attribute', 'option')
                .get(project=project, snapshot=None, pk=value_id)
            )
        except Value.DoesNotExist as exc:
            raise Http404 from exc

        try:
            payload = build_annotation_service().detail(
                project,
                value,
                matcher_id=request.query_params.get('matcher'),
                target_id=request.query_params.get('target'),
            )
        except LookupError as exc:
            raise Http404 from exc

        return Response(payload.to_dict())


class GatewayProxyView(ProjectAPIView):
    def get(self, request, project_id, gateway_path):
        self.get_project(project_id)
        gateway_path = f'ols4/api/{gateway_path}'

        try:
            payload, cache_hit = GatewayClient().get(
                gateway_path,
                filter_gateway_query(request.query_params),
            )
        except GatewayRequestError as exc:
            return Response({'detail': str(exc)}, status=exc.status_code)
        except GatewayError as exc:
            logger.warning(
                'TS4NFDI Gateway proxy failed path=%s status=%s',
                gateway_path,
                exc.status_code,
            )
            return Response({'detail': str(exc)}, status=exc.status_code)

        response = Response(payload)
        response['Cache-Control'] = 'private, max-age=60'
        response['X-TS4NFDI-Cache'] = 'hit' if cache_hit else 'miss'
        return response
