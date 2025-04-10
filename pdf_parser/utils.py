# utils.py

# Módulos padrões
import time
from pathlib import Path
from datetime import timedelta

def ensure_path(path, is_file=False):
    """
    Garante que um caminho exista, criando diretórios se necessário.
    
    Args:
        path: Caminho a ser verificado/criado
        is_file: Se True, considera o caminho como um arquivo e cria o diretório pai
        
    Returns:
        Path: O caminho verificado/criado
    """
    if isinstance(path, str):
        path = Path(path)
    
    if is_file:
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
    else:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
    
    return path