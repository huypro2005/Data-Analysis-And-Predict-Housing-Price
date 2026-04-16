"""
Root conftest — thêm src/web vào sys.path để các test có thể import app.*
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
