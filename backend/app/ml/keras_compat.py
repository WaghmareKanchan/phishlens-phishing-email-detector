"""Windows fix for saving / loading .keras files that contain a text vocabulary.

Why this exists
---------------
The LSTM's TextVectorization layer stores its vocabulary as a text file inside the .keras archive.
Keras writes and reads that file with a plain ``open(path, "r")`` (no encoding), so Python falls
back to the OS default:

* Linux / macOS  -> UTF-8   (works)
* Windows        -> cp1252  (fails: "'charmap' codec can't decode byte 0x9d ...")

The vocabulary contains words like "être" or "it's" (curly apostrophe), so a model trained on Linux
could not be loaded on Windows (and training on Windows could fail while saving).

``utf8_text_files()`` makes every text-mode ``open()`` without an explicit encoding use UTF-8 while
a model is being saved or loaded, then restores the normal behaviour.
"""
from __future__ import annotations

import builtins
import contextlib
import threading

_lock = threading.RLock()


@contextlib.contextmanager
def utf8_text_files():
    with _lock:
        real_open = builtins.open

        def open_utf8(file, mode="r", buffering=-1, encoding=None, *args, **kwargs):
            if encoding is None and "b" not in mode:
                encoding = "utf-8"
            return real_open(file, mode, buffering, encoding, *args, **kwargs)

        builtins.open = open_utf8
        try:
            yield
        finally:
            builtins.open = real_open
