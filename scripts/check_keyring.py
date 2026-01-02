import keyring
import sys
try:
    kr = keyring.get_keyring()
    print(f"Current Backend: {kr}")
    print(f"Name: {kr.name}")
    print(f"Priority: {kr.priority}")
except Exception as e:
    print(f"Error: {e}")
