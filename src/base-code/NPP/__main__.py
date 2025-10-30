# npp.py
# parses and translates .npp files to the nvm bytecode format (lazy loading)
from pathlib import Path
import os
import uuid
import shlex

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

        # compute default namespace/module path under cwd/runtime/namespaces/@/<name>
        ns_path = self._normalize_path("runtime", "namespaces", "@", name)

        if not os.path.exists(ns_path):
          print("===============================================================================")
          print(f"Modules Check Error: occurred at (bytecode) compile time, inside {Path(self.filename).resolve()}")
          print(f"  With the exception below of: namespace {name} does not exist at default path ({ns_path})")
          print(f"    Have you tried manually installing the {name} module?")
          print()
          print(f"  This error occured at a line with the arguments: {args or '(none)'}")
          print(f"    Try using your code editor's text finder. Paste the argument above there.")
          return "exitcode 1"

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

  def compile(self, mode="compile"):
    """
    mode: "interpret" or "compile"
    - interpret: keep bytecode, runtime will dynamically invoke asm binaries with args
    - compile: resolve only required namespaces/files, embed necessary machine code
    """
    if not self.contents:
      return

    compile_code = []
    load_namespaces = []
    namespace_passage = []
    reached_bytecode = False

    for raw_line in self.contents.split("\n"):
      line = raw_line.strip()
      if not reached_bytecode:
        if line.startswith(":"):
          tag = line[1:].strip()
          if tag == "start-bytecode":
            reached_bytecode = True
          continue
        else:
          continue

      # post start-bytecode
      if line.startswith("<namespace:"):
        namespace_passage.append(line)  # keep args for embedding/dispatch
        continue
      if line.startswith("<load:"):
        # format: <load:name path(/abs/path)>
        # extract name and path
        # replace only prefixes we know
        meta = (
          line.replace("<load:", "", 1)
              .replace(")>", "", 1)
              .replace("path(", "", 1)
        )
        # meta like: "name /abs/path"
        parts = meta.split(" ", 1)
        if len(parts) == 2:
          load_namespaces.append((parts[0], Path(parts[1]).resolve()))
        continue
      # modules and other tags are ignored here; a lower-level parser will process them

    # interpret mode: do not embed code; leave bytecode intact
    if mode == "interpret":
      # flip header flag
      header = self.header.replace("compiled: false", "compiled: true", 1)
      self.contents = self.contents.replace(
        f"[bytecode-header]\n{self.header}\n[end-header]",
        f"[bytecode-header]\n{header}\n[end-header]",
        1
      )
      self.header = header
      # In interpret mode, we rely on runtime to launch asm binaries using <namespace:... args[...]>
      return

    # compile mode: embed only necessary binaries requested by load_namespaces
    for name, ns_path in load_namespaces:
      # Each namespace folder is expected to include either:
      #   - an .nh file exporting symbols (preferred for lazy linkage)
      #   - or a .so/.o/.bin for direct embedding
      # We prioritize .nh, then .so, then .bin
      nh = ns_path / f"{name}.nh"
      so = ns_path / f"{name}.so"
      binf = ns_path / f"{name}.bin"

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
        # embed binary blob as base64 or hex; below uses hex for simplicity
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

      # if none exists, emit a compile-time warning but continue lazily
      compile_code.append(f"warn[namespace<{name}> missing artifacts at {ns_path}]")

    # attach embedded namespaces block after header
    embedded_block = "\n".join(compile_code)
    header = self.header.replace("compiled: false", "compiled: true", 1)

    self.contents = self.contents.replace(
      f"[bytecode-header]\n{self.header}\n[end-header]",
      f"[bytecode-header]\n{header}\n[end-header]\n[embedded-namespaces]\n{embedded_block}\n[end-embedded]",
      1
    )
    self.header = header
