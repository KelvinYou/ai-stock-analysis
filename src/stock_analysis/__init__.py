try:
    from stock_analysis._version import __version__
except ImportError:
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__ = version("ai-stock-analysis")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"
