import logging

from .base import TS4NFDIBaseProvider
from .utils import (
    extract_results,
    get_first_value,
    normalize_list,
    option_badge,
    option_breadcrumb,
    option_description,
    option_separator,
)

logger = logging.getLogger(__name__)


class TS4NFDIOntologiesProvider(TS4NFDIBaseProvider):

    search = True
    refresh = False

    def get_options(self, project, search=None, user=None, site=None):
        if not search:
            return []

        provider_config = self.get_provider_config()
        payload = self.make_request(search, provider_config=provider_config)
        if payload is None:
            return self.get_request_error_options(provider_config)

        results = self.filter_results(extract_results(payload), provider_config)
        options = []

        logger.debug(
            "TS4NFDI ontology provider '%s' search=%r filtered result_count=%s",
            self.key,
            search,
            len(results),
        )

        for result in results:
            option = self.map_result_to_option(result, provider_config)
            if option:
                options.append(option)

        options = self.exclude_selected_options(project, options, provider_config)
        return options[: provider_config.get("limit", 20)]

    def build_query_params(self, provider_config, search):
        query_params = {
            provider_config.get("search_param", "query"): search,
        }

        if provider_config.get("limit") is not None and provider_config.get("limit_param"):
            query_params[provider_config.get("limit_param", "limit")] = provider_config["limit"]

        for config_key, default_param in (
            ("database", "database"),
            ("collection_id", "collectionId"),
            ("target_db_schema", "targetDbSchema"),
        ):
            if provider_config.get(config_key):
                query_params[provider_config.get(f"{config_key}_param", default_param)] = provider_config[config_key]

        display = provider_config.get("display", [])
        if display:
            query_params[provider_config.get("display_param", "display")] = ",".join(display)

        terminologies = provider_config.get("terminologies", [])
        if terminologies and provider_config.get("terminologies_param"):
            query_params[provider_config["terminologies_param"]] = ",".join(terminologies)

        entity_types = provider_config.get("entity_types", [])
        if entity_types and provider_config.get("entity_types_param"):
            query_params[provider_config["entity_types_param"]] = ",".join(entity_types)

        extra_params = provider_config.get("extra_params", {})
        query_params.update(extra_params)

        return query_params

    def filter_results(self, results, provider_config):
        return [
            result
            for result in results
            if self.matches_ontology_filter(result, provider_config)
            and self.matches_iri_prefix_filter(result, provider_config)
            and self.matches_type_filter(result, provider_config)
        ]

    def matches_ontology_filter(self, result, provider_config):
        ontologies = provider_config.get("ontologies") or provider_config.get("terminologies")
        ontologies = {ontology.lower() for ontology in normalize_list(ontologies)}

        if not ontologies:
            return True

        ontology_fields = provider_config.get(
            "ontology_fields",
            ("ontology", "ontology_iri", "source_name", "sourceName", "short_form", "backend_type"),
        )
        values = [
            get_first_value(result, (field,))
            for field in ontology_fields
        ]

        return any(
            value and any(ontology == value.lower() or ontology in value.lower() for ontology in ontologies)
            for value in values
        )

    def matches_iri_prefix_filter(self, result, provider_config):
        prefixes = provider_config.get("iri_prefixes") or provider_config.get("iri_prefix")
        prefixes = tuple(normalize_list(prefixes))

        if not prefixes:
            return True

        identifier = get_first_value(result, provider_config.get("id_fields", self.DEFAULT_ID_FIELDS))

        return bool(identifier and identifier.startswith(prefixes))

    def matches_type_filter(self, result, provider_config):
        entity_types = normalize_list(provider_config.get("entity_types"))

        if not entity_types or provider_config.get("entity_types_param"):
            return True

        result_type = get_first_value(result, ("type", "@type"))

        if not result_type:
            return True

        normalized_result_type = result_type.lower()
        return any(entity_type.lower() in normalized_result_type for entity_type in entity_types)

    def map_result_to_option(self, result, provider_config):
        if not isinstance(result, dict):
            return None

        identifier = get_first_value(result, provider_config.get("id_fields", self.DEFAULT_ID_FIELDS))
        label = get_first_value(result, provider_config.get("label_fields", self.DEFAULT_LABEL_FIELDS))

        if not identifier or not label:
            return None

        help_text = self.build_help_html(result, provider_config)

        option = {
            "id": identifier,
            "text": label,
        }

        if help_text:
            option["help"] = help_text

        return option

    def build_help_html(self, result, provider_config):
        source = provider_config.get("source") or {}
        source_name = (
            source.get("label")
            or get_first_value(result, ("source_name", "sourceName"))
        )
        source_url = source.get("url") or get_first_value(result, ("source",))
        ontology_name = get_first_value(
            result,
            provider_config.get("ontology_fields", ("ontology_name", "ontology")),
        )
        short_form = get_first_value(
            result,
            provider_config.get("short_form_fields", ("short_form", "obo_id")),
        )
        description = get_first_value(
            result,
            provider_config.get("help_fields", self.DEFAULT_HELP_FIELDS),
        )

        parts = []

        if source_name or ontology_name or short_form:
            badges = []
            if source_name:
                badges.append(option_badge(source_name, "source", title=source_url))
            if ontology_name:
                if badges:
                    badges.append(option_separator())
                badges.append(option_badge(ontology_name, "ontology"))
            if short_form:
                if badges:
                    badges.append(option_separator())
                badges.append(option_badge(short_form, "term"))
            parts.append(option_breadcrumb(badges))

        description_html = option_description([description])
        if description_html:
            parts.append(description_html)

        return "".join(parts) or None
