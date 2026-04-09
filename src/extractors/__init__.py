# Import all extractor submodules so their @register_extractor decorators run
# and populate the registry. Using absolute import avoids circular-import issues
# that arise from `from src.extractors import submodule` inside __init__.py.
import src.extractors.article  # noqa: F401
import src.extractors.audio  # noqa: F401
import src.extractors.github  # noqa: F401
import src.extractors.youtube  # noqa: F401
