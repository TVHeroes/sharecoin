"""
Removes remaining user-visible "Bitcoin" strings from the fork - GUI
tooltips/labels, RPC help/error text, CLI help text, default paths, and
app-identity constants. Deliberately does NOT touch (and none of these
patches should):
  - Copyright headers ("Copyright (c) ... The Bitcoin Core developers") -
    the MIT license requires preserving them; this fork's own build
    identifies as "Sharecoin Core" via CLIENT_NAME (below), and
    common/license_info.cpp has its own deliberate upstream safeguard
    that automatically re-appends "The Bitcoin Core developers" to the
    generated About-box/--version text whenever CLIENT_NAME no longer
    contains "Bitcoin Core" - already doing its job correctly, not
    touched here.
  - BIP references (BIP32, BIP34, BIP141, BIP174/PSBT, etc.) - real
    external Bitcoin standard names this code correctly implements, not
    this fork's own branding.
  - Academic paper citations (e.g. "Eclipse Attacks on Bitcoin's
    Peer-to-Peer Network") - real external research titles.

Run each section independently against its own file; none depend on each
other or on any other patch script in this repo.
"""

def apply_fixes(path, fixes, allow_missing=False):
    text = open(path, encoding='utf-8').read()
    for old, new in fixes:
        if old not in text:
            if allow_missing:
                print(f'  (skip, not found: {path})')
                continue
            raise AssertionError(f'pattern not found verbatim in {path}:\n{old[:100]}')
        text = text.replace(old, new)
    open(path, 'w', encoding='utf-8').write(text)
    print(f'{path}: patched OK')


# ---- CMakeLists.txt: the build's own identity ----
apply_fixes('CMakeLists.txt', [
    ('set(CLIENT_NAME "Bitcoin Core")', 'set(CLIENT_NAME "Sharecoin Core")'),
])

# ---- BitcoinUnits: BTC -> SHC display strings (class/enum names unchanged -
# internal identifiers, not user-visible) ----
apply_fixes('src/qt/bitcoinunits.cpp', [
    ('case Unit::BTC: return QString("BTC");', 'case Unit::BTC: return QString("SHC");'),
    ('case Unit::mBTC: return QString("mBTC");', 'case Unit::mBTC: return QString("mSHC");'),
    ('case Unit::uBTC: return QString::fromUtf8("µBTC (bits)");', 'case Unit::uBTC: return QString::fromUtf8("µSHC (bits)");'),
    ('case Unit::BTC: return QString("Bitcoins");', 'case Unit::BTC: return QString("Sharecoin");'),
    ('Milli-Bitcoins', 'Milli-Sharecoin'),
    ('Micro-Bitcoins', 'Micro-Sharecoin'),
])

# ---- Default datadir: ~/.bitcoin -> ~/.sharecoin (all platforms), and
# remove the Windows "legacy %APPDATA%\Bitcoin" fallback entirely - that
# check exists upstream only to help users migrating from an old real
# Bitcoin Core install, which doesn't apply here (Sharecoin was never
# called "Bitcoin"), and keeping it would risk silently defaulting to a
# real Bitcoin Core user's own wallet directory if one exists on the same
# machine. ----
apply_fixes('src/common/args.cpp', [
    (
'''fs::path GetDefaultDataDir()
{
    // Windows:
    //   old: C:\\Users\\Username\\AppData\\Roaming\\Bitcoin
    //   new: C:\\Users\\Username\\AppData\\Local\\Bitcoin
    // macOS: ~/Library/Application Support/Bitcoin
    // Unix-like: ~/.bitcoin
#ifdef WIN32
    // Windows
    // Check for existence of datadir in old location and keep it there
    fs::path legacy_path = GetSpecialFolderPath(CSIDL_APPDATA) / "Bitcoin";
    if (fs::exists(legacy_path)) return legacy_path;

    // Otherwise, fresh installs can start in the new, "proper" location
    return GetSpecialFolderPath(CSIDL_LOCAL_APPDATA) / "Bitcoin";
#else
    fs::path pathRet;
    char* pszHome = getenv("HOME");
    if (pszHome == nullptr || strlen(pszHome) == 0)
        pathRet = fs::path("/");
    else
        pathRet = fs::path(pszHome);
#ifdef __APPLE__
    // macOS
    return pathRet / "Library/Application Support/Bitcoin";
#else
    // Unix-like
    return pathRet / ".bitcoin";
#endif
#endif
}''',
'''fs::path GetDefaultDataDir()
{
    // Windows: C:\\Users\\Username\\AppData\\Local\\Sharecoin
    // macOS: ~/Library/Application Support/Sharecoin
    // Unix-like: ~/.sharecoin
    //
    // GPU-mined-crypto/Sharecoin note: upstream Bitcoin Core also checks a
    // legacy %APPDATA%\\Bitcoin path here, kept for users upgrading from an
    // old Bitcoin Core install. That check is deliberately NOT carried over
    // here - Sharecoin was never called "Bitcoin", so there's no legitimate
    // legacy folder to migrate from, and checking %APPDATA%\\Bitcoin would
    // risk accidentally defaulting to a real Bitcoin Core user's own wallet
    // directory if one happens to exist on the same machine.
#ifdef WIN32
    // Windows
    return GetSpecialFolderPath(CSIDL_LOCAL_APPDATA) / "Sharecoin";
#else
    fs::path pathRet;
    char* pszHome = getenv("HOME");
    if (pszHome == nullptr || strlen(pszHome) == 0)
        pathRet = fs::path("/");
    else
        pathRet = fs::path(pszHome);
#ifdef __APPLE__
    // macOS
    return pathRet / "Library/Application Support/Sharecoin";
#else
    // Unix-like
    return pathRet / ".sharecoin";
#endif
#endif
}'''
    ),
    ('const char * const BITCOIN_CONF_FILENAME = "bitcoin.conf";',
     'const char * const BITCOIN_CONF_FILENAME = "sharecoin.conf";'),
])

# ---- Intro dialog: fix a real factual bug, not just branding - this told
# Sharecoin users their blockchain "initially launched" in 2009 (Bitcoin's
# real launch year) and referenced "the Bitcoin block chain" ----
apply_fixes('src/qt/intro.cpp', [
    (
'''    ui->lblExplanation1->setText(ui->lblExplanation1->text()
        .arg(CLIENT_NAME)
        .arg(m_blockchain_size_gb)
        .arg(2009)
        .arg(tr("Bitcoin"))
    );''',
'''    // GPU-mined-crypto/Sharecoin note: upstream hardcodes "Bitcoin" and 2009
    // here (Bitcoin's real launch year) - factually wrong for this fork,
    // not just off-brand, since Sharecoin's own chain didn't exist until
    // 2026. Uses CLIENT_NAME and the real year instead.
    ui->lblExplanation1->setText(ui->lblExplanation1->text()
        .arg(CLIENT_NAME)
        .arg(m_blockchain_size_gb)
        .arg(2026)
        .arg(CLIENT_NAME)
    );'''
    ),
    ('tr("%1 will download and store a copy of the Bitcoin block chain.").arg(CLIENT_NAME)',
     'tr("%1 will download and store a copy of the Sharecoin block chain.").arg(CLIENT_NAME)'),
])

# ---- Payment URI scheme: bitcoin: -> sharecoin: - a real interoperability
# fix, not just cosmetic: if left as "bitcoin:", this wallet would compete
# with a real Bitcoin Core install (if one exists on the same machine) to
# register as the OS handler for bitcoin: links. Also renames the local
# IPC single-instance server name (BitcoinQt -> SharecoinQt) for the same
# reason, though that name already gets a datadir-hash appended so
# collisions were already unlikely. ----
apply_fixes('src/qt/paymentserver.cpp', [
    ('const QString BITCOIN_IPC_PREFIX("bitcoin:");', 'const QString BITCOIN_IPC_PREFIX("sharecoin:");'),
    ('// bitcoin: URI', '// sharecoin: URI'),
    ('QString name("BitcoinQt");', 'QString name("SharecoinQt");'),
    ('tr("URI cannot be parsed! This can be caused by an invalid Bitcoin address or malformed URI parameters.")',
     'tr("URI cannot be parsed! This can be caused by an invalid Sharecoin address or malformed URI parameters.")'),
])

# ---- Message signing magic string: a real behavioral change, not just
# cosmetic - a Sharecoin wallet signing a message that self-identifies as
# a "Bitcoin Signed Message" is actively wrong/confusing, and there's no
# reason to keep cross-compatibility with Bitcoin's own message-signing
# scheme for a genuinely different, unrelated coin. ----
apply_fixes('src/common/signmessage.cpp', [
    ('const std::string MESSAGE_MAGIC = "Bitcoin Signed Message:\\n";',
     'const std::string MESSAGE_MAGIC = "Sharecoin Signed Message:\\n";'),
])

# ---- Internal, never-displayed key self-test string (harmless either way,
# changed only for consistency - this value is hashed with random bytes
# purely to verify a freshly generated keypair works, then discarded) ----
apply_fixes('src/key.cpp', [
    ('"Bitcoin key verification\\n"', '"Sharecoin key verification\\n"'),
])

# ---- Qt application identity constants - used for QSettings storage
# location and window-manager class hints; renaming avoids Sharecoin's own
# app settings/single-instance detection colliding with a real Bitcoin-Qt
# install's on the same machine. ----
apply_fixes('src/qt/guiconstants.h', [
    ('#define QAPP_ORG_NAME "Bitcoin"', '#define QAPP_ORG_NAME "Sharecoin"'),
    ('#define QAPP_APP_NAME_DEFAULT "Bitcoin-Qt"', '#define QAPP_APP_NAME_DEFAULT "Sharecoin-Qt"'),
    ('#define QAPP_APP_NAME_TESTNET "Bitcoin-Qt-testnet"', '#define QAPP_APP_NAME_TESTNET "Sharecoin-Qt-testnet"'),
    ('#define QAPP_APP_NAME_TESTNET4 "Bitcoin-Qt-testnet4"', '#define QAPP_APP_NAME_TESTNET4 "Sharecoin-Qt-testnet4"'),
    ('#define QAPP_APP_NAME_SIGNET "Bitcoin-Qt-signet"', '#define QAPP_APP_NAME_SIGNET "Sharecoin-Qt-signet"'),
    ('#define QAPP_APP_NAME_REGTEST "Bitcoin-Qt-regtest"', '#define QAPP_APP_NAME_REGTEST "Sharecoin-Qt-regtest"'),
])

# ---- Windows "run at startup" shortcut filenames ----
apply_fixes('src/qt/guiutil.cpp', [
    ('GetSpecialFolderPath(CSIDL_STARTUP) / "Bitcoin.lnk"', 'GetSpecialFolderPath(CSIDL_STARTUP) / "Sharecoin.lnk"'),
    ('GetSpecialFolderPath(CSIDL_STARTUP) / "Bitcoin (testnet).lnk"', 'GetSpecialFolderPath(CSIDL_STARTUP) / "Sharecoin (testnet).lnk"'),
    ('strprintf("Bitcoin (%s).lnk", ChainTypeToString(chain))', 'strprintf("Sharecoin (%s).lnk", ChainTypeToString(chain))'),
    ('// check for Bitcoin*.lnk', '// check for Sharecoin*.lnk'),
    ('QObject::tr("Enter a Bitcoin address (e.g. %1)")', 'QObject::tr("Enter a Sharecoin address (e.g. %1)")'),
    ('optionFile << "Name=Bitcoin\\n";', 'optionFile << "Name=Sharecoin\\n";'),
    ('optionFile << strprintf("Name=Bitcoin (%s)\\n", ChainTypeToString(chain));',
     'optionFile << strprintf("Name=Sharecoin (%s)\\n", ChainTypeToString(chain));'),
])

# ---- Remaining GUI tooltips/status tips/labels ----
apply_fixes('src/qt/bitcoingui.cpp', [
    ('tr("Send coins to a Bitcoin address")', 'tr("Send coins to a Sharecoin address")'),
    ('tr("Sign messages with your Bitcoin addresses to prove you own them")',
     'tr("Sign messages with your Sharecoin addresses to prove you own them")'),
    ('tr("Verify messages to ensure they were signed with specified Bitcoin addresses")',
     'tr("Verify messages to ensure they were signed with specified Sharecoin addresses")'),
    ('tr("Show the %1 help message to get a list with possible Bitcoin command-line options")',
     'tr("Show the %1 help message to get a list with possible Sharecoin command-line options")'),
    ('tr("%n active connection(s) to Bitcoin network.", "", count)',
     'tr("%n active connection(s) to Sharecoin network.", "", count)'),
])
apply_fixes('src/qt/editaddressdialog.cpp', [
    ('tr("The entered address \\"%1\\" is not a valid Bitcoin address.")',
     'tr("The entered address \\"%1\\" is not a valid Sharecoin address.")'),
])
apply_fixes('src/qt/sendcoinsdialog.cpp', [
    ('tr("Warning: Invalid Bitcoin address")', 'tr("Warning: Invalid Sharecoin address")'),
])
apply_fixes('src/qt/addressbookpage.cpp', [
    ('tr("These are your Bitcoin addresses for sending payments. Always check the amount and the receiving address before sending coins.")',
     'tr("These are your Sharecoin addresses for sending payments. Always check the amount and the receiving address before sending coins.")'),
    (r'''tr("These are your Bitcoin addresses for receiving payments. Use the 'Create new receiving address' button in the receive tab to create new addresses.\nSigning is only possible with addresses of the type 'legacy'.")''',
     r'''tr("These are your Sharecoin addresses for receiving payments. Use the 'Create new receiving address' button in the receive tab to create new addresses.\nSigning is only possible with addresses of the type 'legacy'.")'''),
])

# ---- Qt .ui form files: tooltips/labels not driven by any .cpp string ----
apply_fixes('src/qt/forms/debugwindow.ui', [
    ('Network addresses that your Bitcoin node is currently using', 'Network addresses that your Sharecoin node is currently using'),
])
apply_fixes('src/qt/forms/optionsdialog.ui', [
    ('Automatically open the Bitcoin client port on the router', 'Automatically open the Sharecoin client port on the router'),
    ('Connect to the Bitcoin network through a SOCKS5 proxy.', 'Connect to the Sharecoin network through a SOCKS5 proxy.'),
    ('Connect to the Bitcoin network through a separate SOCKS5 proxy for Tor onion services.',
     'Connect to the Sharecoin network through a separate SOCKS5 proxy for Tor onion services.'),
])
apply_fixes('src/qt/forms/overviewpage.ui', [
    ('Your wallet automatically synchronizes with the Bitcoin network', 'Your wallet automatically synchronizes with the Sharecoin network'),
])
apply_fixes('src/qt/forms/receivecoinsdialog.ui', [
    ('The message will not be sent with the payment over the Bitcoin network.', 'The message will not be sent with the payment over the Sharecoin network.'),
])
apply_fixes('src/qt/forms/sendcoinsentry.ui', [
    ('The Bitcoin address to send the payment to', 'The Sharecoin address to send the payment to'),
    ('attached to the bitcoin: URI', 'attached to the sharecoin: URI'),
    ('This message will not be sent over the Bitcoin network.', 'This message will not be sent over the Sharecoin network.'),
])
apply_fixes('src/qt/forms/signverifymessagedialog.ui', [
    ('The Bitcoin address to sign the message with', 'The Sharecoin address to sign the message with'),
    ('prove you own this Bitcoin address', 'prove you own this Sharecoin address'),
    ('The Bitcoin address the message was signed with', 'The Sharecoin address the message was signed with'),
    ('signed with the specified Bitcoin address', 'signed with the specified Sharecoin address'),
])

# ---- RPC help/error text ----
apply_fixes('src/rpc/mempool.cpp', [
    ("Ensure you're running Bitcoin Core with -privatebroadcast=1.",
     "Ensure you're running Sharecoin Core with -privatebroadcast=1."),
])
apply_fixes('src/rpc/blockchain.cpp', [
    ('"The Bitcoin address (only if a well-defined address exists)"',
     '"The Sharecoin address (only if a well-defined address exists)"'),
])
apply_fixes('src/rpc/util.cpp', [
    ('"The Bitcoin address (only if a well-defined address exists)"',
     '"The Sharecoin address (only if a well-defined address exists)"'),
])
apply_fixes('src/rpc/rawtransaction_util.cpp', [
    ('std::string("Invalid Bitcoin address: ") + name_', 'std::string("Invalid Sharecoin address: ") + name_'),
])
apply_fixes('src/rpc/rawtransaction.cpp', [
    ('"The Bitcoin address (only if a well-defined address exists)"',
     '"The Sharecoin address (only if a well-defined address exists)"'),
])
apply_fixes('src/wallet/wallettool.cpp', [
    ('tfm::format(std::cout, "The dumpfile may contain private keys. To ensure the safety of your Bitcoin, do not share the dumpfile.\\n");',
     'tfm::format(std::cout, "The dumpfile may contain private keys. To ensure the safety of your Sharecoin, do not share the dumpfile.\\n");'),
])
apply_fixes('src/wallet/rpc/addresses.cpp', [
    ('"Returns a new Bitcoin address for receiving payments.\\n"', '"Returns a new Sharecoin address for receiving payments.\\n"'),
    ('"Returns a new Bitcoin address, for receiving change.\\n"', '"Returns a new Sharecoin address, for receiving change.\\n"'),
    ('throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Invalid Bitcoin address");',
     'throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Invalid Sharecoin address");'),
])
apply_fixes('src/wallet/rpc/coins.cpp', [
    ('throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Invalid Bitcoin address");',
     'throw JSONRPCError(RPC_INVALID_ADDRESS_OR_KEY, "Invalid Sharecoin address");'),
    ('std::string("Invalid Bitcoin address: ") + input.get_str()',
     'std::string("Invalid Sharecoin address: ") + input.get_str()'),
])

# ---- bitcoind --help banner text ----
apply_fixes('src/bitcoind.cpp', [
    ('"The " CLIENT_NAME " daemon (bitcoind) is a headless program that connects to the Bitcoin network to validate and relay transactions and blocks, as well as relaying addresses.\\n\\n"',
     '"The " CLIENT_NAME " daemon (sharecoind) is a headless program that connects to the Sharecoin network to validate and relay transactions and blocks, as well as relaying addresses.\\n\\n"'),
    ('"It provides the backbone of the Bitcoin network and its RPC, REST and ZMQ services can provide various transaction, block and address-related services.\\n\\n"',
     '"It provides the backbone of the Sharecoin network and its RPC, REST and ZMQ services can provide various transaction, block and address-related services.\\n\\n"'),
])

print("Branding sweep complete")
