from dataclasses import dataclass

from python_tools.libs.a.afile import Afile
from python_tools.packages.b.bfile import Bfile


@dataclass
class Cfile:
    afile: Afile
    bfile: Bfile
    cfile: float
