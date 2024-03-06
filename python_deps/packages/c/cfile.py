from dataclasses import dataclass

from python_deps.a.afile import Afile
from python_deps.b.bfile import Bfile


@dataclass
class Cfile:
    afile: Afile
    bfile: Bfile
    cfile: float
