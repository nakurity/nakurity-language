from .npp import Bytecode
bity = Bytecode({
    "filename": "helloworld.npp",
    "filecontents": """
    @import <standardly-native/funcs/print()>
    print "Hello world"
    """
})
bity.parse()
bity.interpret()