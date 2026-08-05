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

    def target_iri(self, option_uri: str | None) -> str | None:
        if not self.policy.enabled or not option_uri:
            return None

        identifiers = set()
        for mapping_set_id in self.policy.mapping_set_ids:
            option = self.registry.get(mapping_set_id).get(option_uri)
            if option is None or len(option.targets) != 1:
                continue

            target = option.targets[0]
            if (
                target.relation in self.policy.relations
                and target.curation_status in self.policy.curation_statuses
            ):
                identifiers.add(target.iri)

        return next(iter(identifiers)) if len(identifiers) == 1 else None

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
