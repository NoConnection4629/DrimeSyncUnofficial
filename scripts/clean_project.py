import os
import shutil
import re

# Utiliser __file__ pour détecter automatiquement le chemin du projet
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(ROOT_DIR, "src", "drimesyncunofficial")
TESTS_DIR = os.path.join(ROOT_DIR, "tests")

def clean_file(filepath):
    """
    Nettoie un fichier Python :
    - Supprime les commentaires de ligne complète (sauf encoding/shebang)
    - Supprime les commentaires inline
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if i < 2 and stripped.startswith("#") and ("coding" in line or "!" in line):
                new_lines.append(line)
                continue
            
            if stripped.startswith("#"):
                continue
            
            cleaned_line = line
            
            if "#" in line and not stripped.startswith("#"):
                in_string = False
                quote_char = None
                for idx, char in enumerate(line):
                    if char in ['"', "'"]:
                        if not in_string:
                            in_string = True
                            quote_char = char
                        elif char == quote_char and (idx == 0 or line[idx-1] != '\\'):
                            in_string = False
                            quote_char = None
                    elif char == "#" and not in_string:
                        cleaned_line = line[:idx].rstrip() + '\n'
                        break
            
            new_lines.append(cleaned_line)
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"Error cleaning {filepath}: {e}")
        return False

def move_test(filepath, filename):
    """Déplace un fichier de test vers le dossier tests/"""
    dst_path = os.path.join(TESTS_DIR, filename)
    if os.path.exists(dst_path):
        print(f"Warning: {filename} already exists in tests/. Skipping move.")
    else:
        shutil.move(filepath, dst_path)
        print(f"Moved {filename} to tests/")
        return 1
    return 0

def run_clean():
    """Exécute le nettoyage complet du projet"""
    print(f"Starting cleanup in: {ROOT_DIR}")
    print(f"Source directory: {SRC_DIR}")
    print(f"Tests directory: {TESTS_DIR}")
    
    count = 0
    for root, dirs, files in os.walk(SRC_DIR):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                if clean_file(filepath):
                    count += 1
                    print(f"  Cleaned: {os.path.relpath(filepath, ROOT_DIR)}")
    
    print(f"\nCleaned comments in {count} files in src.")

    tests_moved = 0
    for file in os.listdir(SRC_DIR):
        if file.startswith("test_") and file.endswith(".py"):
             tests_moved += move_test(os.path.join(SRC_DIR, file), file)

    for file in os.listdir(ROOT_DIR):
        if (file.startswith("test_") or file.startswith("check_") or file.startswith("reproduce_")) and file.endswith(".py"):
             tests_moved += move_test(os.path.join(ROOT_DIR, file), file)
    
    print(f"\nMoved {tests_moved} test files to tests/ directory.")
    print("\n✅ Cleanup complete!")

if __name__ == "__main__":
    run_clean()
