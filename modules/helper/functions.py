# -*- coding: utf-8 -*-
from importlib.machinery import SourceFileLoader


def get_class_from_iname(python_module_path, name):
    python_module = SourceFileLoader(name, python_module_path).load_module()
    python_module_items = [item.upper() for item in dir(python_module)]
    if name.upper() in python_module_items:
        class_name = dir(python_module)[python_module_items.index(name.upper())]
        return getattr(python_module, class_name)
    raise ValueError('Unable to find class from name')
