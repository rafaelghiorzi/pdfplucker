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

def get_output_paths(pdf_path, base_output, images_dir=None, separate_folders=False):
    """
    Determina os caminhos de saída com base nas configurações.
    
    Args:
        pdf_path: Caminho do arquivo PDF
        base_output: Diretório base para resultados
        images_dir: Diretório para imagens (opcional)
        separate_folders: Se True, cria pastas separadas para cada PDF
        
    Returns:
        tuple: (caminho_json, caminho_imagens)
    """
    pdf_path = Path(pdf_path) if isinstance(pdf_path, str) else pdf_path
    base_output = Path(base_output) if isinstance(base_output, str) else base_output
    
    filename = pdf_path.name
    name_without_ext = pdf_path.stem
    
    if separate_folders:
        pdf_output_dir = base_output / name_without_ext
        json_path = pdf_output_dir / f"{name_without_ext}.json"
        images_path = pdf_output_dir / "images"
        ensure_path(pdf_output_dir)
        ensure_path(images_path)
    else:
        json_path = base_output / f"{name_without_ext}.json"
        if images_dir:
            images_path = Path(images_dir)
        else:
            images_path = base_output / "images"
        ensure_path(images_path)
        
    return json_path, images_path

def format_time(seconds):
    """
    Formata o tempo em segundos para uma representação legível.
    
    Args:
        seconds: Tempo em segundos
        
    Returns:
        str: Tempo formatado
    """
    td = timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if td.days > 0:
        return f"{td.days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    elif minutes > 0:
        return f"{minutes:02d}m {seconds:02d}s"
    else:
        return f"{seconds:02d}s"