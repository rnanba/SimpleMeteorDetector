import os

VERSION = "0.2.0"

def version_string(file):
    return "SimpleMeteorDetector v" + VERSION + ": " + os.path.basename(file)
    
