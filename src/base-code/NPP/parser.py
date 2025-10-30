# this module parses and translate .npp files to the nvm bytecode format
from pathlib import Path
import os

class NPP:
  def __init__(self, input):
    self.input = input
    self.filename = input.get("filename", "")
    self.contents = input.get("filecontents", "")

  def parse(self):
    bytecode = f":file {self.filename}\n:start-bytecode\n"
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
        bytecode += f"<namespace:{module[0]} path({path})>\n"
        acknowledged_modules.append(module[0])
      else:
        bytecode += f"<module [{line}]>\n"
    bytecode += ":end-bytecode\n"
