from dataclasses import dataclass

from python_tools.packages.c.cfile import Cfile


@dataclass
class Afile:
    afile: float
    cfile: Cfile
