from dataclasses import dataclass

from packages.d.src.d.dfile import add_seven


@dataclass
class Afile:
    afile: float


test = add_seven(1)
