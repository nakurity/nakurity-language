# bytecode.py
# parses and translates .npp files to the nvm bytecode format (lazy loading)
from pathlib import Path
import os
import uuid
import subprocess
import shlex
from .nvm import NakurityVM
import json

from nakuritycore.utils.logging import Logger
from nakuritycore.data.config import LoggingConfig

loggy = Logger("Loggy's parent (base-code/npp/bytecode.py)", LoggingConfig(
  level='DEBUG' # Only enable during development, the typical developer using NakurityLang does not need this
))


class Bytecode:
  def __init__(self, input):
    # input: {"filename": str, "filecontents": str}
    self.input = input or {}
    self.filename = self.input.get("filename", "")
    self.contents = self.input.get("filecontents", "")
    # uuid4 (correct api), header lines fixed
    self.header = f"uuid: {uuid.uuid4()}\ntype: npp[fileheader]\ncompiled: false"

  def _normalize_path(self, *parts):
    return Path(Path.cwd(), *parts).resolve()

  def interpret(self):
        """
        Walk the bytecode and lazily invoke external binaries.
        - For each <namespace:NAME args[...]> call the NAME binary with args.
        - For each <module [stmt]> dispatch to the resolved symbol.
        """
        if not self.contents:
            return

        nvm = NakurityVM()
        namespace_resolutions = {}
        reached_bytecode = False

        # Build an interpreter context as we walk; this can be shared in registry when requested
        interpreter_context = {
            "file": str(Path(self.filename).resolve()) if self.filename else "",
            "namespaces": {},     # filled with namespace_resolutions
            "bytecode": [],       # lines post :start-bytecode
        }

        for raw_line in self.contents.split("\n"):
            line = raw_line.strip()
            if not reached_bytecode:
                if line.startswith(":") and line[1:].strip() == "start-bytecode":
                    reached_bytecode = True
                continue

            # Record visible bytecode lines for context
            interpreter_context["bytecode"].append(line)

            if line.startswith("<namespace:"):
                # e.g. <namespace:import args[<standardly-native.funcs.print()>]>
                inside = line[len("<namespace:"):-1]  # strip <namespace: and trailing >
                name, rest = inside.split(" args[", 1)
                args = rest.rstrip("]")
                # call the binary for this namespace
                try:
                    result = subprocess.run(
                        [f"packy/namespaces/@{name}", f"{args}"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    resolved = result.stdout.strip()
                    namespace_resolutions[name] = resolved
                    loggy.debug(f"[interpret] namespace {name} resolved to {resolved}")
                except Exception as e:
                    loggy.debug(f"[interpret] error invoking namespace {name}: {e}")
                continue

            if line.startswith("<module ["):
                import re
                stmt = re.match(r"<module \[(.*)\]>", line).group(1)  # strip <module [ and trailing ]
                # naive split: first token is function, rest are args
                tokens = shlex.split(stmt)
                if not tokens:
                    continue
                func = tokens[0]
                args = tokens[1:]
                # find which namespace provided this func
                # (for now assume it's in namespace 'import' resolution)
                target = namespace_resolutions.get("import")
                if not target:
                    loggy.debug(f"[interpret] no resolution for {func}")
                    continue

                libfile, sym = target.split(":")
                # Derive executable/wrapper path from libpath (e.g., cfd:/print.so -> ./print)
                # You may adapt this mapping to your actual runtime layout.
                binfile = None
                # Heuristic: if libfile endswith .so/.bin, try a sibling executable without extension
                base = os.path.splitext(libfile)[0]
                candidate = base if os.path.isfile(base) else libfile
                binfile = candidate
                # First pass: call VM with current registry (namespaces + context)
                registry = {
                    "namespaces": interpreter_context["namespaces"],
                    "context": {
                        "file": interpreter_context["file"],
                        "symbols": {"func": func, "sym": sym},
                        "bytecode_lines": interpreter_context["bytecode"],
                    }
                }
                resp = nvm.run(func_name=func, binpath=binfile, func_args=args, registry=registry)

                # Handle pending: VM requests registry array to be filled by interpreter
                try:
                    js = json.loads(resp)
                except json.JSONDecodeError:
                    loggy.debug(f"[interpret] VM returned non-JSON: {resp}")
                    continue

                if js.get("status") == "pending" and isinstance(js.get("registry"), list):
                    # Provide a full registry context; here we pass a dict but you requested an array.
                    # We'll convert the dict to a single-element array with one comprehensive object.
                    full_registry = [{
                        "namespaces": interpreter_context["namespaces"],
                        "context": {
                            "file": interpreter_context["file"],
                            "symbols": {"func": func, "sym": sym},
                            "bytecode_lines": interpreter_context["bytecode"],
                        }
                    }]
                    # Resume negotiation
                    resp2 = nvm.resume_with_registry(full_registry)
                    try:
                        js2 = json.loads(resp2)
                    except json.JSONDecodeError:
                        loggy.debug(f"[interpret] VM resume returned non-JSON: {resp2}")
                        continue
                    if js2.get("status") == "true":
                        out = js2.get("output", "")
                        if out:
                            print(out)
                        continue
                    else:
                        loggy.debug(f"[interpret] VM unresolved: {js2}")
                        continue

                if js.get("status") == "true":
                    out = js.get("output", "")
                    if out:
                        print(out)
                    continue

                loggy.debug(f"[interpret] VM error or unknown status: {js}")
                continue

            # ignore other tags (<load:>, comments, etc.)

  def parse(self):
    """
    Translates source lines into a structured bytecode that captures:
      - file metadata
      - namespace requests (@import, @...)
      - module lines (non-directives)
    """
    bytecode = []
    bytecode.append(f":file {self.filename}")
    bytecode.append("[bytecode-header]")
    bytecode.append(self.header)
    bytecode.append("[end-header]")
    bytecode.append(":start-bytecode")

    acknowledged_modules = set()

    for raw_line in self.contents.split("\n"):
      line = raw_line.strip()

      # skip empty lines
      if not line:
        continue

      # strip trailing comments after a directive or statement
      # comment char: '#'
      if "#" in line:
        # preserve comment only if it's the entire line
        if line.startswith("#"):
          # comments in bytecode are kept as metadata lines to help tooling
          bytecode.append(f"<comment [{line[1:].strip()}]>")
          continue
        else:
          # strip inline comment
          line = line.split("#", 1)[0].rstrip()

      # namespace directive: starts with '@'
      if line.startswith("@"):
        # Example: @import <standardly-native.funcs.print()>
        directive = line[1:].strip()
        # first token is name, rest are arguments (if any)
        tokens = shlex.split(directive)
        name = tokens[0]
        args = " ".join(tokens[1:]) if len(tokens) > 1 else ""

        # compute default namespace/module path under cwd/runtime/namespaces/@<name>
        ns_path = self._normalize_path("packy", "namespaces", f"@{name}")

        # args is the correct package path (e.g., <standardly-native.funcs()>)
        # sanitize the argument path (remove surrounding <> and parentheses)
        clean_pkg = args.strip("<>()").replace(".", os.sep)
        pkg_path = self._normalize_path("packy", "modules", f"@{clean_pkg}")
        if not os.path.exists(ns_path) or not os.path.exists(pkg_path):
            print("===============================================================================")
            print(f"Modules Check Error: occurred at (bytecode) compile time, inside {Path(self.filename).resolve()}")
            print(f"  Neither namespace nor package '{name}' exists.")
            print(f"    Expected paths:")
            print(f"      Namespace: {ns_path}")
            print(f"      Package:   {pkg_path}")
            print(f"  Have you installed or built the {name} package?")
            print()
            print(f"  This error occurred at a line with the arguments: {args or '(none)'}")
            print(f"    Try using your code editor's text finder. Paste the argument above there.")
            return "exitcode 1"

        # prefer package path if namespace is missing
        # if not os.path.exists(ns_path) and os.path.exists(pkg_path):
        #     ns_path = pkg_path # This is stupid af

        # record namespace request and args
        bytecode.append(f"<namespace:{name} args[{args}]>")

        # ensure load instruction is emitted only once per namespace
        if name not in acknowledged_modules:
          bytecode.append(f"<load:{name} path({ns_path})>")
          acknowledged_modules.add(name)

        # import directive can also materialize a higher-level request:
        # leave it to the import binary; we just capture the request.
        continue

      # regular module line
      bytecode.append(f"<module [{line}]>")

    bytecode.append(":end-bytecode")
    self.contents = "\n".join(bytecode)

  def compile(self):
    """
    mode: "compile"
    - resolve required namespaces/files
    - embed necessary machine code
    - catch missing artifacts early
    """
    if not self.contents:
      print("Compile Error: no bytecode to compile. Did you run parse() first?")
      return "exitcode 1"

    compile_code = []
    load_namespaces = []
    namespace_passage = []
    reached_bytecode = False
    file_resolved = str(Path(self.filename).resolve())

    for raw_line in self.contents.split("\n"):
      line = raw_line.strip()
      if not reached_bytecode:
        if line.startswith(":") and line[1:].strip() == "start-bytecode":
          reached_bytecode = True
          continue

        if not line:
          continue

        if line.startswith("<namespace:"):
          namespace_passage.append(line)
          continue

        if line.startswith("<load:"):
          meta = (
            line.replace("<load:", "", 1)
              .replace(")>", "", 1)
              .replace("path(", "", 1)
            )
          parts = meta.split(" ", 1)
          if len(parts) == 2:
            name, pth = parts
            resolved_path = Path(pth).resolve()
            if not resolved_path.exists():
              print("===============================================================================")
              print(f"Compile Error: Namespace load path not found")
              print(f"  Namespace: {name}")
              print(f"  Expected path: {resolved_path}")
              print(f"  Occurred at: {file_resolved}")
              return "exitcode 1"
            load_namespaces.append((name, resolved_path))
          else:
            print("===============================================================================")
            print(f"Compile Error: malformed load directive '{line}'")
            print(f"  Occurred at: {file_resolved}")
            return "exitcode 1"
          continue

    if not reached_bytecode:
      print("===============================================================================")
      print("Compile Error: no ':start-bytecode' tag found. Invalid NPP structure.")
      print(f"  File: {file_resolved}")
      return "exitcode 1"

    if not load_namespaces:
      print("===============================================================================")
      print("Compile Error: no namespaces found to embed.")
      print(f"  File: {file_resolved}")
      return "exitcode 1"

    for name, ns_path in load_namespaces:
      nh = ns_path / f"{name}.nh"
      so = ns_path / f"{name}.so"
      binf = ns_path / f"{name}.bin"

      if not any([nh.exists(), so.exists(), binf.exists()]):
        print("===============================================================================")
        print(f"Compile Error: missing artifacts for namespace '{name}'")
        print(f"  Expected one of: {nh}, {so}, or {binf}")
        print(f"  Occurred at: {file_resolved}")
        return "exitcode 1"

      if nh.exists():
        with open(nh, "r", encoding="utf-8") as f:
          content = f.read()
        compile_code.append(f"start[namespace<{name}>]")
        compile_code.append(content)
        compile_code.append("end")
        continue

      if so.exists():
        with open(so, "rb") as f:
          content = f.read()
          blob = content.hex()
        compile_code.append(f"start[namespace<{name}>]")
        compile_code.append(f"embed[so-hex:{blob}]")
        compile_code.append("end")
        continue

      if binf.exists():
        with open(binf, "rb") as f:
          content = f.read()
          blob = content.hex()
        compile_code.append(f"start[namespace<{name}>]")
        compile_code.append(f"embed[bin-hex:{blob}]")
        compile_code.append("end")
        continue

    # sanity check header before embedding
    if "compiled: false" not in self.header:
      print("===============================================================================")
      print("Compile Error: header mismatch or already compiled. Cannot recompile.")
      print(f"  File: {file_resolved}")
      return "exitcode 1"

    embedded_block = "\n".join(compile_code)
    header = self.header.replace("compiled: false", "compiled: true", 1)

    self.contents = self.contents.replace(
      f"[bytecode-header]\n{self.header}\n[end-header]",
      f"[bytecode-header]\n{header}\n[end-header]\n[embedded-namespaces]\n{embedded_block}\n[end-embedded]",
      1
    )
    self.header = header

    # Final sanity check
    if "[embedded-namespaces]" not in self.contents:
      print("===============================================================================")
      print("Compile Error: embedding failed — no [embedded-namespaces] block found.")
      print(f"  File: {file_resolved}")
      return "exitcode 1"

    print(f"✅ Successfully compiled {self.filename}")
    return "exitcode 0"
