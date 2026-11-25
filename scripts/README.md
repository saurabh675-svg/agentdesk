# scripts/ layout
- build/: package-windows.ps1, stage-runtime.ps1, build-installer.mjs, assemble-setup.py
- verify/: verify_release.py, test_*.py, ui_*.py
- probe/: probe_*.py, _probe_*.py, _live_chat.py, _browser_smoke.py
- Legacy underscore helpers (_*.ps1) are kept for reproducible installer repro
  and should be moved into build/ or verify/ when the next installer cycle runs.
