import logging

from .base import TS4NFDIBaseProvider
from .utils import extract_results as extract_default_results
from .utils import get_first_value, option_badge, option_breadcrumb, option_description

logger = logging.getLogger(__name__)


class TS4NFDICollectionTerminologiesProvider(TS4NFDIBaseProvider):

    search = True
    refresh = False

    def get_options(self, project, search=None, user=None, site=None):
        provider_config = self.get_provider_config()
        payload = self.make_request(search, provider_config=provider_config)
        results = self.extract_results(payload) if payload is not None else []

        if not results and provider_config.get("fallback_endpoint"):
            fallback_config = self.get_fallback_provider_config(provider_config)
            payload = self.make_request(search, provider_config=fallback_config)
            results = self.extract_results(payload) if payload is not None else []

        if payload is None:
            return self.get_request_error_options(provider_config)

        filtered_results = self.filter_results(results, search)
        options = []

        logger.debug(
            "TS4NFDI collection terminologies provider '%s' search=%r result_count=%s filtered_result_count=%s",
            self.key,
            search,
            len(results),
            len(filtered_results),
        )

        for result in filtered_results:
            option = self.map_result_to_option(result, provider_config)
            if option:
                options.append(option)

        options = self.deduplicate_options(options, provider_config)
        options = self.exclude_selected_options(project, options, provider_config)
        return options[: provider_config.get("limit", 100)]

    def build_query_params(self, provider_config, search):
        query_params = {}

        if not provider_config.get("_collections_fallback"):
            collection_id = provider_config.get("collection_id")
            if collection_id:
                query_params[provider_config.get("collection_id_param", "collectionId")] = collection_id

            for config_key, default_param in (
                ("size", "size"),
                ("page", "page"),
            ):
                if provider_config.get(config_key) is not None:
                    param_name = provider_config.get(f"{config_key}_param", default_param)
                    query_params[param_name] = provider_config[config_key]

        if provider_config.get("server_side_search") and search:
            query_params[provider_config.get("search_param", "query")] = search

        extra_params = provider_config.get("extra_params", {})
        query_params.update(extra_params)

        return query_params

    def extract_results(self, payload):
        if isinstance(payload, dict):
            embedded = payload.get("_embedded")
            if isinstance(embedded, dict) and isinstance(embedded.get("ontologies"), list):
                return embedded["ontologies"]

            collection = payload.get("collection")
            if isinstance(collection, dict):
                return self.extract_collection_terminologies(collection)

            terminologies = payload.get("terminologies")
            if isinstance(terminologies, list):
                return terminologies

        results = extract_default_results(payload)
        collection_id = self.get_provider_config().get("collection_id")

        if collection_id:
            collection = self.find_collection(results, collection_id)
            if collection:
                return self.extract_collection_terminologies(collection)

        return results

    def find_collection(self, results, collection_id):
        for result in results:
            if not isinstance(result, dict):
                continue

            identifier = get_first_value(result, ("id", "uuid"))
            if identifier == collection_id:
                return result

        return None

    def extract_collection_terminologies(self, collection):
        terminologies = collection.get("terminologies")
        if not isinstance(terminologies, list):
            return []

        collection_metadata = {
            "collection_id": get_first_value(collection, ("id",)),
            "collection_label": get_first_value(collection, ("label",)),
        }
        results = []

        for terminology in terminologies:
            if not isinstance(terminology, dict):
                continue

            results.append({**terminology, **collection_metadata})

        return results

    def get_fallback_provider_config(self, provider_config):
        fallback_config = {
            **provider_config,
            "endpoint": provider_config["fallback_endpoint"],
            "_collections_fallback": True,
        }
        fallback_api_url = provider_config.get("fallback_api_url")
        if fallback_api_url:
            fallback_config["api_url"] = fallback_api_url
        else:
            fallback_config.pop("api_url", None)

        return fallback_config

    def filter_results(self, results, search):
        if not search:
            return results

        normalized_search = str(search).strip().casefold()
        if not normalized_search:
            return results

        return [
            result
            for result in results
            if self.terminology_matches(result, normalized_search)
        ]

    def terminology_matches(self, result, normalized_search):
        if not isinstance(result, dict):
            return False

        values = [
            get_first_value(result, ("ontologyId",)),
            get_first_value(result, ("URI", "uri")),
            get_first_value(result, ("label",)),
            get_first_value(result, ("source",)),
            get_first_value(result, ("type",)),
            get_first_value(result, ("config.title",)),
            get_first_value(result, ("config.description",)),
            get_first_value(result, ("collection_label",)),
        ]

        return any(
            value and normalized_search in value.casefold()
            for value in values
        )

    def map_result_to_option(self, result, provider_config):
        if not isinstance(result, dict):
            return None

        identifier = get_first_value(
            result,
            provider_config.get(
                "id_fields",
                ("URI", "config.id", "uri", "ontologyId", "id"),
            ),
        )
        label = get_first_value(
            result,
            provider_config.get(
                "label_fields",
                ("config.title", "label", "ontologyId", "name", "title"),
            ),
        )

        if not identifier or not label:
            return None

        option = {
            "id": identifier,
            "text": label,
        }

        ontology_id = get_first_value(result, ("ontologyId", "label"))
        if ontology_id:
            option["ontology_id"] = ontology_id

        help_text = self.build_help_html(result, provider_config)
        if help_text:
            option["help"] = help_text

        return option

    def build_help_html(self, result, provider_config):
        collection_label = (
            get_first_value(result, ("collection_label",))
            or provider_config.get("collection_label")
        )
        ontology_id = get_first_value(result, ("ontologyId", "label"))
        source = get_first_value(result, ("source",))
        terminology_type = get_first_value(result, ("type",))
        uri = get_first_value(result, ("URI", "uri", "config.id"))
        version = get_first_value(result, ("config.version",))
        description = get_first_value(
            result,
            provider_config.get(
                "help_fields",
                ("config.description", "description", "definition", "summary"),
            ),
        )

        parts = []
        badges = []

        if collection_label:
            badges.append(option_badge(collection_label, "collection"))

        if ontology_id:
            badges.append(option_badge(ontology_id, "ontology"))

        if source:
            badges.append(option_badge(source, "source"))

        if terminology_type:
            badges.append(option_badge(terminology_type, "term"))

        breadcrumb = option_breadcrumb(badges)
        if breadcrumb:
            parts.append(breadcrumb)

        details = []
        if description:
            details.append(description)
        if uri:
            details.append(f"uri: {uri}")
        if version:
            details.append(f"version: {version}")

        description_html = option_description(details)
        if description_html:
            parts.append(description_html)

        return "".join(parts) or None
