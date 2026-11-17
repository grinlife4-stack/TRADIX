# Mega Market Local Runner v0.1

## Purpose

Provide a small, offline, repeatable command that validates one normalized sales report and writes an auditable import summary. This is the first executable path through the Mega Market sales-import boundary, not a live marketplace integration.

## Requirements

- Python 3.11 or newer.
- No runtime third-party dependencies.
- No API credentials, browser session, network access, payment account, exchange account, or wallet.

## Install from the repository root

```bash
python -m pip install -e .
```

## Run the synthetic fixture

The fixture is invented test data. Its `fixture://` permission reference is not a real contract, license, or proof of legal access.

```bash
mega-market import-sales \
  --input examples/mega_market/sales_report_v1.json \
  --source-id demo-sales-source \
  --source-name "Synthetic demo source" \
  --permission-reference "fixture://demo/permission" \
  --terms-reviewed-at 2026-11-16T12:00:00Z \
  --output /tmp/mega-market-import-result.json
```

The command exits with code 0 on success and 2 on validation or file errors. If `--output` is omitted, the JSON result is written to standard output. An existing output file is never overwritten.

## Real report use

Replace the fixture with a report obtained from a source whose terms and permissions have been reviewed outside this program. Supply the exact source ID and permission reference registered for that source. The CLI records the operator's permission attestation; it does not independently establish legal authorization or source truthfulness.

The output includes the SHA-256 of the exact input bytes, normalized observations, provenance references, coverage state, and an explicit `commercial_authorization: false` marker.

## Safety boundary

- No network calls or source polling occur.
- No files are deleted or overwritten.
- No candidate is approved by this command.
- Importing verified direct-sales observations is evidence intake only. Candidate assessment still requires the separate evidence, economics, supplier, fulfillment, and compliance gates.
- No listing, order, purchase, payment, FX conversion, or crypto transfer can be initiated.
