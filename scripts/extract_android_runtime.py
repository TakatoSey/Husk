#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Extract the TL's Android runtime data from a raw Lineage disk, without booting it.

Needs e2fsprogs/debugfs. Reads GPT and Android dynamic-partition metadata directly;
the system/APEX extraction follows build_android_system.sh.
"""
import io
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile


def read_at(stream, offset, size):
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Truncated disk image")
    return data


def system_partition(raw, output):
    with open(raw, "rb") as disk:
        header = read_at(disk, 512, 92)
        if header[:8] != b"EFI PART":
            raise ValueError("No GPT header")
        table, count, entry_size = struct.unpack_from("<QII", header, 72)
        base = None
        for i in range(count):
            entry = read_at(disk, table * 512 + i * entry_size, entry_size)
            name = entry[56:128].decode("utf-16-le").rstrip("\0")
            if name == "super":
                base = struct.unpack_from("<Q", entry, 32)[0] * 512
                break
        if base is None:
            raise ValueError("No super partition")
        header = read_at(disk, base + 12288, 128)
        if struct.unpack_from("<I", header)[0] != 0x414C5030:
            raise ValueError("No Android logical partition metadata")
        header_size = struct.unpack_from("<I", header, 8)[0]
        table_size = struct.unpack_from("<I", header, 44)[0]
        tables = read_at(disk, base + 12288 + header_size, table_size)
        po, pn, ps = struct.unpack_from("<III", header, 80)
        eo, en, es = struct.unpack_from("<III", header, 92)
        for i in range(pn):
            part = tables[po + ps * i:po + ps * (i + 1)]
            name = part[:36].split(b"\0")[0].decode()
            if name not in ("system", "system_a"):
                continue
            _, first, count, _ = struct.unpack_from("<IIII", part, 36)
            if first + count > en:
                raise ValueError("Invalid system extents")
            with open(output, "wb") as out:
                for j in range(first, first + count):
                    sectors, kind, sector, device = struct.unpack_from("<QIQI", tables, eo + es * j)
                    if device != 0 or kind not in (0, 1):
                        raise ValueError("Unsupported system extent")
                    left = sectors * 512
                    if kind == 1:
                        out.seek(left, 1)
                        out.truncate()
                        continue
                    disk.seek(base + sector * 512)
                    while left:
                        data = disk.read(min(left, 8 << 20))
                        if not data:
                            raise ValueError("Truncated system extent")
                        out.write(data)
                        left -= len(data)
            return
        raise ValueError("No system logical partition")


def extract(raw, dest):
    dest = pathlib.Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        system = tmp / "system.img"
        system_partition(raw, system)

        def debugfs(image, command):
            subprocess.run(["debugfs", "-R", command, str(image)], check=True)

        def dump(path, output):
            output.parent.mkdir(parents=True, exist_ok=True)
            debugfs(system, f"dump {path} {output}")
            if not output.is_file() or output.stat().st_size == 0:
                raise ValueError(f"Missing Android system file: {path}")

        for module in ("com.android.art", "com.android.i18n", "com.android.tzdata", "com.android.conscrypt"):
            package = tmp / f"{module}.capex"
            # Some system releases carry an uncompressed .apex instead of .capex.
            for extension in ("capex", "apex"):
                debugfs(system, f"dump /system/apex/{module}.{extension} {package}")
                if package.is_file() and package.stat().st_size:
                    break
            if not package.is_file() or not package.stat().st_size:
                raise ValueError(f"Missing APEX: {module}")
            with zipfile.ZipFile(package) as compressed:
                if "original_apex" in compressed.namelist():
                    apex_data = io.BytesIO(compressed.read("original_apex"))
                    archive = zipfile.ZipFile(apex_data)
                else:
                    archive = compressed
                payload = tmp / f"{module}.img"
                with archive.open("apex_payload.img") as src, payload.open("wb") as out:
                    shutil.copyfileobj(src, out)
                if archive is not compressed:
                    archive.close()
            folder = dest / "apex" / module
            folder.mkdir(parents=True, exist_ok=True)
            # Only the directories the TL needs; avoid bin/, tests and unrelated ART artifacts.
            for name in ("javalib", "lib64", "etc", "cacerts"):
                debugfs(payload, f"rdump /{name} {folder}")
            payload.unlink()
            package.unlink()

        dump("/system/framework/org.apache.http.legacy.jar", dest / "org.apache.http.legacy.jar")
        dump("/system/framework/framework-res.apk", dest / "framework-res.apk")
        sysout = dest / "android-system"
        sysout.mkdir(parents=True, exist_ok=True)
        debugfs(system, f"rdump /system/fonts {sysout}")
        for path in (sysout / "fonts").glob("*CJK*"):
            path.unlink()
        for name in ("fonts.xml", "font_fallback.xml"):
            dump(f"/system/etc/{name}", sysout / "etc" / name)
        shutil.copytree(dest / "apex/com.android.conscrypt/cacerts", sysout / "cacerts", dirs_exist_ok=True)
    print(f"Extracted Android runtime sources into {dest}")


if __name__ == "__main__":
    extract(sys.argv[1], sys.argv[2])
