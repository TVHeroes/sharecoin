// Copyright (c) 2009-present The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <bitcoin-build-config.h> // IWYU pragma: keep

#include <arith_uint256.h>
#include <chain.h>
#include <chainparams.h>
#include <chainparamsbase.h>
#include <clientversion.h>
#include <common/args.h>
#include <common/license_info.h>
#include <common/system.h>
#include <compat/compat.h>
#include <core_io.h>
#include <pow.h>
#include <streams.h>
#include <util/exception.h>
#include <util/strencodings.h>
#include <util/translation.h>

#include <atomic>
#include <cstdio>
#include <functional>
#include <memory>
#include <thread>

static const int CONTINUE_EXECUTION=-1;

const TranslateFn G_TRANSLATION_FUN{nullptr};

static void SetupBitcoinUtilArgs(ArgsManager &argsman)
{
    SetupHelpOptions(argsman);

    argsman.AddArg("-version", "Print version and exit", ArgsManager::ALLOW_ANY, OptionsCategory::OPTIONS);

    argsman.AddCommand("grind", "Perform proof of work on hex header string");
    argsman.AddCommand("netmagic", "Get the network magic bytes of the selected chain");

    SetupChainParamsBaseOptions(argsman);
}

// This function returns either one of EXIT_ codes when it's expected to stop the process or
// CONTINUE_EXECUTION when it's expected to continue further.
static int AppInitUtil(ArgsManager& args, int argc, char* argv[])
{
    SetupBitcoinUtilArgs(args);
    std::string error;
    if (!args.ParseParameters(argc, argv, error)) {
        tfm::format(std::cerr, "Error parsing command line arguments: %s\n", error);
        return EXIT_FAILURE;
    }

    if (HelpRequested(args) || args.GetBoolArg("-version", false)) {
        // First part of help message is specific to this utility
        std::string strUsage = CLIENT_NAME " bitcoin-util utility version " + FormatFullVersion() + "\n";

        if (args.GetBoolArg("-version", false)) {
            strUsage += FormatParagraph(LicenseInfo());
        } else {
            strUsage += "\n"
                "The bitcoin-util tool provides bitcoin related functionality that does not rely on the ability to access a running node. Available [commands] are listed below.\n"
                "\n"
                "Usage:  bitcoin-util [options] [command]\n"
                "or:     bitcoin-util [options] grind <hex-block-header>\n";
            strUsage += "\n" + args.GetHelpMessage();
        }

        tfm::format(std::cout, "%s", strUsage);

        if (argc < 2) {
            tfm::format(std::cerr, "Error: too few parameters\n");
            return EXIT_FAILURE;
        }
        return EXIT_SUCCESS;
    }

    // Check for chain settings (Params() calls are only valid after this clause)
    try {
        SelectParams(args.GetChainType());
    } catch (const std::exception& e) {
        tfm::format(std::cerr, "Error: %s\n", e.what());
        return EXIT_FAILURE;
    }

    return CONTINUE_EXECUTION;
}

// GPU-mined-crypto note: this used to be a hand-rolled multi-threaded
// SHA-256d nonce grinder (grind_task, run across hardware_concurrency()
// threads). Replaced with a single call into MineBlock (pow.cpp) - the
// same real ProgPoW search every other mining path in this codebase uses
// (rpc/mining.cpp's GenerateBlock, node/miner.cpp) - rather than
// reimplementing (and re-parallelizing) the search loop a third time for
// a hash function it no longer even checks against. Single-threaded here
// is a real regression in raw speed for this one CLI tool specifically,
// accepted deliberately: correctness and reuse mattered more than grind
// throughput for what is fundamentally a genesis/test-header utility, not
// a production miner.
static int Grind(const std::vector<std::string>& args, std::string& strPrint)
{
    if (args.size() != 1 && args.size() != 2) {
        strPrint = "Must specify block header to grind, optionally followed by a decimal start_nonce (for splitting the search across parallel processes over disjoint nonce ranges)";
        return EXIT_FAILURE;
    }

    CBlockHeader header;
    if (!DecodeHexBlockHeader(header, args[0])) {
        strPrint = "Could not decode block header";
        return EXIT_FAILURE;
    }

    uint64_t start_nonce{0};
    if (args.size() == 2) {
        const auto parsed{ToIntegral<uint64_t>(args[1])};
        if (!parsed) {
            strPrint = "Could not parse start_nonce";
            return EXIT_FAILURE;
        }
        start_nonce = *parsed;
    }

    uint64_t max_iterations{std::numeric_limits<uint32_t>::max()};
    if (!MineBlock(header, start_nonce, max_iterations)) {
        strPrint = "Could not satisfy difficulty target";
        return EXIT_FAILURE;
    }

    DataStream ss{};
    ss << header;
    strPrint = HexStr(ss);
    return EXIT_SUCCESS;
}

static int NetMagic(const std::vector<std::string>& args, std::string& strPrint)
{
    if (!args.empty()) {
        strPrint = "netmagic does not take arguments";
        return EXIT_FAILURE;
    }

    strPrint = HexStr(Params().MessageStart());
    return EXIT_SUCCESS;
}

MAIN_FUNCTION
{
    ArgsManager& args = gArgs;
    SetupEnvironment();

    try {
        int ret = AppInitUtil(args, argc, argv);
        if (ret != CONTINUE_EXECUTION) {
            return ret;
        }
    } catch (const std::exception& e) {
        PrintExceptionContinue(&e, "AppInitUtil()");
        return EXIT_FAILURE;
    } catch (...) {
        PrintExceptionContinue(nullptr, "AppInitUtil()");
        return EXIT_FAILURE;
    }

    const auto cmd = args.GetCommand();
    if (!cmd) {
        tfm::format(std::cerr, "Error: must specify a command\n");
        return EXIT_FAILURE;
    }

    int ret = EXIT_FAILURE;
    std::string strPrint;
    try {
        if (cmd->command == "grind") {
            ret = Grind(cmd->args, strPrint);
        } else if (cmd->command == "netmagic") {
            ret = NetMagic(cmd->args, strPrint);
        } else {
            assert(false); // unknown command should be caught earlier
        }
    } catch (const std::exception& e) {
        strPrint = std::string("error: ") + e.what();
    } catch (...) {
        strPrint = "unknown error";
    }

    if (strPrint != "") {
        tfm::format(ret == 0 ? std::cout : std::cerr, "%s\n", strPrint);
    }

    return ret;
}
