import os
import sys
import typing as t
sys.path.insert(0, os.path.abspath('../../src'))

project = 'gunz-utils'
copyright = '2025, Yeremia Gunawan Adhisantoso'
author = 'Yeremia Gunawan Adhisantoso'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'myst_parser',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'gunz_ml': ('https://gunz-ml.pages.dev/', None),
    'gunz_cm': ('https://gunz-cm.pages.dev/', None),
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Mock imports for external dependencies
autodoc_mock_imports = ["pydantic", "pydantic_core", "rich", "git", "typing_extensions", "loguru"]

# Napoleon settings
napoleon_google_docstring = False
napoleon_numpy_docstring = True
