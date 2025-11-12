import sys

def autorun(pm):
    argv = sys.argv
    if ":bare" in argv:
        pm.disable_needy()
    if "download" in argv:
        from . import download
        download.handle(pm.root_dir, argv[2:])
        sys.exit(0)
