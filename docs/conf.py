import os
import sys
sys.path.insert(0, os.path.abspath('../src'))

project = 'Gunz Utils'
copyright = '2025, Yeremia Gunawan Adhisantoso'
author = 'Yeremia Gunawan Adhisantoso'
release = '1.0.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'myst_parser',
]

html_theme = 'furo'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
