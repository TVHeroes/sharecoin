"""
Patches src/CMakeLists.txt - wires the vendored ethash/ProgPoW library
(see README.md's vendoring instructions) into the build as a static target,
linked into both bitcoin_consensus (needs it for primitives/block.cpp's new
GetPoWHeaderHash()) and bitcoin_common (needs it for pow.cpp). The library's
own CMakeLists.txt (in src/crypto/ethash/, not this file - see
bitcoin-cmake-ethash.txt for its content) defines the actual
`ethash_progpow` target this adds a subdirectory for and links against.
"""
path = 'src/CMakeLists.txt'
text = open(path).read()

old_secp = '''include(../cmake/secp256k1.cmake)
add_secp256k1(secp256k1)'''
new_secp = '''include(../cmake/secp256k1.cmake)
add_secp256k1(secp256k1)
add_subdirectory(crypto/ethash)'''
assert old_secp in text, 'secp256k1 anchor not found verbatim'
text = text.replace(old_secp, new_secp, 1)

old_consensus = '''target_link_libraries(bitcoin_consensus
  PRIVATE
    core_interface
    bitcoin_crypto
    secp256k1
)'''
new_consensus = '''target_link_libraries(bitcoin_consensus
  PRIVATE
    core_interface
    bitcoin_crypto
    secp256k1
    ethash_progpow
)'''
assert old_consensus in text, 'bitcoin_consensus target_link_libraries not found verbatim'
text = text.replace(old_consensus, new_consensus, 1)

old_common = '''target_link_libraries(bitcoin_common
  PRIVATE
    core_interface
    bitcoin_consensus
    bitcoin_util
    univalue
    secp256k1
    $<TARGET_NAME_IF_EXISTS:USDT::headers>
    $<$<PLATFORM_ID:Windows>:ws2_32>
)'''
new_common = '''target_link_libraries(bitcoin_common
  PRIVATE
    core_interface
    bitcoin_consensus
    bitcoin_util
    univalue
    secp256k1
    ethash_progpow
    $<TARGET_NAME_IF_EXISTS:USDT::headers>
    $<$<PLATFORM_ID:Windows>:ws2_32>
)'''
assert old_common in text, 'bitcoin_common target_link_libraries not found verbatim'
text = text.replace(old_common, new_common, 1)

open(path, 'w').write(text)
print('src/CMakeLists.txt patched OK')
