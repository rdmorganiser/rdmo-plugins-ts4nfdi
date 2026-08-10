import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from rdmo_ts4nfdi.vendor import load_tss_vendor_manifest

PACKAGE_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PACKAGE_ROOT / 'vendor/terminology_service_suite.json'
STATIC_ROOT = PACKAGE_ROOT / 'static'
PACKAGE_NAME = '@ts4nfdi/terminology-service-suite-js'
DEFAULT_REGISTRY = 'https://registry.npmjs.org'
DEFAULT_OPENAPI_URL = 'https://terminology.services.base4nfdi.de/api-gateway/v3/api-docs'
DEFAULT_GATEWAY_URL = 'https://terminology.services.base4nfdi.de/api-gateway'
FAIRAGRO_COLLECTION_ID = 'ff5491d1-d0a9-481e-ac90-0fad065fa097'
FAIRAGRO_ENTITYSET_ID = 'fc45621d-7e40-47ce-9616-4133f0b54edf'
EDAM_SAMPLE_IRI = 'http://edamontology.org/format_2332'
AGROVOC_SAMPLE_IRI = 'http://aims.fao.org/aos/agrovoc/c_4826'
REQUIRED_GATEWAY_PATHS = {
    '/collections/',
    '/entitysets',
    '/search',
    '/ols4/api/ontologies/{onto}',
    '/ols4/api/ontologies/{onto}/terms',
    '/ols4/api/v2/entities',
    '/ols4/api/v2/ontologies/{onto}',
    '/ols4/api/v2/ontologies/{onto}/classes',
    '/ols4/api/v2/ontologies/{onto}/individuals',
    '/ols4/api/v2/ontologies/{onto}/properties',
}


def read_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))


def fetch_json(url, user_agent):
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': user_agent})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_json_response(url, user_agent, headers=None):
    request_headers = {'Accept': 'application/json', 'User-Agent': user_agent}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response), {
            key.lower(): value for key, value in response.headers.items()
        }


def fetch_bytes(url):
    request = Request(url, headers={'Accept': 'application/octet-stream', 'User-Agent': 'rdmo-ts4nfdi-vendor'})
    with urlopen(request, timeout=60) as response:
        return response.read()


def package_metadata(registry, version):
    encoded_package = quote(PACKAGE_NAME, safe='')
    selector = 'latest' if version is None else quote(version, safe='')
    return fetch_json(
        f'{registry.rstrip("/")}/{encoded_package}/{selector}',
        'rdmo-ts4nfdi-vendor',
    )


def verify_archive_integrity(archive, integrity):
    try:
        algorithm, expected = integrity.split('-', 1)
        actual = base64.b64encode(hashlib.new(algorithm, archive).digest()).decode('ascii')
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f'Unsupported npm integrity value: {integrity!r}') from exc

    if not hmac.compare_digest(actual, expected):
        raise RuntimeError('The downloaded npm archive does not match its published integrity value.')


def read_assets(archive, manifest):
    assets = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
        for name, asset in manifest['assets'].items():
            archive_path = asset['archive_path']
            member = package.getmember(archive_path)
            source = package.extractfile(member)
            if not member.isfile() or source is None:
                raise RuntimeError(f'TSS asset is not a regular file: {archive_path}')
            assets[name] = source.read()
    return assets


def asset_metadata(data):
    sha256 = hashlib.sha256(data).hexdigest()
    integrity = base64.b64encode(hashlib.sha256(data).digest()).decode('ascii')
    return {'sha256': sha256, 'integrity': f'sha256-{integrity}'}


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.', delete=False) as output:
            temporary_path = Path(output.name)
            output.write(data)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def display_path(path):
    try:
        return path.relative_to(PACKAGE_ROOT.parent)
    except ValueError:
        return path


def verify_local_assets(manifest):
    failures = []
    for name, asset in manifest['assets'].items():
        path = STATIC_ROOT / asset['static_path']
        if not path.is_file():
            failures.append(f'{name}: missing {display_path(path)}')
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if not hmac.compare_digest(actual, asset['sha256']):
            failures.append(f'{name}: SHA-256 mismatch for {display_path(path)}')
    if failures:
        raise RuntimeError('\n'.join(failures))


def update_vendor(manifest, metadata, archive):
    version = metadata['version']
    if metadata.get('name') != PACKAGE_NAME:
        raise RuntimeError(f'Unexpected npm package: {metadata.get("name")!r}')

    dist = metadata['dist']
    verify_archive_integrity(archive, dist['integrity'])
    assets = read_assets(archive, manifest)

    for name, data in assets.items():
        target = STATIC_ROOT / manifest['assets'][name]['static_path']
        atomic_write(target, data)
        manifest['assets'][name].update(asset_metadata(data))

    manifest.update(
        {
            'version': version,
            'release': f'https://github.com/ts4nfdi/terminology-service-suite/releases/tag/v{version}',
            'source': {
                'registry': DEFAULT_REGISTRY,
                'tarball': dist['tarball'],
                'integrity': dist['integrity'],
            },
        }
    )
    atomic_write(MANIFEST_PATH, (json.dumps(manifest, indent=2) + '\n').encode())
    load_tss_vendor_manifest.cache_clear()
    verify_local_assets(manifest)


def run_vendor_action(*, latest=False, version=None, check=False, check_latest=False):
    manifest = read_manifest()
    messages = []

    if check or check_latest:
        verify_local_assets(manifest)
        messages.append(f'Vendored TSS {manifest["version"]}: local assets verified.')
        if not check_latest:
            return messages

    requested_version = version
    if not latest and requested_version is None:
        requested_version = manifest['version']

    metadata = package_metadata(DEFAULT_REGISTRY, None if latest or check_latest else requested_version)
    if check_latest:
        if metadata['version'] != manifest['version']:
            raise RuntimeError(f'TSS update available: {manifest["version"]} -> {metadata["version"]}')
        messages.append(f'Vendored TSS {manifest["version"]} is npm latest.')
        return messages

    archive = fetch_bytes(metadata['dist']['tarball'])
    update_vendor(manifest, metadata, archive)
    messages.append(f'Updated vendored TSS assets to {metadata["version"]} in {PACKAGE_ROOT}.')
    return messages


def check_gateway_contract(openapi_url=DEFAULT_OPENAPI_URL):
    document = fetch_json(openapi_url, 'rdmo-ts4nfdi-contract-check')
    paths = document.get('paths', {})
    missing = sorted(REQUIRED_GATEWAY_PATHS - paths.keys())
    if missing:
        missing_paths = '\n'.join(f'  {path}' for path in missing)
        raise RuntimeError(f'Gateway contract is missing required paths:\n{missing_paths}')

    return (
        f'Gateway OpenAPI {document.get("openapi", "unknown")} '
        f'({document.get("info", {}).get("version", "unversioned")}): required paths available.'
    )


def check_gateway_live_contract(gateway_url=DEFAULT_GATEWAY_URL, origin=None):
    """Probe public Gateway responses needed by the configured example routes.

    This intentionally checks response behavior, not merely the OpenAPI route
    declarations. It is an opt-in deployment check: public DNS, CORS policy,
    or temporarily unavailable upstream sources must not affect normal RDMO
    requests or the test suite.
    """
    gateway_url = gateway_url.rstrip('/')

    origin = origin.strip() if isinstance(origin, str) else None
    request_headers = {'Origin': origin} if origin else None
    edam_payload, edam_headers = fetch_json_response(
        _gateway_url(
            gateway_url,
            'ols4/api/v2/ontologies/edam/entities',
            iri=EDAM_SAMPLE_IRI,
            database='ebi',
        ),
        'rdmo-ts4nfdi-live-contract-check',
        request_headers,
    )
    if origin and not edam_headers.get('access-control-allow-origin'):
        raise RuntimeError('Gateway EDAM OLS4 response does not expose a CORS allow-origin header.')
    if not _contains_iri(_response_items(edam_payload), EDAM_SAMPLE_IRI):
        raise RuntimeError('Gateway EDAM OLS4 response does not contain the expected sample entity.')

    collections_payload, _collections_headers = fetch_json_response(
        _gateway_url(gateway_url, 'collections/'),
        'rdmo-ts4nfdi-live-contract-check',
    )
    if not _contains_id(_response_items(collections_payload), FAIRAGRO_COLLECTION_ID):
        raise RuntimeError('Gateway collections response does not contain the configured FAIRagro collection.')

    entitysets_payload, _entitysets_headers = fetch_json_response(
        _gateway_url(gateway_url, 'entitysets'),
        'rdmo-ts4nfdi-live-contract-check',
    )
    if not _contains_id(_response_items(entitysets_payload), FAIRAGRO_ENTITYSET_ID):
        raise RuntimeError('Gateway entity-sets response does not contain the configured FAIRagro entity set.')

    agrovoc_payload, _agrovoc_headers = fetch_json_response(
        _gateway_url(
            gateway_url,
            'ols4/api/v2/ontologies/agrovoc/entities',
            iri=AGROVOC_SAMPLE_IRI,
            database='agrovoc',
        ),
        'rdmo-ts4nfdi-live-contract-check',
    )
    agrovoc_ready = _contains_iri(_response_items(agrovoc_payload), AGROVOC_SAMPLE_IRI)
    agrovoc_status = (
        'AGROVOC OLS4 entity available for a future TSS migration.'
        if agrovoc_ready
        else 'AGROVOC OLS4 entity unavailable; keep the native annotation path.'
    )
    cors_status = (
        f'CORS available for {origin}'
        if origin
        else 'CORS not checked (pass --origin with the RDMO browser origin)'
    )
    return (
        f'Gateway live contract: EDAM OLS4 entity available; {cors_status}; '
        'FAIRagro collection and entity set available; '
        f'{agrovoc_status}'
    )


def _gateway_url(gateway_url, path, **params):
    url = f'{gateway_url}/{path.lstrip("/")}'
    return f'{url}?{urlencode(params)}' if params else url


def _response_items(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return ()
    if any(key in payload for key in ('iri', '@id', 'uri', 'id')):
        return (payload,)
    for key in ('elements', 'entitysets', 'items', 'results'):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return ()


def _contains_iri(items, expected_iri):
    return any(
        isinstance(item, dict)
        and next(
            (
                item.get(key)
                for key in ('iri', '@id', 'uri', 'id')
                if item.get(key)
            ),
            None,
        ) == expected_iri
        for item in items
    )


def _contains_id(items, expected_id):
    return any(
        isinstance(item, dict) and str(item.get('id') or '').strip() == expected_id
        for item in items
    )


def vendor_cli(argv=None):
    parser = argparse.ArgumentParser(description='Update or verify the locally served TSS browser bundle.')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--latest', action='store_true', help='install the current npm latest release')
    selection.add_argument('--version', help='install one exact npm release')
    selection.add_argument('--check', action='store_true', help='verify local asset hashes without network access')
    selection.add_argument('--check-latest', action='store_true', help='fail if npm publishes a newer release')
    args = parser.parse_args(argv)

    try:
        for message in run_vendor_action(
            latest=args.latest,
            version=args.version,
            check=args.check,
            check_latest=args.check_latest,
        ):
            print(message)
    except (KeyError, OSError, RuntimeError, tarfile.TarError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


def gateway_contract_cli(argv=None):
    parser = argparse.ArgumentParser(description='Check the live TS4NFDI Gateway routes used by this plugin.')
    parser.add_argument('--openapi-url', default=DEFAULT_OPENAPI_URL)
    parser.add_argument(
        '--live',
        action='store_true',
        help='probe the public responses and CORS contract used by the example configuration',
    )
    parser.add_argument('--gateway-url', default=DEFAULT_GATEWAY_URL)
    parser.add_argument(
        '--origin',
        help='RDMO browser origin to use for the optional direct-mode CORS assertion',
    )
    args = parser.parse_args(argv)

    try:
        if args.live:
            print(check_gateway_live_contract(args.gateway_url, args.origin))
        else:
            print(check_gateway_contract(args.openapi_url))
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0
