from src.core.types import ASTNode
from pathlib import Path

import os

class OuterlandsSymbolProvider:
    def __init__(self, pm):
        self.pm = pm

    def tokens_to_ast(self, tokens):
        # Example syntax: outerlands require["root/a.py"]
        payload = " ".join(tokens[1:])
        # Strip surrounding quotes if present
        if len(payload) >= 2 and payload.startswith('require["') and payload.endswith('"]'):
            payload = payload[9:-2] #
            if payload.startswith('root'):
                payload = payload.replace('root',
                    str(Path(
                        Path(
                            os.path.abspath(__file__)
                        ) / '..' / '..' / '..' / '..' / '..'
                    )), 1)
                payload = Path(payload).resolve()
            return ASTNode(kind="Outerlands", data={"path": payload, "alias": "require"})
        return ASTNode(kind='Outerlands', data={'alias': 'unknown alias'})

    # def tokens_to_ast(self, tokens, source_lines=None, current_index=0):
    #     """
    #     Supports syntax:
    #       outerlands:module.create [below]
    #         .type python
    #         .name example_file
    #         .parent cwd()
    #     ...code...
    #     [finished-definition]
    #     """
    #     # Defensive checks
    #     if not tokens:
    #         return ASTNode(kind="Outerlands", data={})

    #     # Parse the header: e.g. outerlands:module.create [below]
    #     head = tokens[0]
    #     mode = tokens[1] if len(tokens) > 1 else None

    #     # Start collecting configuration + payload
    #     config = {}
    #     payload_lines = []
    #     in_payload = False

    #     if source_lines is None:
    #         # Fallback if we have no context (shouldn't happen for real parser)
    #         return ASTNode(kind="Outerlands", data={"mode": mode})

    #     # Walk lines after the header
    #     for i in range(current_index + 1, len(source_lines)):
    #         line = source_lines[i].rstrip("\n")
    #         stripped = line.strip()

    #         # Stop at [finished-definition]
    #         if stripped == "[finished-definition]":
    #             break

    #         # Detect key-value attributes
    #         if stripped.startswith(".") and not in_payload:
    #             parts = stripped[1:].split(" ", 1)
    #             key = parts[0]
    #             val = parts[1].strip() if len(parts) > 1 else ""
    #             config[key] = val
    #             continue

    #         # Detect [below] payload start
    #         if stripped.endswith("[below]"):
    #             in_payload = True
    #             continue

    #         # Inside payload area
    #         if in_payload:
    #             # Skip pure empty indented lines
    #             if not stripped and not line.startswith("  "):
    #                 continue
    #             # Capture code content (dedent if needed)
    #             payload_lines.append(line[2:] if line.startswith("  ") else line)

    #     payload = "\n".join(payload_lines)

    #     return ASTNode(
    #         kind="Outerlands",
    #         data={
    #             "mode": mode,
    #             "config": config,
    #             "text": payload
    #         }
    #     )


class OuterlandsExecutor:
    def __init__(self, pm):
        self.pm = pm

    def can_handle(self, node: ASTNode) -> bool:
        return node.kind == "Outerlands"
    
    def execute(self, node: ASTNode):
        # Plugin-provided behavior

        alias = node.data.get("alias", "")

        if alias == "require":
            self.pm._import_file(node.data.get("path", ""))
        
    # def execute(self, node: ASTNode):
    #     data = node.data
    #     cfg = data.get("config", {})
    #     code = data.get("text", "")

    #     filetype = cfg.get("type", "python")
    #     name = cfg.get("name", "unnamed_module")
    #     parent = cfg.get("parent", "cwd()")

    #     print(f"[OuterlandsExecutor] Creating {filetype} module '{name}' under {parent}")
    #     print("--- Code ---")
    #     print(code)
    #     print("------------")

    #     # Real behavior could dispatch to a type-specific handler
    #     if filetype == "python":
    #         try:
    #             exec(code, {})
    #         except Exception as e:
    #             print(f"[OuterlandsExecutor error] {e}")

def create_outerlands_symbol(pm):
    return OuterlandsSymbolProvider(pm)

def create_executor(pm):
    return OuterlandsExecutor(pm)

def register(pm, module_key: str):
    # NOTE: factory_name must be the name of the factory function as a string
    pm.registry.register_executor(kind="Outerlands", module_path=module_key, factory_name="create_executor")
    pm.registry.register_symbol(
        symbol_name="outerlands", 
        module_path=module_key, 
        factory_name="create_outerlands_symbol"
    )