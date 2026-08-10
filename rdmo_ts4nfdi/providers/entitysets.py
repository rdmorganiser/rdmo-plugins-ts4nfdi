import logging

from django.utils.translation import get_language

from rdmo_ts4nfdi.config import load_source_configs

from .base import TS4NFDIBaseProvider
from .utils import option_badge, option_breadcrumb, option_description, option_separator

logger = logging.getLogger(__name__)


class TS4NFDIEntitySetProvider(TS4NFDIBaseProvider):
    """Expose the entities from one configured TS4NFDI entity set as RDMO options."""

    search = False
    refresh = False

    def get_options(self, project, search=None, user=None, site=None):
        provider_config = self.get_provider_config()
        entityset_id = str(provider_config.get('entityset_id') or '').strip()
        if not entityset_id:
            raise RuntimeError(
                f"TS4NFDI provider '{self.key}' requires an entityset_id."
            )

        payload = self.make_request(provider_config=provider_config)
        if payload is None:
            return self.get_request_error_options(provider_config)

        entityset = self.find_entityset(payload, entityset_id)
        if entityset is None:
            logger.warning(
                "TS4NFDI entity-set provider '%s' did not find configured entity set %s.",
                self.key,
                entityset_id,
            )
            return []

        language = get_language() or 'en'
        sources = load_source_configs()
        options = []
        for entity in entityset.get('entities', []):
            option = self.map_entity_to_option(entity, language, sources)
            if option:
                options.append(option)

        return options

    @staticmethod
    def find_entityset(payload, entityset_id):
        if isinstance(payload, dict):
            if str(payload.get('id') or '').strip() == entityset_id:
                return payload
            entitysets = (
                payload.get('entitysets')
                or payload.get('items')
                or payload.get('results')
                or []
            )
        elif isinstance(payload, list):
            entitysets = payload
        else:
            return None

        return next(
            (
                entityset
                for entityset in entitysets
                if isinstance(entityset, dict)
                and str(entityset.get('id') or '').strip() == entityset_id
            ),
            None,
        )

    @classmethod
    def map_entity_to_option(cls, entity, language, sources):
        if not isinstance(entity, dict):
            return None

        iri = cls.normalize_string(entity.get('uri'))
        if not iri:
            return None

        label = cls.localized_text(entity.get('label'), language) or iri
        option = {
            'id': iri,
            'text': label,
        }

        help_html = cls.build_help_html(entity, label, language, sources)
        if help_html:
            option['help'] = help_html
        return option

    @classmethod
    def build_help_html(cls, entity, label, language, sources):
        provider_id = cls.normalize_string(entity.get('provider'))
        source = sources.get(provider_id, {}) if provider_id else {}
        source_label = source.get('label') or provider_id
        terminology = cls.normalize_string(entity.get('terminology'))

        badges = []
        if source_label:
            badges.append(
                option_badge(
                    source_label,
                    'source',
                    title=source.get('url'),
                )
            )
        if terminology:
            if badges:
                badges.append(option_separator())
            badges.append(option_badge(terminology, 'ontology'))
        if label:
            if badges:
                badges.append(option_separator())
            badges.append(
                option_badge(
                    label,
                    'term',
                    title=cls.normalize_string(entity.get('uri')),
                )
            )

        parts = []
        breadcrumb = option_breadcrumb(badges)
        if breadcrumb:
            parts.append(breadcrumb)

        definition = cls.localized_text(entity.get('definition'), language)
        description = option_description([definition] if definition else [])
        if description:
            parts.append(description)

        return ''.join(parts) or None

    @classmethod
    def localized_text(cls, values, language):
        if isinstance(values, str):
            return cls.normalize_string(values)

        if isinstance(values, dict):
            if 'value' in values or 'label' in values:
                values = [values]
            else:
                values = [
                    {'lang': key, 'value': value}
                    for key, value in values.items()
                ]
        if not isinstance(values, list):
            return None

        candidates = []
        for item in values:
            if isinstance(item, str):
                value = cls.normalize_string(item)
                if value:
                    candidates.append((None, value))
                continue
            if not isinstance(item, dict):
                continue

            value = cls.normalize_string(item.get('value') or item.get('label'))
            if not value:
                continue
            item_language = cls.normalize_language(item.get('lang'))
            candidates.append((item_language, value))

        if not candidates:
            return None

        requested = cls.normalize_language(language) or 'en'
        primary = requested.split('-', 1)[0]
        preferences = tuple(dict.fromkeys((requested, primary, 'en', None)))
        for preference in preferences:
            for candidate_language, value in candidates:
                if candidate_language == preference:
                    return value

        return candidates[0][1]

    @staticmethod
    def normalize_string(value):
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def normalize_language(value):
        if value is None:
            return None
        normalized = str(value).strip().replace('_', '-').casefold()
        return normalized or None
