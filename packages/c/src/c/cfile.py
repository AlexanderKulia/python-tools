from dataclasses import dataclass

from a.afile import Afile
from b.bfile import Bfile


@dataclass
class Cfile:
    afile: Afile
    bfile: Bfile
    cfile: float
