from django.urls import path

from .api.views import AnnotationDetailView, AnnotationListV2View, AnnotationListView, GatewayProxyView

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
        'projects/<int:project_id>/annotations/<int:value_id>/',
        AnnotationDetailView.as_view(),
        name='annotation-detail',
    ),
    path(
        'projects/<int:project_id>/gateway/ols4/api/<path:gateway_path>',
        GatewayProxyView.as_view(),
        name='gateway-proxy',
    ),
]
