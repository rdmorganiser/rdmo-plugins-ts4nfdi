from django.urls import path

from .api.views import (
    AnnotationDetailView,
    AnnotationListV2View,
    AnnotationListView,
    EntitySetProvenanceView,
    GatewayProxyView,
    GatewaySearchProxyView,
    ProviderResourceDetailView,
)

app_name = 'rdmo_ts4nfdi'

urlpatterns = [
    path(
        'projects/<int:project_id>/annotations/',
        AnnotationListView.as_view(),
        name='annotation-list',
    ),
    path(
        'projects/<int:project_id>/annotations/v2/',
        AnnotationListV2View.as_view(),
        name='annotation-list-v2',
    ),
    path(
        'projects/<int:project_id>/annotations/v2/<int:value_id>/entityset-provenance/',
        EntitySetProvenanceView.as_view(),
        name='entityset-provenance',
    ),
    path(
        'projects/<int:project_id>/annotations/v2/<int:value_id>/provider-resource/',
        ProviderResourceDetailView.as_view(),
        name='provider-resource-detail',
    ),
    path(
        'projects/<int:project_id>/annotations/<int:value_id>/',
        AnnotationDetailView.as_view(),
        name='annotation-detail',
    ),
    path(
        'projects/<int:project_id>/gateway/search',
        GatewaySearchProxyView.as_view(),
        name='gateway-search-proxy',
    ),
    path(
        'projects/<int:project_id>/gateway/ols4/api/<path:gateway_path>',
        GatewayProxyView.as_view(),
        name='gateway-proxy',
    ),
]
