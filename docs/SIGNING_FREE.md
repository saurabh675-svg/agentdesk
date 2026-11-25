# Free code-signing alternatives (no paid cert)

Paid EV/OV certs are $200-400/yr. For a personal/local app these work free:

## 1. Self-signed (best for personal use) — $0, 2 minutes
- `scripts/sign-selfsigned.ps1` — creates a local self-signed cert, signs
  `release/*.exe` with `signtool`, prints the SHA256 fingerprint.
- Users who install it once see no SmartScreen warning thereafter:
  import the printed `.cer` into **Trusted Root / Trusted Publishers**
  (double-click → Install → Local Machine → Trusted Root Certification
  Authorities). For sharing with friends, send them the `.cer` too.
- Unlimited, offline, no account. SmartScreen reputation still builds
  slowly (many installs), but the warning is a one-click "More info →
  Run anyway" instead of a block.

## 2. SignPath free (open-source projects) — $0, trusted
- https://signpath.org/ — free Authenticode signing for OSS.
- Create a project, connect this repo, submit the built exe for signing.
  Windows then trusts it like a paid cert (no SmartScreen block).
- Best when AgentDesk goes public. Needs a GitHub account + 1-2 day review.

## 3. Just checksums (zero signing) — $0, always do this
- `scripts/checksums.mjs` — after any build, writes
  `release/SHA256SUMS.txt` (hash of every artifact).
- Publish it next to the installer; users run
  `Get-FileHash AgentDesk-Setup-0.4.0.exe` and compare. Proves the file
  wasn't tampered with, even though SmartScreen still warns once.

## What NOT to rely on
- **Unsigned** (current) — works, but SmartScreen warns on every machine.
- **Free "instant SSL" sites** — most are not trusted by Windows; skip.
- **electron-builder `certificateFile`** — only works with a real .pfx
  from option 1 or 2 above; don't commit the .pfx password.

## Recommended flow
Self-signed now (option 1) + checksums (option 3) for every release.
If AgentDesk ever goes public, apply to SignPath (option 2) once.
