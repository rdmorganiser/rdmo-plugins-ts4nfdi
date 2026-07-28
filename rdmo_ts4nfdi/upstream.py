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
from urllib.parse import quote
from urllib.request import Request, urlopen

from rdmo_ts4nfdi.vendor import load_tss_vendor_manifest

PACKAGE_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PACKAGE_ROOT / 'vendor/terminology_service_suite.json'
STATIC_ROOT = PACKAGE_ROOT / 'static'
PACKAGE_NAME = '@ts4nfdi/terminology-service-suite-js'
DEFAULT_REGISTRY = 'https://registry.npmjs.org'
DEFAULT_OPENAPI_URL = 'https://terminology.services.base4nfdi.de/api-gateway/v3/api-docs'
REQUIRED_GATEWAY_PATHS = {
    '/collections/',
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
    args = parser.parse_args(argv)

    try:
        print(check_gateway_contract(args.openapi_url))
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0
