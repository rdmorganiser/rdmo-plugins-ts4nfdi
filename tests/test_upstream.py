import rdmo_ts4nfdi.upstream as upstream


def test_gateway_contract_requires_every_gateway_route_used_by_the_plugin(monkeypatch):
    paths = {path: {} for path in upstream.REQUIRED_GATEWAY_PATHS}
    monkeypatch.setattr(
        upstream,
        'fetch_json',
        lambda _url, _user_agent: {
            'openapi': '3.1.0',
            'info': {'version': 'test'},
            'paths': paths,
        },
    )

    result = upstream.check_gateway_contract('https://gateway.example/api-docs')

    assert result == 'Gateway OpenAPI 3.1.0 (test): required paths available.'


def test_gateway_contract_reports_entitysets_when_the_provider_route_disappears(monkeypatch):
    paths = {path: {} for path in upstream.REQUIRED_GATEWAY_PATHS - {'/entitysets'}}
    monkeypatch.setattr(
        upstream,
        'fetch_json',
        lambda _url, _user_agent: {'paths': paths},
    )

    try:
        upstream.check_gateway_contract('https://gateway.example/api-docs')
    except RuntimeError as exc:
        assert str(exc) == 'Gateway contract is missing required paths:\n  /entitysets'
    else:
        raise AssertionError('Expected the missing entity-set route to fail the contract check.')


def test_live_gateway_contract_checks_direct_edam_and_fairagro_resources(monkeypatch):
    responses = {
        'ols4/api/v2/ontologies/edam/entities': (
            {'elements': [{'iri': upstream.EDAM_SAMPLE_IRI}]},
            {'access-control-allow-origin': '*'},
        ),
        'search?query=xml': (
            [{'iri': upstream.EDAM_SAMPLE_IRI}],
            {'access-control-allow-origin': '*'},
        ),
        'collections/': ([{'id': upstream.FAIRAGRO_COLLECTION_ID}], {}),
        'entitysets': ([{'id': upstream.FAIRAGRO_ENTITYSET_ID}], {}),
        'ols4/api/v2/ontologies/agrovoc/entities': ({'elements': []}, {}),
    }

    def fetch(url, _user_agent, headers=None):
        if 'ols4/api/v2/ontologies/edam/entities' in url:
            assert headers == {'Origin': 'https://rdmo.example'}
        return next(
            response
            for suffix, response in responses.items()
            if suffix in url
        )

    monkeypatch.setattr(upstream, 'fetch_json_response', fetch)

    result = upstream.check_gateway_live_contract(
        'https://gateway.example',
        'https://rdmo.example',
    )

    assert result == (
        'Gateway live contract: EDAM OLS4 entity available; '
        'OLS4 and search CORS available for https://rdmo.example; '
        'FAIRagro collection and entity set available; '
        'AGROVOC OLS4 entity unavailable; keep the native annotation path.'
    )


def test_live_gateway_contract_requires_edam_cors(monkeypatch):
    monkeypatch.setattr(
        upstream,
        'fetch_json_response',
        lambda _url, _user_agent, _headers=None: ({'elements': [{'iri': upstream.EDAM_SAMPLE_IRI}]}, {}),
    )

    try:
        upstream.check_gateway_live_contract('https://gateway.example', 'https://rdmo.example')
    except RuntimeError as exc:
        assert str(exc) == 'Gateway EDAM OLS4 response does not expose a CORS allow-origin header.'
    else:
        raise AssertionError('Expected a missing EDAM CORS header to fail the live contract check.')


def test_live_gateway_contract_requires_search_cors(monkeypatch):
    responses = {
        'ols4/api/v2/ontologies/edam/entities': (
            {'elements': [{'iri': upstream.EDAM_SAMPLE_IRI}]},
            {'access-control-allow-origin': '*'},
        ),
        'search?query=xml': ([{'iri': upstream.EDAM_SAMPLE_IRI}], {}),
    }
    monkeypatch.setattr(
        upstream,
        'fetch_json_response',
        lambda url, _user_agent, _headers=None: next(
            response for suffix, response in responses.items() if suffix in url
        ),
    )

    try:
        upstream.check_gateway_live_contract('https://gateway.example', 'https://rdmo.example')
    except RuntimeError as exc:
        assert str(exc) == 'Gateway search response does not expose a CORS allow-origin header.'
    else:
        raise AssertionError('Expected a missing search CORS header to fail the live contract check.')


def test_live_gateway_contract_does_not_require_cors_without_a_browser_origin(monkeypatch):
    responses = {
        'ols4/api/v2/ontologies/edam/entities': ({'elements': [{'iri': upstream.EDAM_SAMPLE_IRI}]}, {}),
        'search?query=xml': ([{'iri': upstream.EDAM_SAMPLE_IRI}], {}),
        'collections/': ([{'id': upstream.FAIRAGRO_COLLECTION_ID}], {}),
        'entitysets': ([{'id': upstream.FAIRAGRO_ENTITYSET_ID}], {}),
        'ols4/api/v2/ontologies/agrovoc/entities': ({'elements': []}, {}),
    }
    monkeypatch.setattr(
        upstream,
        'fetch_json_response',
        lambda url, _user_agent, _headers=None: next(
            response for suffix, response in responses.items() if suffix in url
        ),
    )

    result = upstream.check_gateway_live_contract('https://gateway.example')

    assert 'CORS not checked (pass --origin with the RDMO browser origin)' in result
