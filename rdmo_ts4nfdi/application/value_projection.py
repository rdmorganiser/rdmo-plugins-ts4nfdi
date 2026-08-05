from rdmo_ts4nfdi.domain import OptionExternalIdProjectionPolicy, SemanticOptionRegistry


class SemanticOptionExternalIdProjector:
    """Project one curated concept IRI into RDMO's scalar external-id field."""

    def __init__(
        self,
        registry: SemanticOptionRegistry,
        policy: OptionExternalIdProjectionPolicy,
    ):
        self.registry = registry
        self.policy = policy
        self._target_iris = self._build_target_iris()

    def target_iri(self, option_uri: str | None) -> str | None:
        if not self.policy.enabled or not option_uri:
            return None
        return self._target_iris.get(option_uri)

    def option_identifier(self, option_uri: str) -> str:
        """Return the identifier RDMO must use for selecting and storing an option."""

        return self.target_iri(option_uri) or option_uri

    def _build_target_iris(self) -> dict[str, str]:
        if not self.policy.enabled:
            return {}

        identifiers_by_option: dict[str, set[str]] = {}
        for mapping_set_id in self.policy.mapping_set_ids:
            for option in self.registry.get(mapping_set_id).options:
                if len(option.targets) != 1:
                    continue

                target = option.targets[0]
                if (
                    target.relation in self.policy.relations
                    and target.curation_status in self.policy.curation_statuses
                ):
                    identifiers_by_option.setdefault(option.uri, set()).add(target.iri)

        return {
            option_uri: next(iter(identifiers))
            for option_uri, identifiers in identifiers_by_option.items()
            if len(identifiers) == 1
        }

    def project(
        self,
        *,
        option_uri: str | None,
        external_id: str,
        previous_option_uri: str | None = None,
    ) -> str:
        previous_managed_id = self.target_iri(previous_option_uri)

        # A non-empty identifier that is not the previous projection belongs to
        # RDMO, an import, or another integration and must remain untouched.
        if external_id and external_id != previous_managed_id:
            return external_id

        return self.target_iri(option_uri) or ''

    def project_provider_external_id(self, external_id: str) -> str:
        """Replace a provider's local option URI while retaining all other ids."""

        return self.option_identifier(external_id)

    def project_value(
        self,
        *,
        option_uri: str | None,
        external_id: str,
        previous_option_uri: str | None = None,
    ) -> str:
        if option_uri:
            return self.project(
                option_uri=option_uri,
                external_id=external_id,
                previous_option_uri=previous_option_uri,
            )
        return self.project_provider_external_id(external_id)
