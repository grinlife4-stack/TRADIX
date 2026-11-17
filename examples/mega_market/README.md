# Mega Market offline execution demo

This is a deterministic-path smoke demo for the normalized sales-report importer,
demand assessment, unit-economics calculator, and candidate decision gate.

## Run

From the repository root, with Python 3.11 or newer:

```bash
python -m pip install -e .
python examples/mega_market/offline_sales_report_demo.py
```

No network access, marketplace account, API key, supplier account, payment method,
wallet, or external service is used.

## Expected result

The script imports two synthetic direct-sales observations, computes the SHA-256
of the exact JSON payload, assesses demand, calculates unit economics, and prints
a simulated `eligible_for_manual_pilot` result when all fixture checks pass.

The fixture uses a synthetic source descriptor marked approved solely to exercise
the importer. Its permission reference, complete-coverage attestation, supplier
authorization, compliance review, and sales values are not real. The output is
not evidence of demand and is not authorization to purchase, publish listings,
accept orders, make payments, convert currency, transfer BTC, or scale operations.

A successful run proves only that this offline example can traverse the current
local analysis path. It does not verify any live marketplace integration.
