"""Package & Stage button callback — delegates to PythonModule.on_package_clicked."""

import importlib
import hda_scripts.PythonModule as pm
importlib.reload(pm)
pm.on_package_clicked(kwargs)
