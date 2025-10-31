from .npp import Bytecode
bity = Bytecode({
    "filename": "helloworld.npp",
    "filecontents": """
    @import <standardly-native.funcs()>
    @import <standardly-native.typings.str()>
    @import <standardly-native.contents.undefined()>
    @import <standardly-native.definitions.multi-line()>
    fn print[msg: str]:
        ...undefined
    end
    """
})
bity.parse()
bity.interpret()