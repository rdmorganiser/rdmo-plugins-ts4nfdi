import json
from importlib.resources import files
from typing import Any

from rdmo_ts4nfdi.config import load_source_configs
from rdmo_ts4nfdi.domain import (
    ResourceReference,
    SemanticOption,
    SemanticOptionSet,
    SemanticTarget,
)
from rdmo_ts4nfdi.utils import is_http_iri, require_string

MANIFEST_PACKAGE = 'rdmo_ts4nfdi.data.semantic_option_sets'
MANIFESTS = {
    'fairagro-data-generation': 'fairagro_data_generation.json',
}
MAPPING_RELATIONS = frozenset({'exact', 'close', 'broad', 'narrow', 'related', 'component'})
CURATION_STATUSES = frozenset({'draft', 'reviewed', 'deprecated'})


class PackageSemanticOptionRegistry:
    """Load reviewed option-to-terminology mappings shipped with the plugin."""

    def __init__(self):
        self._cache: dict[str, SemanticOptionSet] = {}

    def get(self, mapping_set_id: str) -> SemanticOptionSet:
        if mapping_set_id not in MANIFESTS:
            raise LookupError(f"Unknown semantic option set '{mapping_set_id}'.")
        if mapping_set_id not in self._cache:
            resource = files(MANIFEST_PACKAGE).joinpath(MANIFESTS[mapping_set_id])
            payload = json.loads(resource.read_text(encoding='utf-8'))
            self._cache[mapping_set_id] = self._normalize(payload, mapping_set_id)
        return self._cache[mapping_set_id]

    def _normalize(self, payload: Any, expected_id: str) -> SemanticOptionSet:
        if not isinstance(payload, dict):
            raise RuntimeError(f"Semantic option set '{expected_id}' must contain a JSON object.")

        mapping_set_id = require_string(payload, 'id')
        if mapping_set_id != expected_id:
            raise RuntimeError(
                f"Semantic option set id '{mapping_set_id}' does not match requested id '{expected_id}'."
            )

        raw_options = payload.get('options')
        if not isinstance(raw_options, list):
            raise RuntimeError(f"Semantic option set '{mapping_set_id}' options must be a list.")

        sources = load_source_configs()
        options = tuple(self._normalize_option(raw_option, mapping_set_id, sources) for raw_option in raw_options)
        option_ids = [option.id for option in options]
        option_uris = [option.uri for option in options]
        if len(option_ids) != len(set(option_ids)):
            raise RuntimeError(f"Semantic option set '{mapping_set_id}' contains duplicate option ids.")
        if len(option_uris) != len(set(option_uris)):
            raise RuntimeError(f"Semantic option set '{mapping_set_id}' contains duplicate option URIs.")

        return SemanticOptionSet(
            id=mapping_set_id,
            version=require_string(payload, 'version'),
            options=options,
            source_name=_optional_string(payload.get('source_name')),
            source_sha256=_optional_string(payload.get('source_sha256')),
        )

    def _normalize_option(
        self,
        payload: Any,
        mapping_set_id: str,
        sources: dict[str, dict[str, str | None]],
    ) -> SemanticOption:
        if not isinstance(payload, dict):
            raise RuntimeError(f"Semantic option set '{mapping_set_id}' contains a non-object option.")

        option_id = require_string(payload, 'id')
        option_uri = require_string(payload, 'uri')
        if not is_http_iri(option_uri):
            raise RuntimeError(f"Semantic option '{option_id}' URI must be an HTTP(S) IRI.")

        raw_labels = payload.get('labels')
        if not isinstance(raw_labels, dict) or not raw_labels:
            raise RuntimeError(f"Semantic option '{option_id}' labels must be a non-empty object.")
        labels = tuple(
            (language.lower().replace('_', '-'), str(label).strip())
            for language, label in raw_labels.items()
            if str(language).strip() and str(label).strip()
        )
        if not labels:
            raise RuntimeError(f"Semantic option '{option_id}' must contain at least one non-empty label.")

        raw_targets = payload.get('targets', [])
        if not isinstance(raw_targets, list):
            raise RuntimeError(f"Semantic option '{option_id}' targets must be a list.")
        targets = tuple(self._normalize_target(target, option_id, sources) for target in raw_targets)
        target_ids = [target.id for target in targets]
        if len(target_ids) != len(set(target_ids)):
            raise RuntimeError(f"Semantic option '{option_id}' contains duplicate target ids.")

        selectable = payload.get('selectable', True)
        if not isinstance(selectable, bool):
            raise RuntimeError(f"Semantic option '{option_id}' selectable must be a boolean.")

        return SemanticOption(
            id=option_id,
            uri=option_uri,
            labels=labels,
            targets=targets,
            selectable=selectable,
        )

    def _normalize_target(
        self,
        payload: Any,
        option_id: str,
        sources: dict[str, dict[str, str | None]],
    ) -> SemanticTarget:
        if not isinstance(payload, dict):
            raise RuntimeError(f"Semantic option '{option_id}' contains a non-object target.")

        target_id = require_string(payload, 'id')
        target_iri = require_string(payload, 'iri')
        if not is_http_iri(target_iri):
            raise RuntimeError(f"Semantic target '{target_id}' IRI must be an HTTP(S) IRI.")

        relation = require_string(payload, 'relation')
        if relation not in MAPPING_RELATIONS:
            raise RuntimeError(f"Semantic target '{target_id}' relation must be one of {sorted(MAPPING_RELATIONS)}.")

        curation_status = _optional_string(payload.get('curation_status')) or 'draft'
        if curation_status not in CURATION_STATUSES:
            raise RuntimeError(
                f"Semantic target '{target_id}' curation_status must be one of {sorted(CURATION_STATUSES)}."
            )

        source_key = require_string(payload, 'source_key')
        if source_key not in sources:
            raise RuntimeError(f"Semantic target '{target_id}' references unknown source_key '{source_key}'.")
        source = ResourceReference(**sources[source_key])

        raw_terminology = payload.get('terminology')
        if not isinstance(raw_terminology, dict):
            raise RuntimeError(f"Semantic target '{target_id}' terminology must be an object.")
        terminology = ResourceReference(
            id=require_string(raw_terminology, 'id'),
            label=require_string(raw_terminology, 'label'),
            iri=_optional_string(raw_terminology.get('iri')),
        )

        return SemanticTarget(
            id=target_id,
            iri=target_iri,
            label=require_string(payload, 'label'),
            relation=relation,
            source=source,
            terminology=terminology,
            curation_status=curation_status,
        )


def _optional_string(value: Any) -> str | None:
    normalized = str(value).strip() if value is not None else ''
    return normalized or None
