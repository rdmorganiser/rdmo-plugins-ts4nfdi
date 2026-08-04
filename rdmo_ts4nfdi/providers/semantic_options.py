from django.utils.translation import get_language

from rdmo.options.providers import Provider

from rdmo_ts4nfdi.domain import SemanticOption
from rdmo_ts4nfdi.semantic_options import PackageSemanticOptionRegistry

from .utils import option_badge, option_breadcrumb, option_description, option_separator


class SemanticOptionSetProvider(Provider):
    """Expose a versioned curated mapping set as dynamic RDMO options."""

    search = False
    refresh = False
    mapping_set_id: str | None = None

    def get_options(self, project, search=None, user=None, site=None):
        if not self.mapping_set_id:
            raise RuntimeError(f'{type(self).__name__}.mapping_set_id must be configured.')

        mapping_set = PackageSemanticOptionRegistry().get(self.mapping_set_id)
        language = get_language()
        return [
            {
                'id': option.uri,
                'text': option.label(language),
                'help': self.build_help_html(option, mapping_set.version),
            }
            for option in mapping_set.options
            if option.selectable
        ]

    @staticmethod
    def build_help_html(option: SemanticOption, mapping_version: str) -> str:
        if not option.targets:
            return option_description(
                ['No related terminology concept is available for this option yet.']
            )

        parts = []
        for target in option.targets:
            badges = [
                option_badge(target.source.label or target.source.id or 'Source', 'source', title=target.source.url),
                option_separator(),
                option_badge(
                    target.terminology.label or target.terminology.id or 'Terminology',
                    'ontology',
                    title=target.terminology.iri,
                ),
                option_separator(),
                option_badge(target.label, 'term', title=target.iri),
            ]
            parts.append(option_breadcrumb(badges))

        parts.append(
            option_description(
                [
                    'Related terminology concept.'
                    if len(option.targets) == 1
                    else 'Related terminology concepts.'
                ]
            )
        )
        return ''.join(parts)


class FAIRAgroDataGenerationOptionSetProvider(SemanticOptionSetProvider):
    mapping_set_id = 'fairagro-data-generation'
