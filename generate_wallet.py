#!/usr/bin/env python3
"""
Standalone Sharecoin (SHC) address/keypair generator.

Generates a real secp256k1 keypair entirely on THIS machine - no network
connection, no dependency on any Sharecoin node. Nobody but you ever sees
the private key. That's what makes the resulting address genuinely yours:
whoever holds the private key controls any coins sent to the address, and
only you have it.

Requires: pip install base58 pycryptodome ecdsa
"""
import base58
import secrets
from Crypto.Hash import SHA256, RIPEMD160
from ecdsa import SigningKey, SECP256k1

PUBKEY_ADDRESS_VERSION = 111  # matches Sharecoin's base58Prefixes[PUBKEY_ADDRESS]
SECRET_KEY_VERSION = 239      # matches Sharecoin's base58Prefixes[SECRET_KEY]


def hash160(b: bytes) -> bytes:
    return RIPEMD160.new(SHA256.new(b).digest()).digest()


def main():
    signing_key = SigningKey.generate(curve=SECP256k1, entropy=secrets.token_bytes)
    priv_bytes = signing_key.to_string()

    point = signing_key.verifying_key.pubkey.point
    x = int(point.x()).to_bytes(32, "big")
    prefix = b"\x03" if int(point.y()) % 2 else b"\x02"
    compressed_pubkey = prefix + x

    pubkey_hash = hash160(compressed_pubkey)
    address = base58.b58encode_check(bytes([PUBKEY_ADDRESS_VERSION]) + pubkey_hash).decode()

    wif = base58.b58encode_check(
        bytes([SECRET_KEY_VERSION]) + priv_bytes + b"\x01"  # \x01 = compressed pubkey
    ).decode()

    print("=" * 70)
    print("New Sharecoin (SHC) wallet generated")
    print("=" * 70)
    print()
    print(f"Address (share this to receive mining rewards):")
    print(f"  {address}")
    print()
    print(f"Private key / WIF (KEEP THIS SECRET - anyone with this can")
    print(f"spend any coins sent to the address above):")
    print(f"  {wif}")
    print()
    print("Save the private key somewhere safe (a password manager, an")
    print("encrypted file, on paper). If you lose it, any coins sent to")
    print("this address are gone for good - there is no recovery.")
    print("=" * 70)


if __name__ == "__main__":
    main()
