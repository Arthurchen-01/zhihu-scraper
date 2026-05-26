"""
signature.py - Pure Python x-zse-96 Signature Generator (v3.0 Core)

Ported from z_core.js, avoiding any external JavaScript engines (Node, Bun, etc.).
Generates x-zse-96 signatures compatible with Zhihu's API requests.
"""

from __future__ import annotations

import hashlib
import random
from typing import Dict, List

# SM4-like CK (Constant Keys) constant array
ZK = [
    1170614578, 1024848638, 1413669199, 3951632832, 3528873006, 2921909214,
    4151847688, 3997739139, 1933479194, 3323781115, 3888513386, 460404854,
    3747539722, 2403641034, 2615871395, 2119585428, 2265697227, 2035090028,
    2773447226, 4289380121, 4217216195, 2200601443, 3051914490, 1579901135,
    1321810770, 456816404, 2903323407, 4065664991, 330002838, 3506006750,
    363569021, 2347096187
]

# S-Box for linear substitution
ZB = [
    20, 223, 245, 7, 248, 2, 194, 209, 87, 6, 227, 253, 240, 128, 222, 91,
    237, 9, 125, 157, 230, 93, 252, 205, 90, 79, 144, 199, 159, 197, 186, 167,
    39, 37, 156, 198, 38, 42, 43, 168, 217, 153, 15, 103, 80, 189, 71, 191,
    97, 84, 247, 95, 36, 69, 14, 35, 12, 171, 28, 114, 178, 148, 86, 182,
    32, 83, 158, 109, 22, 255, 94, 238, 151, 85, 77, 124, 254, 18, 4, 26,
    123, 176, 232, 193, 131, 172, 143, 142, 150, 30, 10, 146, 162, 62, 224, 218,
    196, 229, 1, 192, 213, 27, 110, 56, 231, 180, 138, 107, 242, 187, 54, 120,
    19, 44, 117, 228, 215, 203, 53, 239, 251, 127, 81, 11, 133, 96, 204, 132,
    41, 115, 73, 55, 249, 147, 102, 48, 122, 145, 106, 118, 74, 190, 29, 16,
    174, 5, 177, 129, 63, 113, 99, 31, 161, 76, 246, 34, 211, 13, 60, 68,
    207, 160, 65, 111, 82, 165, 67, 169, 225, 57, 112, 244, 155, 51, 236, 200,
    233, 58, 61, 47, 100, 137, 185, 64, 17, 70, 234, 163, 219, 108, 170, 166,
    59, 149, 52, 105, 24, 212, 78, 173, 45, 0, 116, 226, 119, 136, 206, 135,
    175, 195, 25, 92, 121, 208, 126, 139, 3, 75, 141, 21, 130, 98, 241, 40,
    154, 66, 184, 49, 181, 46, 243, 88, 101, 183, 8, 23, 72, 188, 104, 179,
    210, 134, 250, 201, 164, 89, 216, 202, 220, 50, 221, 152, 140, 33, 235, 214
]


def Q(e: int, t: int) -> int:
    """Cyclic left shift on 32-bit unsigned integer."""
    e &= 0xFFFFFFFF
    return (((e << t) & 0xFFFFFFFF) | (e >> (32 - t)))


def i_func(e: int, t: List[int], n: int) -> None:
    """Unpack a 32-bit integer into 4 bytes in a byte list."""
    e &= 0xFFFFFFFF
    t[n] = (e >> 24) & 0xFF
    t[n + 1] = (e >> 16) & 0xFF
    t[n + 2] = (e >> 8) & 0xFF
    t[n + 3] = e & 0xFF


def B(e: List[int], t: int) -> int:
    """Pack 4 bytes from a list into a 32-bit integer."""
    val = (e[t] << 24) | (e[t + 1] << 16) | (e[t + 2] << 8) | e[t + 3]
    return val & 0xFFFFFFFF


def G(e: int) -> int:
    """Linear substitution function."""
    t0 = (e >> 24) & 0xFF
    t1 = (e >> 16) & 0xFF
    t2 = (e >> 8) & 0xFF
    t3 = e & 0xFF

    n0 = ZB[t0]
    n1 = ZB[t1]
    n2 = ZB[t2]
    n3 = ZB[t3]

    r = (n0 << 24) | (n1 << 16) | (n2 << 8) | n3
    r &= 0xFFFFFFFF

    return r ^ Q(r, 2) ^ Q(r, 10) ^ Q(r, 18) ^ Q(r, 24)


def array_0_16_offset(e: List[int]) -> List[int]:
    """SM4-like 16-byte block encryption logic."""
    n = [0] * 36
    n[0] = B(e, 0)
    n[1] = B(e, 4)
    n[2] = B(e, 8)
    n[3] = B(e, 12)

    for r in range(32):
        xor_val = n[r + 1] ^ n[r + 2] ^ n[r + 3] ^ ZK[r]
        o = G(xor_val)
        n[r + 4] = (n[r] ^ o) & 0xFFFFFFFF

    t = [0] * 16
    i_func(n[35], t, 0)
    i_func(n[34], t, 4)
    i_func(n[33], t, 8)
    i_func(n[32], t, 12)
    return t


def array_16_48_offset(e: List[int], t: List[int]) -> List[int]:
    """Encrypt 32 bytes (offset 16-48) with dynamic keys."""
    n: List[int] = []
    length = len(e)
    i = 0
    while length > 0:
        o = e[16 * i : 16 * (i + 1)]
        a = [0] * 16
        for c in range(16):
            a[c] = o[c] ^ t[c]
        t = array_0_16_offset(a)
        n.extend(t)
        i += 1
        length -= 16
    return n


def encode_0_16(array_0_16: List[int]) -> List[int]:
    """Pre-process first 16 bytes and encrypt."""
    result = []
    array_offset = [48, 53, 57, 48, 53, 51, 102, 55, 100, 49, 53, 101, 48, 49, 100, 55]
    for idx in range(len(array_0_16)):
        a = array_0_16[idx] ^ array_offset[idx]
        b = a ^ 42
        result.append(b)
    return array_0_16_offset(result)


def encode(ar: List[int]) -> List[int]:
    """Transform 3 bytes (24-bit) into 4 x 6-bit numbers."""
    b = ar[1] << 8
    c = ar[0] | b
    d = ar[2] << 16
    e = c | d

    result_array = []
    result_array.append(e & 63)
    x6 = 6
    while len(result_array) < 4:
        a = e >> x6
        result_array.append(a & 63)
        x6 += 6
    return result_array


def get_init_array(encode_md5: str, seed_byte: int | None = None) -> List[int]:
    """Build the initial 48-byte buffer and encrypt it."""
    init_array = []
    for char in encode_md5:
        init_array.append(ord(char))
    init_array.insert(0, 0)
    
    # Allow seed_byte insertion for deterministic testing, otherwise use random byte
    sb = random.randint(0, 126) if seed_byte is None else seed_byte
    init_array.insert(0, sb)
    
    while len(init_array) < 48:
        init_array.append(14)

    array_0_16 = encode_0_16(init_array[0:16])
    array_16_48 = array_16_48_offset(init_array[16:48], array_0_16)
    return array_0_16 + array_16_48


def get_zse_96(encode_md5: str, seed_byte: int | None = None) -> str:
    """Generate final x-zse-96 signature from MD5 hash string."""
    init_array = get_init_array(encode_md5, seed_byte=seed_byte)
    for i in range(47, -1, -4):
        init_array[i] ^= 58
    init_array.reverse()

    result_array = []
    for j in range(3, len(init_array) + 1, 3):
        ar = init_array[j - 3 : j]
        result_array.extend(encode(ar))

    init_str = "6fpLRqJO8M/c3jnYxFkUVC4ZIG12SiH=5v0mXDazWBTsuw7QetbKdoPyAl+hN9rgE"
    result = ""
    for val in result_array:
        result += init_str[val]
    return "2.0_" + result


def get_sign(url: str, d_c0: str, seed_byte: int | None = None) -> Dict[str, str]:
    """
    Generate dynamic sign headers containing x-zse-96 and x-zst-81.
    """
    ta = "101_3_3.0"
    tc = (
        "3_2.0aR_sn77yn6O92wOB8hPZnQr0EMYxc4f18wNBUgpTQ6nxERFZfTY0-4Lm-h3_tufIwJS8gcxTgJS_"
        "AuPZNcXCTwxI78YxEM20s4PGDwN8gGcYAupMWufIoLVqr4gxrRPOI0cY7HL8qun9g93mFukyigcmebS_Fw"
        "OYPRP0E4rZUrN9DDom3hnynAUMnAVPF_PhaueTFH9fQL39OCCqYTxfb0rfi9wfPhSM6vxGDJo_rBHpQGNmB"
        "BLqPJHK2_w8C9eTVMO9Z9NOrMtfhGH_DgpM-BNM1DOxScLG3gg1Hre1FCXKQcXKkrSL1r9GWDXMk8wqBLNm"
        "bRH96BtOFqVZ7UYG3gC8D9cMS7Y9UrHLVCLZPJO8_CL_6GNCOg_zhJS8PbXmGTcBpgxfkieOPhNfthtf2gC"
        "_qD3YOce8nCwG2uwBOqeMoML9NBC1xb9yk6SuJhHLK7SM6LVfCve_3vLKlqcL6TxL_UosDvHLxrHmWgxBQ8Xs"
    )
    # The sign parameters are joined by '+'
    params_join_str = f"{ta}+{url}+{d_c0}+{tc}"
    params_md5_value = hashlib.md5(params_join_str.encode("utf-8")).hexdigest()

    return {
        "x-zst-81": tc,
        "x-zse-96": get_zse_96(params_md5_value, seed_byte=seed_byte),
    }
