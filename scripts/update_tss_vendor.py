#!/usr/bin/env python3
"""Repository/CI wrapper for the TS4NFDI vendor updater."""

from rdmo_ts4nfdi.upstream import vendor_cli

if __name__ == '__main__':
    raise SystemExit(vendor_cli())
