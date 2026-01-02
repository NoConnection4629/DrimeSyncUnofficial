import inspect
import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.abspath("src"))

try:
    from drimesyncunofficial.browsers import AndroidFileBrowser
    sig = inspect.signature(AndroidFileBrowser.__init__)
    print(f"Signature: {sig}")
    print(f"Params: {list(sig.parameters.keys())}")
    
    param = sig.parameters.get("initial_path")
    print(f"initial_path param: {param}")
    if param:
        print(f"Default: {param.default}")
except Exception as e:
    print(f"Error: {e}")
