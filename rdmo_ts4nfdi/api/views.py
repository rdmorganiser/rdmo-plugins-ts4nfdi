import logging

from django.shortcuts import get_object_or_404

from rest_framework.exceptions import NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from rdmo.projects.models import Project

from rdmo_ts4nfdi.api.permissions import CanViewProject
from rdmo_ts4nfdi.composition import build_annotation_service
from rdmo_ts4nfdi.integrations.ts4nfdi.gateway import (
    GatewayClient,
    GatewayError,
    GatewayRequestError,
    GatewayTimeout,
    filter_gateway_query,
)

from .serializers import (
    AnnotationDetailQuerySerializer,
    AnnotationListQuerySerializer,
)

logger = logging.getLogger(__name__)


class ProjectAPIView(GenericAPIView):
    permission_classes = (CanViewProject,)
    queryset = Project.objects.all()

    lookup_field = 'pk'
    lookup_url_kwarg = 'project_id'

    def get_queryset(self):
        return (
            Project.objects
            .filter_user(self.request.user)
            .select_related('catalog')
            .distinct()
        )

    def get_project(self):
        return self.get_object()


class AnnotationListView(ProjectAPIView):
    def get_payload(self, project, page):
        return build_annotation_service().list_page(project, page)

    def get(self, request, project_id):
        project = self.get_project()

        query = AnnotationListQuerySerializer(
            data=request.query_params,
        )
        query.is_valid(raise_exception=True)
        page_id = query.validated_data['page']

        if project.catalog is None:
            raise NotFound()

        project.catalog.prefetch_elements()
        page = project.catalog.get_page(page_id)
        if page is None:
            raise NotFound()

        payload = self.get_payload(project, page)
        return Response(payload.to_dict())


class AnnotationListV2View(AnnotationListView):
    def get_payload(self, project, page):
        return build_annotation_service().list_page_v2(project, page)


class AnnotationDetailView(ProjectAPIView):
    def get(self, request, project_id, value_id):
        project = self.get_project()

        query = AnnotationDetailQuerySerializer(
            data=request.query_params,
        )
        query.is_valid(raise_exception=True)

        value = get_object_or_404(
            project.values
            .filter(snapshot=None)
            .select_related('attribute', 'option'),
            pk=value_id,
        )

        try:
            payload = build_annotation_service().detail(
                project,
                value,
                matcher_id=query.validated_data.get('matcher'),
            )
        except LookupError as exc:
            raise NotFound(
                'No annotation applies to this value.'
            ) from exc

        return Response(payload.to_dict())


class GatewayProxyView(ProjectAPIView):

    def get(self, request, project_id, gateway_path):
        self.get_project()

        path = f'ols4/api/{gateway_path}'

        try:
            payload, cache_hit = GatewayClient().get(
                path,
                filter_gateway_query(request.query_params),
            )
        except GatewayRequestError as exc:
            return Response(
                {'detail': str(exc)},
                status=exc.status_code,
            )
        except GatewayTimeout as exc:
            logger.warning(
                'TS4NFDI Gateway proxy timed out '
                'path=%s upstream_status=%s response_status=%s project=%s user=%s',
                path,
                exc.status_code,
                exc.proxy_status_code,
                project_id,
                request.user.pk,
            )
            response = Response(
                {
                    'detail': str(exc),
                    'code': 'gateway_timeout',
                    'upstream_status': exc.status_code,
                    'retryable': True,
                },
                status=exc.proxy_status_code,
            )
            response['Cache-Control'] = 'no-store'
            response['X-TS4NFDI-Upstream-Status'] = str(exc.status_code)
            return response
        except GatewayError as exc:
            logger.warning(
                'TS4NFDI Gateway proxy failed '
                'path=%s status=%s project=%s user=%s',
                path,
                exc.status_code,
                project_id,
                request.user.pk,
            )
            return Response(
                {'detail': str(exc)},
                status=exc.status_code,
            )

        response = Response(payload)
        response['Cache-Control'] = 'private, max-age=60'
        response['X-TS4NFDI-Cache'] = (
            'hit' if cache_hit else 'miss'
        )
        return response
