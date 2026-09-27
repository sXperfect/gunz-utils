import os
import sys
from importlib.metadata import PackageNotFoundError, version as package_version

sys.path.insert(0, os.path.abspath('../../src'))

project = 'gunz-utils'
copyright = '2025, Yeremia Gunawan Adhisantoso'
author = 'Yeremia Gunawan Adhisantoso'
try:
    release = package_version("gunz-utils")
except PackageNotFoundError:
    release = "0+unknown"

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'myst_parser',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Mock imports for external dependencies
autodoc_mock_imports = [
    "pydantic", "pydantic_core", "cryptography", "git", "gitpython", "loguru",
]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
