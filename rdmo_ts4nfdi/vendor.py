import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def load_tss_vendor_manifest():
    manifest_path = files('rdmo_ts4nfdi').joinpath('vendor/terminology_service_suite.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

    required = {'package', 'version', 'assets'}
    if not required.issubset(manifest):
        raise RuntimeError('The TS4NFDI widget vendor manifest is incomplete.')

    for name in ('script', 'stylesheet'):
        asset = manifest['assets'].get(name, {})
        if not {'archive_path', 'static_path', 'sha256', 'integrity'}.issubset(asset):
            raise RuntimeError(f'The TS4NFDI widget {name} manifest is incomplete.')

    return manifest
