#!/usr/bin/env python
"""Fix vendored Composable Kernel headers for Clang 23.

Clang 23's __builtin_amdgcn_raw_buffer_{load,store}_b* take and return
unsigned integers / uint32 vectors. CK still assigns those to int32xN_t
and float payloads. Same class of fix as python-xformers
0001-ck-tile-clang23-rdna.patch.

Idempotent: safe to re-run on an already-patched tree.
Walks every composable_kernel copy under the given root (default: .).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# reinterpret_cast<mbuf_t&>(value) = __builtin_amdgcn_raw_buffer_load_bNN(
#     args);
#
# b16/b8 return a sub-dword unsigned integer; mbuf_t is float (4 bytes),
# so zero-extend then bit_cast. Wider loads are the same width as mbuf_t.
LOAD_ASSIGN = re.compile(
    r"(?P<indent>[ \t]*)reinterpret_cast<mbuf_t&>\(value\) = "
    r"(?P<builtin>__builtin_amdgcn_raw_buffer_load_b(?P<bits>8|16|32|64|96|128))\("
    r"(?P<args>.*?)\);",
    re.S,
)

# int16_t / int32_t / int32xN_t tmp = __builtin_amdgcn_raw_buffer_load_bNN(...);
TYPED_LOAD = re.compile(
    r"(?P<indent>[ \t]*)(?P<lhs>(?:int8_t|int16_t|int32_t|int32x\d+_t)\s+\w+)\s*=\s*"
    r"(?P<builtin>__builtin_amdgcn_raw_buffer_load_b(?P<bits>8|16|32|64|96|128))\("
    r"(?P<args>.*?)\);",
    re.S,
)

# return __builtin_amdgcn_raw_buffer_load_b8(...);
RETURN_LOAD = re.compile(
    r"(?P<indent>[ \t]*)return\s+"
    r"(?P<builtin>__builtin_amdgcn_raw_buffer_load_b(?P<bits>8|16|32|64|96|128))\("
    r"(?P<args>.*?)\);",
    re.S,
)


def _already_cast(prefix: str) -> bool:
    return "bit_cast" in prefix[-40:]


def wrap_load_assign(m: re.Match[str]) -> str:
    indent = m.group("indent")
    bits = m.group("bits")
    builtin = m.group("builtin")
    args = m.group("args")
    if "bit_cast" in m.group(0):
        return m.group(0)
    call = f"{builtin}({args})"
    if bits in ("8", "16"):
        return (
            f"{indent}reinterpret_cast<mbuf_t&>(value) = bit_cast<mbuf_t>("
            f"static_cast<uint32_t>({call}));"
        )
    return f"{indent}reinterpret_cast<mbuf_t&>(value) = bit_cast<mbuf_t>({call});"


def wrap_typed_load(m: re.Match[str]) -> str:
    if "bit_cast" in m.group(0):
        return m.group(0)
    lhs = m.group("lhs")
    ty = lhs.split()[0]
    return (
        f"{m.group('indent')}{lhs} = bit_cast<{ty}>("
        f"{m.group('builtin')}({m.group('args')}));"
    )


def wrap_return_load(m: re.Match[str]) -> str:
    if "bit_cast" in m.group(0):
        return m.group(0)
    bits = m.group("bits")
    ty = {
        "8": "int8_t",
        "16": "int16_t",
        "32": "int32_t",
        "64": "int32x2_t",
        "96": "int32x3_t",
        "128": "int32x4_t",
    }[bits]
    return (
        f"{m.group('indent')}return bit_cast<{ty}>("
        f"{m.group('builtin')}({m.group('args')}));"
    )


STORE_MAP = (
    # store_b8(src_thread_data,  -> store_b8(bit_cast<uint8_t>(src_thread_data),
    (
        re.compile(
            r"__builtin_amdgcn_raw_buffer_store_b8\(\s*src_thread_data\s*,"
        ),
        "__builtin_amdgcn_raw_buffer_store_b8(bit_cast<uint8_t>(src_thread_data),",
    ),
    (
        re.compile(
            r"__builtin_amdgcn_raw_buffer_store_b16\(bit_cast<int16_t>"
        ),
        "__builtin_amdgcn_raw_buffer_store_b16(bit_cast<uint16_t>",
    ),
    (
        re.compile(
            r"__builtin_amdgcn_raw_buffer_store_b32\(bit_cast<int32_t>"
        ),
        "__builtin_amdgcn_raw_buffer_store_b32(bit_cast<uint32_t>",
    ),
    (
        re.compile(
            r"__builtin_amdgcn_raw_buffer_store_b64\(bit_cast<int32x2_t>"
        ),
        "__builtin_amdgcn_raw_buffer_store_b64(bit_cast<uint32x2_t>",
    ),
    (
        re.compile(
            r"__builtin_amdgcn_raw_buffer_store_b128\(bit_cast<int32x4_t>"
        ),
        "__builtin_amdgcn_raw_buffer_store_b128(bit_cast<uint32x4_t>",
    ),
    # store_b128(tmp.template AsType<int32x4_t>()[Number<N>{}],
    (
        re.compile(
            r"__builtin_amdgcn_raw_buffer_store_b128\("
            r"(tmp\.template AsType<int32x4_t>\(\)\[Number<\d+>\{\}\])"
        ),
        r"__builtin_amdgcn_raw_buffer_store_b128(bit_cast<uint32x4_t>(\1)",
    ),
)

UINT_TYPEDEFS = """
// Clang 23+ raw_buffer_* builtins take/return unsigned vectors.
using uint32x2_t = uint32_t __attribute__((ext_vector_type(2)));
using uint32x4_t = uint32_t __attribute__((ext_vector_type(4)));
"""


def fix_old_ck_typedefs(text: str, path: Path) -> str:
    if "ext_vector_type(4)));" in text and "using uint32x4_t" in text:
        return text
    # Old CK (ck/utility), not ck_tile — stores now pass uint32xN_t.
    if "/ck/utility/amd_buffer_addressing_builtins.hpp" not in path.as_posix():
        return text
    if "namespace ck {\n" not in text:
        return text
    return text.replace("namespace ck {\n", "namespace ck {" + UINT_TYPEDEFS + "\n", 1)


def fix_ck_tile_config(text: str) -> str:
    old = "#define CK_TILE_HOST_DEVICE_EXTERN __host__ __device__\n"
    new = (
        "#if __clang_major__ < 22\n"
        "#define CK_TILE_HOST_DEVICE_EXTERN __host__ __device__\n"
        "#else\n"
        "#define CK_TILE_HOST_DEVICE_EXTERN\n"
        "#endif\n"
    )
    if "__clang_major__ < 22" in text or old not in text:
        return text
    return text.replace(old, new, 1)


def fix_bfloat16(text: str) -> str:
    # Clang 23 vector builtins want signed short, not ushort.
    text = text.replace("using type = ushort;", "using type = short;")
    text = text.replace("using bfloat16_t = ushort;", "using bfloat16_t = short;")
    text = text.replace("using bf16_raw_t = uint16_t;", "using bf16_raw_t = short;")
    return text


def fix_buffer_header(text: str) -> str:
    text = LOAD_ASSIGN.sub(wrap_load_assign, text)
    text = TYPED_LOAD.sub(wrap_typed_load, text)
    text = RETURN_LOAD.sub(wrap_return_load, text)
    for pat, repl in STORE_MAP:
        text = pat.sub(repl, text)
    return text


def process(root: Path) -> int:
    changed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.as_posix()
        if "composable_kernel" not in rel:
            continue
        name = path.name
        orig = path.read_text(encoding="utf-8", errors="surrogateescape")
        text = orig
        if name.startswith("amd_buffer_addressing") and name.endswith(".hpp"):
            text = fix_buffer_header(text)
            text = fix_old_ck_typedefs(text, path)
        elif name == "config.hpp" and "/ck_tile/core/config.hpp" in rel:
            text = fix_ck_tile_config(text)
        elif name == "bfloat16.hpp" and "/ck_tile/" in rel:
            text = fix_bfloat16(text)
        else:
            continue
        if text != orig:
            path.write_text(text, encoding="utf-8")
            changed += 1
            print(path)
    return changed


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    n = process(root)
    print(f"updated {n} files under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
