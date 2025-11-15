from dataclasses import dataclass
from nakuritycore.data.defaults import DefaultConfig

@dataclass
class Modes(DefaultConfig):
  modes: Literal['programming-language', 'setup-utility', 'testing-utility', 'mutli-language-tool']
