from pathlib import Path
import os
import uuid
import subprocess
import shlex
import json

class NakurityVM:
    """
    Nakurity Virtual Machine (NVM) requirement negotiator.

    Protocol:
    - Probe: run the target binary without args; parse lines shaped as <tag key[type]>.
      Supported tags: requires, format, request, return.
    - If requirements include 'request' and the provided registry is empty/missing,
      return {"status":"pending","registry":[]} and remember state.
    - Otherwise, synthesize inputs from provided args/registry, run the binary with
      those inputs, capture stdout and return {"status":"true","output": "..."}.
    """

    def __init__(self):
        # Store unresolved sessions by a simple counter key if needed in future
        self._pending_state = None

    def _run_no_args(self, binpath: str) -> str:
        try:
            result = subprocess.run(
                [binpath],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout or ""
        except subprocess.CalledProcessError as e:
            # Some tools may exit non-zero when probed; still return their stdout
            return e.stdout or ""
        except Exception as e:
            return f""

    def _parse_reqbytecode(self, text: str):
        """
        Parse lines like:
          <requires input[str]>
          <format input[str]>
          <request input[str]>
          <return console[output]>

        Returns a dict:
        {
          "requires": [{"key":"input","type":"str"}],
          "format": [{"key":"input","type":"str"}],
          "requests": [{"key":"input","type":"str"}],
          "returns": [{"key":"console","type":"output"}]
        }
        """
        spec = {"requires": [], "format": [], "requests": [], "returns": []}
        for raw in text.splitlines():
            line = raw.strip()
            if not (line.startswith("<") and line.endswith(">")):
                continue
            inside = line[1:-1]  # strip <>
            # shape: tag space key[type]
            # or: tag key[type] (no space)
            parts = inside.split(" ", 1)
            tag = parts[0]
            payload = parts[1] if len(parts) > 1 else ""
            # payload could also be in form tag:key[type]
            if not payload and ":" in tag:
                tag, payload = tag.split(":", 1)

            def parse_keytype(s):
                # key[type] -> ("key","type")
                s = s.strip()
                if "[" in s and s.endswith("]"):
                    key, typ = s.split("[", 1)
                    typ = typ[:-1]
                    return key.strip(), typ.strip()
                return s, ""

            if tag == "requires" and payload:
                k, t = parse_keytype(payload)
                spec["requires"].append({"key": k, "type": t})
            elif tag == "format" and payload:
                k, t = parse_keytype(payload)
                spec["format"].append({"key": k, "type": t})
            elif tag == "request" and payload:
                k, t = parse_keytype(payload)
                spec["requests"].append({"key": k, "type": t})
            elif tag == "return" and payload:
                k, t = parse_keytype(payload)
                spec["returns"].append({"key": k, "type": t})
        return spec

    def _synthesize_inputs(self, spec, func_args, registry):
        """
        Produce argv for the binary based on:
        - requires/format keys (e.g., input[str])
        - provided func_args (e.g., ["hello world"])
        - registry (e.g., namespace resolutions, environment)

        Strategy:
        - If there's requires/format for 'input[str]', take the first func_arg joined
          as a single string (preserve quoting semantics handled by interpret).
        - If missing func_args but registry can provide a default (not implemented in detail),
          leave input empty and let binary handle it or return pending earlier.
        """
        argv = []
        # Determine if binary expects 'input[str]'
        expects_input = any(r["key"] == "input" for r in (spec["requires"] + spec["format"]))
        if expects_input:
            if func_args:
                # Combine args into one input string; many CLIs accept single arg
                argv.append(" ".join(func_args))
            else:
                argv.append("")  # placeholder empty input
        # You can expand here to support more keys/types later.
        return argv

    def run(self, func_name: str, binpath: str, func_args: list, registry: dict):
        """
        Entry point for the interpreter.

        Returns JSON strings:
        - {"status":"pending","registry":[]}
        - {"status":"true","output":"..."}
        - {"status":"error","message":"..."}  (only on fatal issues)
        """
        # Step 1: Probe requirements
        probe = self._run_no_args(binpath)
        spec = self._parse_reqbytecode(probe)

        # If VM needs registry but none provided, go pending
        needs_registry = len(spec["requests"]) > 0
        registry_empty = (not registry) or (isinstance(registry, dict) and len(registry) == 0)

        if needs_registry and registry_empty:
            # Store minimal pending state to resume later
            self._pending_state = {
                "func_name": func_name,
                "binpath": binpath,
                "func_args": func_args,
                "spec": spec
            }
            return json.dumps({"status": "pending", "registry": []})

        # Step 2: Synthesize argv
        argv = self._synthesize_inputs(spec, func_args, registry)

        # Step 3: Execute and capture output
        try:
            result = subprocess.run(
                [binpath] + argv,
                capture_output=True,
                text=True,
                check=True
            )
            out = result.stdout or ""
        except subprocess.CalledProcessError as e:
            out = (e.stdout or "") + (e.stderr or "")
        except Exception as e:
            return json.dumps({"status": "error", "message": f"execution failed: {e}"})

        # Step 4: Interpret return contract
        # If returns include console[output], forward captured stdout
        returns_console = any(r["key"] == "console" and r["type"] == "output" for r in spec["returns"])
        if returns_console:
            return json.dumps({"status": "true", "output": out.strip()})

        # Default success when no explicit return contract
        return json.dumps({"status": "true", "output": out.strip()})

    def resume_with_registry(self, registry: dict):
        """
        Resume the pending session with a newly provided registry.
        """
        if not self._pending_state:
            return json.dumps({"status": "error", "message": "no pending state"})
        state = self._pending_state
        self._pending_state = None
        # Reuse run path with known spec; avoid re-probe for determinism
        argv = self._synthesize_inputs(state["spec"], state["func_args"], registry)
        try:
            result = subprocess.run(
                [state["binpath"]] + argv,
                capture_output=True,
                text=True,
                check=True
            )
            out = result.stdout or ""
        except subprocess.CalledProcessError as e:
            out = (e.stdout or "") + (e.stderr or "")
        except Exception as e:
            return json.dumps({"status": "error", "message": f"execution failed: {e}"})

        returns_console = any(r["key"] == "console" and r["type"] == "output" for r in state["spec"]["returns"])
        if returns_console:
            return json.dumps({"status": "true", "output": out.strip()})
        return json.dumps({"status": "true", "output": out.strip()})
