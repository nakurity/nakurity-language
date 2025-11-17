import re
import runpy
import types

def parse_candle_file(text: str):
    """
    Parse the candle-loader style file into parameters and python instructions.
    """
    # Extract parameters block
    params_match = re.search(r"\.parameters.*?\[below\](.*?)\.terminate \(parameters\)", text, re.S)
    parameters = params_match.group(1).strip() if params_match else ""

    # Extract python instructions block
    instr_match = re.search(r"\.instructions \(python\)(.*?)\.terminate \(instructions\)", text, re.S)
    instructions = instr_match.group(1).strip() if instr_match else ""

    return parameters, instructions


def execute_instructions(parameters: str, instructions: str):
    """
    Execute the Python instructions dynamically, injecting parameters.
    """
    # Create a namespace for execution
    namespace = {}

    # Execute the instructions safely
    exec(instructions, namespace)

    # Look for Candle class
    Candle = namespace.get("Candle")
    if Candle is None:
        raise ValueError("No Candle class found in instructions")

    # Dummy CandleLoader for demonstration
    class CandleLoader:
        def __init__(self):
            self.name = "DemoLoader"

    # Instantiate Candle with parameters
    candle_instance = Candle(parameters, CandleLoader())

    return candle_instance


if __name__ == "__main__":
    # Example: using the text you provided
    candle_text = """
(candle-loader)
  .parameters [below]

    >>>>>>>>>>>>>>>>>>>>> Liquidity Header
    type-include [.nakurility, .masha, .liquidity, .carrier, .outercode]
    executables-include []
    object-locations (default)
    outsiders (candle-loader)
    Liquidity Header <<<<<<<<<<<<<<<<<<<<<

    [head:index]

  .terminate (parameters)
  .instructions (python)
    class Candle:
      def __init__(self, 
        parameters: str,
        candle: CandleLoader
      ):
        self.header_information = parameters
        self.candle = candle

      def environment(self):
        return { 'candle-version': '0.0.1', 'build-time': '2025-11-17T08:37:18Z', 'loader-version': 'put hash here' }
      def launch(self):
        pass # code that candle will actually execute
  .terminate (instructions)
    """

    params, instr = parse_candle_file(candle_text)
    candle = execute_instructions(params, instr)

    print("Parameters extracted:\n", params)
    print("Environment:\n", candle.environment())
