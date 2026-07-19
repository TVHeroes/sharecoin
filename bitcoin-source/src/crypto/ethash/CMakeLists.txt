# Vendored from the ethash project (https://github.com/chfast/ethash),
# Copyright 2018-2019 Pawel Bylica, Apache License 2.0 (see LICENSE in this
# directory) - includes the progpow.cpp/progpow.hpp extension, sourced via
# Ravencoin own integration of the same upstream project (also Apache-2.0,
# same author/license headers throughout). This is the GPU-favorable,
# ASIC-resistant hash used ONLY for the block proof-of-work check (see
# ../../pow.cpp) - every other SHA-256 use in this codebase (txids, merkle
# roots, addresses, checksums) is deliberately left untouched, since those
# are never brute-forced and changing them would not affect which hardware
# is competitive at mining.
add_library(ethash_progpow STATIC EXCLUDE_FROM_ALL
  lib/ethash/ethash.cpp
  lib/ethash/managed.cpp
  lib/ethash/progpow.cpp
  lib/ethash/primes.c
  lib/keccak/keccak.c
  lib/keccak/keccakf1600.c
  lib/keccak/keccakf800.c
)
target_include_directories(ethash_progpow
  PUBLIC
    ${PROJECT_SOURCE_DIR}/src
)
target_link_libraries(ethash_progpow
  PRIVATE
    core_interface
)
set_target_properties(ethash_progpow PROPERTIES
  C_STANDARD 99
  CXX_STANDARD 17
)
