from dataclasses import dataclass

from python_deps.packages.c.cfile import Cfile


@dataclass
class Afile:
    afile: float
    cfile: Cfile
