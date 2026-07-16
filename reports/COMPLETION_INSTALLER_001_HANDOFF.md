# COMPLETION-INSTALLER-001 handoff

## Scope and boundary

This closeout proves a real installer apply against a fresh disposable target only. The live Hermes plugin root was never an installer target, `--live` was never passed, and no plugin, gateway, Telegram, Google, website, remote Git, merge, or checker actions were performed.

- Required starting commit: `d2fcbacce04c41f8b63ff3327233797aca0b80e5`
- Starting branch: `completion-installer-001`
- Final closeout commit SHA: recorded in the Kanban handoff after the focused report commit
- Repository: `C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs`
- Live root: `C:\Users\fallo\AppData\Local\hermes\plugins`
- Disposable root: `C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp`
- Disposable target: `C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\target`
- Disposable backup root: `C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\target\.cleanup_004_backups`
- Rollback target: `C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\rollback_target`

The preflight branch, starting SHA, and clean worktree matched the contract. The installer and drift checker were unchanged; no focused test or implementation defect was found.

## Canonical manifest evidence

`RUNTIME_PLUGIN_MANIFEST.json` SHA-256:

```text
5bf62877bc0dfc1fc49d658342c1936694a7f728ae861922e5886236a73651e3
```

All 16 canonical source/metadata files matched the manifest after apply. Expected SHA-256 values:

```text
non-profit-hermes-daily/__init__.py e4d797b55d463b76377f6fd5db55a7beb1f6a967181fc43166519d9eff54b0c8
non-profit-hermes-daily/init.py e55c923556d4aa6e3e48216afd34252ba9566a849b62ce999b1ae58ded16c927
non-profit-hermes-daily/plugin.yaml 76ee0934c02c2d4599152f0eba9c06b49f567c7acd780fa2198f2443da6121b3
non-profit-hermes-event/__init__.py a421fbdaa5544816d9872f705e3c3713333f9486d3bd6b2b1be9b90a1f32a446
non-profit-hermes-event/plugin.yaml 7c3711b87ae81229b83c4d0d2fac867c1a66751277d475bdd135200b748924b5
non-profit-hermes-need/__init__.py f9f694c2d4f978f15d0bae5abe5391bdc5a18211b71b7e7d934a535b815ea028
non-profit-hermes-need/plugin.yaml a4ff2d3473e42e4a81424eaf006903523412a90413d332fe5379a86a3116b930
non-profit-hermes-donation/__init__.py 6eb689e0f2e7468d126f21efc71c76defe640703cfa31f77e52e9cea2fd241c9
non-profit-hermes-donation/init.py 59119e7feaedb42bcb28ea2fd9fda870e41cee8adfd7b2216e64b032c146388f
non-profit-hermes-donation/plugin.yaml ab96a3f58754ad3520d3292a00ae44c1e7d58512814a3a335f09603b924bb408
non-profit-hermes-report/__init__.py f4ab02fbc9a33a6515ab359de7020def7b5f9a44ac098cad5d2d1eaed5857aa7
non-profit-hermes-report/plugin.yaml d8b88730c28a62a9a7b7a597efd5d40bd9cd3ff956390e8f6436d1af30e1b7d5
non-profit-hermes-task/__init__.py 5f14632f651d71ecc1bc6d50c887c3ea50f8a3f0263bb9ddb4af3245f42b2ef0
non-profit-hermes-task/plugin.yaml fea98056cb50558413b71abd7fd596fb09a888c212fc88e7aa41fa34ea63c319
non-profit-hermes-inventory/__init__.py 52f79a04cd90b87ada50009c7ba7cea63fc2c38ba12c84ee4217eb0a11a8af60
non-profit-hermes-inventory/plugin.yaml 4a67c8ad1595a8d510295ca2fb0986ca79a3f32031cd1f07c1982a5cb916de8d
```

## Real disposable apply

The target was fresh except for controlled stale state in `non-profit-hermes-daily`:

- stale `__init__.py` content: `STALE = True\n`
- declared mutable bytecode: `__pycache__/retained.pyc`, bytes `controlled mutable bytecode`

Exact installer command (no `--live`):

```text
C:\Python314\python.exe C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs\scripts\install_runtime_plugins.py --repo-root C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs --apply --target-root C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\target
```

- Exit: `0`
- All seven plugins reported `INSTALLED`.
- The daily backup was created at:
  `C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\target\.cleanup_004_backups\non-profit-hermes-daily.20260716T172055Z`
- Backup evidence: the backup retained `STALE = True\n`; its SHA-256 was `92f906a0d769998328892bb473ed61ba4583c266f90d847aacacf072a013b702`.
- Mutable bytecode remained at `target\non-profit-hermes-daily\__pycache__\retained.pyc`.

Exact strict disposable drift command:

```text
C:\Python314\python.exe C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs\scripts\check_runtime_plugin_drift.py --repo-root C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs --installed-root C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\target --strict --json
```

- Exit: `0`
- Daily: `EXPECTED DERIVATION` only for `__pycache__/retained.pyc`.
- Event, need, donation, report, task, inventory: `MATCH`.
- Missing, unexplained, and mutable-state lists were empty.
- All 16 target source/metadata hashes matched the manifest.

## Controlled failure, rollback, and recovery

A disposable `rollback_target` was seeded with old daily plugin files. A controlled inline Python proof imported `install_runtime_plugins.atomic_install`, recorded `os.replace` operations, and raised `OSError("controlled closeout failure")` exactly on the staged-directory replacement after the existing target had been moved to backup. The observed operation order was target-to-backup, stage-to-target (forced failure), backup-to-target (recovery). The original daily files were restored byte-for-byte; `rollback_recovered: true`.

Recovery then used the real installer:

```text
C:\Python314\python.exe C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs\scripts\install_runtime_plugins.py --repo-root C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs --apply --target-root C:\Users\fallo\AppData\Local\Temp\cleanup004_closeout_frah57jp\rollback_target
```

- Exit: `0`
- Exact strict drift check against `rollback_target`: exit `0`; all seven plugins were `MATCH`.

## Live-root before/after proof

The following read-only per-plugin tree hash is SHA-256 over sorted `relative-path sha256(file)` rows, including existing derived bytecode. Before and after values were identical:

```text
plugin                                      before                                                            after
non-profit-hermes-daily                    b145c53268aee39c724dd984b5a4f336013cb0a5374375fed9f411f7bbc7b397 b145c53268aee39c724dd984b5a4f336013cb0a5374375fed9f411f7bbc7b397
non-profit-hermes-event                    5ff6cdb815b27efac433b8baf366d7e0374706046cdaea329903ea52ed67422f 5ff6cdb815b27efac433b8baf366d7e0374706046cdaea329903ea52ed67422f
non-profit-hermes-need                     90f79a47e5b2f64d0b64ddfc06bf412002519ac387f4f2f115746b90e15f482b 90f79a47e5b2f64d0b64ddfc06bf412002519ac387f4f2f115746b90e15f482b
non-profit-hermes-donation                 de0f8d6e79034ed3675a13fdc12838021be25fbb53fdb6da4cd2c7bd155c9d81 de0f8d6e79034ed3675a13fdc12838021be25fbb53fdb6da4cd2c7bd155c9d81
non-profit-hermes-report                   0965c501be713def078a56c9cdf682b2f2dbc2b4bb07d41ea5b7663836f07f2b 0965c501be713def078a56c9cdf682b2f2dbc2b4bb07d41ea5b7663836f07f2b
non-profit-hermes-task                     c8c1f278c4ca4a0e384993365211e1761b3391c9af9707650c8afab415cb7b5d c8c1f278c4ca4a0e384993365211e1761b3391c9af9707650c8afab415cb7b5d
non-profit-hermes-inventory               9d15d873b88b69fea588c6c11a6d2d5821edab59d96841eafedd1e3078f28aaf 9d15d873b88b69fea588c6c11a6d2d5821edab59d96841eafedd1e3078f28aaf
```

Exact strict live drift command (read-only; no installer apply):

```text
C:\Python314\python.exe C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs\scripts\check_runtime_plugin_drift.py --repo-root C:\Users\fallo\non-profit-hermes-mvp\worktrees\nonprofit-cleanup-docs --installed-root C:\Users\fallo\AppData\Local\hermes\plugins --strict --json
```

- Exit before/after: `0`.
- Both checks classified only expected `__pycache__` derivations for the seven live plugins.
- `live_hashes_unchanged: true`.

## Tests and final state

Commands run:

```text
python -m pytest tests/test_runtime_plugin_drift.py tests/test_runtime_plugin_install.py -q
python -m pytest -q
python -m py_compile scripts/*.py tests/*.py
git diff --check
git status --short --branch
```

The focused suite passed `13` tests. The full suite passed `214 passed, 64 subtests passed in 6.00s`; `python -m py_compile scripts/*.py tests/*.py` exited `0`; `git diff --check` exited `0`. The final status before commit was `## completion-installer-001` with only this new report untracked. No generated repository artifacts were created. The disposable proof root is intentionally retained for review and is outside the repository and live root.

Limitations: this is Windows filesystem proof using a disposable target and read-only live inspection. It does not claim plugin enablement, gateway lifecycle, Telegram/Google behavior, website publication, or Samsung/device acceptance.
