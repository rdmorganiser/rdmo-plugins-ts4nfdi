import logging
from hashlib import sha256

from django.core.cache import cache
from django.utils.translation import get_language

from rdmo_ts4nfdi.config import load_source_configs
from rdmo_ts4nfdi.integrations.ts4nfdi.provider import GatewayProviderClient

from .base import TS4NFDIBaseProvider
from .utils import option_badge, option_breadcrumb, option_description, option_separator

logger = logging.getLogger(__name__)


class TS4NFDIEntitySetProvider(TS4NFDIBaseProvider):
    """Expose the entities from one configured TS4NFDI entity set as RDMO options."""

    # This is intentionally search-backed although the temporary Gateway
    # endpoint returns a list.  The bounded list is cached and filtered here,
    # avoiding a full remote request for every debounced keystroke.
    search = True
    refresh = False

    def get_options(self, project, search=None, user=None, site=None):
        if not search:
            return []

        provider_config = self.get_provider_config()
        entityset_id = str(provider_config.get('entityset_id') or '').strip()
        if not entityset_id:
            raise RuntimeError(
                f"TS4NFDI provider '{self.key}' requires an entityset_id."
            )

        payload = self.get_cached_payload(provider_config)
        if payload is None:
            return self.with_free_text_candidate(
                search,
                self.get_request_error_options(provider_config),
                provider_config,
            )

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

        filtered_options = [
            option for option in options if self.option_matches_search(option, search)
        ]
        return self.with_free_text_candidate(
            search,
            filtered_options,
            provider_config,
            all_options=options,
        )

    def get_cached_payload(self, provider_config):
        request_url = GatewayProviderClient.prepare_request_url(provider_config, {})
        cache_key = 'rdmo-ts4nfdi:provider-entityset:' + sha256(
            request_url.encode('utf-8')
        ).hexdigest()
        timeout = provider_config.get('entityset_cache_timeout', 300)

        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 300

        if timeout > 0:
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                return cached_payload

        payload = self.make_request(provider_config=provider_config)
        if payload is not None and timeout > 0:
            cache.set(cache_key, payload, timeout)
        return payload

    @staticmethod
    def option_matches_search(option, search):
        query = str(search).strip().casefold()
        if not query:
            return False
        return any(
            query in str(option.get(field) or '').casefold()
            for field in ('id', 'text')
        )

    @staticmethod
    def find_entityset(payload, entityset_id):
        # Temporary compatibility path.  Replace this list lookup with the
        # Gateway's dedicated GET /entitysets/{uuid} response once deployed.
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
