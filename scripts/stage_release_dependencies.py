#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Stage prebuilt dependencies from a pinned upstream IPA for app-only CI builds.

The app and its translation layer are compiled from this checkout. QEMU, ANGLE,
MoltenVK and guest boot resources are reused; this is not a full dependency build.
"""
import bz2
import hashlib
import pathlib
import shutil
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA256 = "f2044fea5b5f8287deffa0466f5f71bfd915fc4ee0d1cb852b10b0242c6ca949"


def stage(ipa):
    with open(ipa, "rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != SHA256:
            raise ValueError("Upstream Husk 1.1.0 IPA checksum mismatch")
    with zipfile.ZipFile(ipa) as archive:
        prefix = "Payload/Husk.app/"

        def copy(name, dest):
            dest = ROOT / dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(prefix + name) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            mode = (archive.getinfo(prefix + name).external_attr >> 16) & 0o777
            if mode:
                dest.chmod(mode)

        for name in ("vmlinuz-virt", "initramfs-virt"):
            copy(name, "guests/phase0/" + name)
        copy("Frameworks/libqemu-aarch64-softmmu.dylib", "build/ios-arm64/lib/libqemu-aarch64-softmmu.dylib")
        copy("Frameworks/libANGLE-shared.dylib", "build/ios-arm64/sysroot/lib/libANGLE-shared.dylib")
        bios = ROOT / "third_party/build/qemu-10.0.12-utm/pc-bios"
        bios.mkdir(parents=True, exist_ok=True)
        (bios / "edk2-aarch64-code.fd.bz2").write_bytes(bz2.compress(archive.read(prefix + "edk2-aarch64-code.fd")))
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.startswith(prefix):
                continue
            name = entry.filename[len(prefix):]
            if ".." in pathlib.PurePosixPath(name).parts:
                raise ValueError("Invalid resource path")
            if name.startswith("Frameworks/MoltenVK.framework/"):
                copy(name, "build/bootstrap/" + name.removeprefix("Frameworks/"))
            elif name.startswith("pc-bios/"):
                copy(name, "third_party/build/qemu-10.0.12-utm/" + name)
            elif name.startswith(("android-system/", "java-runtime/")):
                copy(name, "build/" + name)
        for folder in ("android-system", "java-runtime"):
            if not (ROOT / "build" / folder).is_dir():
                print(f"WARNING: upstream IPA has no {folder}; this build does not supply that optional runtime data")
    print("Staged dependencies from upstream Husk 1.1.0 (SHA-256 verified)")


if __name__ == "__main__":
    stage(sys.argv[1])
