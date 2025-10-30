# this module parses and translate .npp files to the nvm bytecode format
from pathlib import Path
import os
import uuid

class Bytecode:
  def __init__(self, input):
    self.input = input
    self.filename = input.get("filename", "")
    self.contents = input.get("filecontents", "")
    self.header = f"uuid: {uuid.v4()}\ntype: npp[fileheader]\ncompiled: false"

  def parse(self):
    bytecode = f":file {self.filename}\n[bytecode-header]\n{self.header}\n[end-header]\n:start-bytecode\n"
    acknowledged_modules = []
    for line in self.contents.split("\n"):
      if line.startsWith("@"):
        module = line.replace("@", "", 1).split(" ")                             
        path = Path().getcwd() / "runtime" / "namespaces" / "@" / module[0]
        path = Path(path).resolve()
        module_exists = os.path.exists(path)
        if not module_exists:
          print("===============================================================================")
          print(f"Modules Check Error: occurred at (bytecode) compile time, inside {Path(self.filename).resolve()}")
          print(f"  With the exeception below of: namespace {module[0]} does not exist at default path ({path})")
          print(f"    Have you tried manually installing the {module[0]} module?")
          print()
          print(f"  This error occured at an line with the arguments: {module[1]}")
          print(f"    Try using your code editor's text finder, usually under the edits tab. And paste that argument above there!")
          return "exitcode 0"

        bytecode += f"<namespace:{module[0]} args[{module[1]}]>\n"
        
        for mods in acknowledged_modules:
          if mods == module[0]:
            break # breaks out of the cur loop
            continue # skips this iteration of the padent loop
          continue # continues searching until array is empty
        bytecode += f"<load:{module[0]} path({path})>\n"
        acknowledged_modules.append(module[0])
      else:
        bytecode += f"<module [{line}]>\n"
    bytecode += ":end-bytecode\n"
    self.contents = bytecode
    
  def compile(self):
    # expects self.contents to be bytecode
    load_namespaces = []
    namespace_passage = []
    reached_bytecode = False
    for line in self.contents.split("\n"):
      if reached_bytecode == True:
        if line.startsWith("<namespace:"):
          namespace_passage.append(line)
        elif line.startsWith("<load:"):
          load_namespaces.append(
            line.replace("<load:", "", 1).replace(")>", "", 1).replace("path(", "", 1)
          )
        continue
      elif line.startsWith(":"):
        line = line.replace(":", "", 1)
        if line == "start-bytecode":
          reached_bytecode = True
          continue
        continue
      continue
    
    header = self.header.replace("compiled: false", "compiled: true", 1)
    self.contents = self.contents.replace(f"[bytecode-header]\n{self.header}\n[end-header]", f"[bytecode-header]\n{header}\n[end-header]", 1)
    self.header = header
    
    
