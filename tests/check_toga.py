import toga
try:
    print(f"toga.Switch exists: {toga.Switch}")
except AttributeError:
    print("toga.Switch does NOT exist")