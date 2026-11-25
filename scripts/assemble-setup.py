"""Combine the Windows setup bootstrap, 7-Zip extractor, and app archive."""

import argparse
import hashlib
from pathlib import Path
import shutil
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bootstrap", "extractor", "archive", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    pending = args.output.with_suffix(".exe.part")
    digest = hashlib.sha256()
    with pending.open("xb") as output:
        with args.bootstrap.open("rb") as source:
            shutil.copyfileobj(source, output)
        lengths = []
        for segment in (args.extractor, args.archive):
            count = 0
            with segment.open("rb") as source:
                while block := source.read(1024 * 1024):
                    output.write(block)
                    digest.update(block)
                    count += len(block)
            lengths.append(count)
        output.write(struct.pack("<qq", *lengths))
        output.write(digest.digest())
        output.write(b"AGENTDESK-PKG-03")
    pending.rename(args.output)
    print(f"Assembled {args.output.name} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
