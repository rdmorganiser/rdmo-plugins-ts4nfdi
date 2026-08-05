from dataclasses import dataclass
from typing import Protocol

from .annotations import ResourceReference

SEMANTIC_MAPPING_RELATIONS = frozenset({'exact', 'close', 'broad', 'narrow', 'related', 'component'})
SEMANTIC_CURATION_STATUSES = frozenset({'draft', 'reviewed', 'deprecated'})


@dataclass(frozen=True, slots=True)
class OptionExternalIdProjectionPolicy:
    enabled: bool = False
    mapping_set_ids: tuple[str, ...] = ()
    relations: frozenset[str] = frozenset()
    curation_statuses: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class SemanticTarget:
    id: str
    iri: str
    label: str
    relation: str
    source: ResourceReference
    terminology: ResourceReference
    curation_status: str = 'draft'


@dataclass(frozen=True, slots=True)
class SemanticOption:
    id: str
    uri: str
    labels: tuple[tuple[str, str], ...]
    targets: tuple[SemanticTarget, ...] = ()
    selectable: bool = True

    def label(self, language: str | None = None) -> str:
        labels = dict(self.labels)
        if language:
            normalized_language = language.lower().replace('_', '-')
            if normalized_language in labels:
                return labels[normalized_language]
            base_language = normalized_language.partition('-')[0]
            if base_language in labels:
                return labels[base_language]
        return labels.get('en') or next(iter(labels.values()), self.id)


@dataclass(frozen=True, slots=True)
class SemanticOptionSet:
    id: str
    version: str
    options: tuple[SemanticOption, ...]
    source_name: str | None = None
    source_sha256: str | None = None

    def get(self, option_uri: str) -> SemanticOption | None:
        return next((option for option in self.options if option.uri == option_uri), None)


class SemanticOptionRegistry(Protocol):
    def get(self, mapping_set_id: str) -> SemanticOptionSet: ...
