#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile the production Java framework and run host-side view hierarchy checks."""
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    sources = []
    for folder in ("stubs", "src", "gen-src"):
        sources.extend((ROOT / "src/java-framework" / folder).rglob("*.java"))
    sources.extend(pathlib.Path(__file__).parent.glob("*Test.java"))
    args = tmp / "javac.args"
    args.write_text("\n".join('"' + p.resolve().as_posix() + '"' for p in sources), encoding="utf-8")
    subprocess.run(["javac", "-nowarn", "--release", "8", "-encoding", "UTF-8",
                    "-d", str(tmp / "classes"), "@" + str(args)], check=True)
    subprocess.run(["java", "-cp", str(tmp / "classes"), "ViewGroupLayoutParamsTest"], check=True)
