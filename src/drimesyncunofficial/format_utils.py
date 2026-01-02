
from typing import Optional, Union
from datetime import datetime

def truncate_path_smart(name: str, max_length: int = 35) -> str:
    """
    Tronque intelligemment un nom de fichier pour l'affichage (ex: 'abcdef...1234.pdf').
    Garde l'extension et le début du nom.
    """
    if len(name) <= max_length:
        return name
    
    part_len = (max_length - 3) // 2
    return f"{name[:part_len]}...{name[-part_len:]}"

def format_size(size_bytes: Union[int, float, None]) -> str:
    """Convertit une taille en octets en une chaîne lisible (Ko, Mo, Go, To)."""
    try: val = float(size_bytes or 0)
    except: val = 0.0
    
    if val == 0: return "0 o"
    
    units = ["o", "Ko", "Mo", "Go", "To", "Po"]
    i = 0
    while val >= 1024 and i < len(units) - 1:
        val /= 1024.0
        i += 1
        
    if i == 0: return f"{int(val)} {units[i]}"
    return f"{val:.2f} {units[i]}"

def format_display_date(ts_or_str: Union[int, float, str, None]) -> str:
    """Formate un timestamp ou une string ISO en date lisible."""
    if not ts_or_str: return "-"
    try:
        dt = None
        if isinstance(ts_or_str, (int, float)):
            dt = datetime.fromtimestamp(ts_or_str)
        elif isinstance(ts_or_str, str):
            s = ts_or_str.replace('Z', '+00:00')
            dt = datetime.fromisoformat(s)
            
        if dt:
            return dt.strftime("%d/%m/%Y %H:%M")
        return str(ts_or_str)
    except:
        return str(ts_or_str)

def sanitize_filename_for_upload(name: str) -> str:
    """
    Renomme le fichier "0" en "0.renamed" pour contourner un bug de l'API Drime.
    L'API ou le système de fichiers peut mal l'interpréter, donc on le renomme "0.renamed".
    """
    return "0.renamed" if name == "0" else name

def restore_filename_from_download(name: str) -> str:
    """
    Restaure le nom original "0" si le fichier s'appelle "0.renamed".
    Inverse de sanitize_filename_for_upload.
    """
    return "0" if name == "0.renamed" else name
