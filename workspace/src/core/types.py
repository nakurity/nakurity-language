# masha_lang/core/types.py
from dataclasses import dataclass

@dataclass
class SourceFile:
    path: str
    content: str
    extension: str

@dataclass
class ASTNode:
    kind: str
    data: dict
