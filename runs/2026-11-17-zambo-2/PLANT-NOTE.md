# Run 2026-11-17-zambo-2: A5 plant (post-fix)

Planted 2026-11-17, after the production recovery fix and after the
short-range verification in runs/2026-11-17-zambo-fix-verify/ scored
K-only recovery, identical-retry replay, and modified-parameter
conflict refusal all PASS (triple-verified).

Formal plant (a5_plant.json): K lr-op-13118ee094-a1, session
lr-13118ee094-a1, receipt e3af210e-182f-4c48-9da1-dd954be4ccda,
committed digest
sha256:90c4715cfe287641f6145abe9a9cbc074eb85b3c3bf3af2a1022a35f9a44bd1d,
external effect count 1 (count_a1_after_attempt1_plant2.json),
planted 2026-11-17T17:12:46Z, delayed leg due 2026-11-18T17:12:46Z.
The delayed leg runs with the harness (--delayed-leg on
a5_plant.json) plus the supplementary K-only recovery and
protection probes, and scores as a new run section in RESULTS.md.
Run 2026-11-16-zambo-1's A5 FAIL row is never edited.

First plant attempt, recorded exactly: plant_probe.py's first
attempt (K lr-op-d2945b2c6e-a1, response dropped per the contract
setup) never committed. Its journal is empty
(plant_check_journal.json: status "empty"), its workflow snapshot
holds only the two workflow_close enumeration receipts, and the
K lookup returns 404 because nothing was committed
(plant_check_receipt.json). The dropped response makes the refusal
class unobservable; a kept-response attempt minutes later committed
as the formal plant above (a1_attempt1_kept.json). The uncommitted
plant file is preserved as a5_plant_uncommitted.json.
