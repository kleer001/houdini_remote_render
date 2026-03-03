"""Verify button callback — delegates to PythonModule.on_verify_clicked."""

import importlib
import hda_scripts.PythonModule as pm
importlib.reload(pm)
pm.on_verify_clicked(kwargs)
