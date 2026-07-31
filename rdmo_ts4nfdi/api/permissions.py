from rest_framework.permissions import SAFE_METHODS, BasePermission


class CanViewProject(BasePermission):
    """Apply the same project-viewing policy used by the RDMO project API."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.method in SAFE_METHODS
        )

    def has_object_permission(self, request, view, project):
        return (
            request.user.has_perm('projects.view_project')
            or request.user.has_perm(
                'projects.view_project_object',
                project,
            )
        )
