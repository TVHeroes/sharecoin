"""
MSVC-only compatibility fix for src/kernel/chainparams.cpp - not needed on
GCC/Clang (Linux/WSL builds), only needed when building with the MSVC
toolset (Windows).

Upstream Bitcoin Core's uint256{"hex string"} constructor is `consteval`
(must be evaluable at compile time). MSVC's toolset rejects this specific
constructor used inside the assumeutxo data's designated-initializer list
context with "call to immediate function is not a constant expression"
(error C7595), even though the same code compiles fine with GCC/Clang.
uint256::FromUserHex(...).value() is the non-consteval equivalent (parsed
at runtime instead, functionally identical for these fixed literal
values) and compiles cleanly under both toolsets.

Only apply this patch when building on Windows/MSVC. If building on
Linux/WSL with GCC or Clang, skip this script entirely - the original
uint256{"..."} form already works there.
"""
import re

path = 'src/kernel/chainparams.cpp'
text = open(path).read()

pattern = re.compile(r'uint256\{"([a-f0-9]+)"\}')
count = len(pattern.findall(text))
assert count > 0, 'no uint256{"..."} literals found - already patched, or file changed'

text = pattern.sub(r'uint256::FromUserHex("\1").value()', text)

open(path, 'w').write(text)
print(f'chainparams.cpp patched OK, {count} uint256{{"..."}} literals converted for MSVC')
