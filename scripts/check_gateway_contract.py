#!/usr/bin/env python3
"""Repository/CI wrapper for the TS4NFDI Gateway contract check."""

from rdmo_ts4nfdi.upstream import gateway_contract_cli

if __name__ == '__main__':
    raise SystemExit(gateway_contract_cli())
