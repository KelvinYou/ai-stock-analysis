# Use the operating system's certificate store instead of certifi's bundle.
#
# Needed wherever a TLS-inspecting corporate proxy sits in front of the network:
# its root CA is installed in the OS trust store but absent from certifi, and it
# is often not RFC 5280 conformant (e.g. missing an Authority Key Identifier),
# which Python 3.13+ rejects outright because it enables VERIFY_X509_STRICT.
# The OS verifier accepts what the OS already trusts, so both problems go away
# without weakening verification or pinning a checked-in CA bundle.
#
# Optional on purpose: on a clean network nothing here is required.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - optional dependency
    pass

try:
    from stock_analysis._version import __version__
except ImportError:
    from importlib.metadata import PackageNotFoundError, version
    try:
        __version__ = version("ai-stock-analysis")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"
