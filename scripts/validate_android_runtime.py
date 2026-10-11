#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail packaging if the Java TL's boot class path or native runtime is incomplete."""
import pathlib
import struct
import sys
import zipfile


def validate(root):
    root = pathlib.Path(root)
    java = root / "java-runtime"
    required = ["husk-framework.dex", "framework-res.apk", "org.apache.http.legacy.jar"]
    required += [f"com.android.art/javalib/{name}.jar" for name in
                 ("core-oj", "core-libart", "okhttp", "bouncycastle", "apache-xml")]
    required += [f"com.android.art/lib64/{name}.so" for name in
                 ("libandroidio", "libbase", "libc++", "libexpat", "libjavacore", "libnativehelper", "libopenjdk")]
    required += ["com.android.i18n/javalib/core-icu4j.jar", "com.android.conscrypt/javalib/conscrypt.jar"]
    required += [f"com.android.conscrypt/lib64/{name}.so" for name in ("libjavacrypto", "libcrypto", "libssl")]
    errors = []
    for name in required:
        path = java / name
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing java-runtime/{name}")
            continue
        if name.endswith(".so"):
            with path.open("rb") as stream:
                header = stream.read(20)
            if len(header) < 20 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != 183:
                errors.append(f"not an arm64 Android ELF: {name}")
        elif name.endswith(".jar"):
            try:
                with zipfile.ZipFile(path) as archive:
                    if "classes.dex" not in archive.namelist():
                        errors.append(f"no classes.dex in {name}")
                    elif name == "com.android.art/javalib/core-oj.jar" and b"Ljava/lang/Object;" not in archive.read("classes.dex"):
                        errors.append("core-oj.jar has no java/lang/Object")
            except zipfile.BadZipFile:
                errors.append(f"invalid jar: {name}")
        elif name.endswith(".dex") and not path.read_bytes().startswith(b"dex\n"):
            errors.append(f"invalid DEX: {name}")
    for folder in ("java-runtime/com.android.i18n/etc/icu", "java-runtime/com.android.tzdata/etc",
                   "android-system/fonts", "android-system/cacerts"):
        path = root / folder
        if not path.is_dir() or not any(item.is_file() for item in path.rglob("*")):
            errors.append(f"missing or empty {folder}")
    for name in ("fonts.xml", "font_fallback.xml"):
        if not (root / "android-system/etc" / name).is_file():
            errors.append(f"missing android-system/etc/{name}")
    if errors:
        raise ValueError("Incomplete Android runtime:\n" + "\n".join(errors))
    print("Android Java runtime, arm64 libraries and system resources verified")


if __name__ == "__main__":
    validate(sys.argv[1])
