from rest_framework import serializers


class AnnotationListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1)


class AnnotationDetailQuerySerializer(serializers.Serializer):
    matcher = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=200,
    )
    target = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=500,
    )
