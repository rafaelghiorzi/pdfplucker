import sys
import argparse
from pathlib import Path
import time
import json

from processor import process_batch, create_converter, process_pdf
from utils import ensure_path

def create_parser():
    """
    Cria o parser de argumentos de linha de comando.
    
    Returns:
        ArgumentParser: Parser configurado
    """
    parser = argparse.ArgumentParser(
        description='Extrator de PDFs - Processador de documentos PDF',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Argumentos obrigatórios
    parser.add_argument(
        '-f', '--source',
        help='Caminho para os arquivos PDF (diretório ou arquivo único)'
    )
    
    # Argumentos opcionais
    parser.add_argument(
        '-o', '--output',
        help='Diretório para salvar os resultados',
        default='./resultados'
    )
    
    parser.add_argument(
        '-i', '--images',
        help='Diretório para salvar as imagens extraídas (ignorado se --separate-folders estiver ativado)'
    )
    
    parser.add_argument(
        '-s', '--separate-folders',
        action='store_true',
        help='Criar pastas separadas para cada PDF processado'
    )
    
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        help='Número de processos paralelos a serem usados'
    )
    
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=900,  # 15 minutos
        help='Tempo limite em segundos para processamento de cada PDF'
    )
    
    parser.add_argument(
        '-d', '--device',
        choices=['CPU', 'CUDA', 'AUTO'],
        default='CPU',
        help='Dispositivo para processamento (CPU, CUDA ou AUTO)'
    )
    
    parser.add_argument(
        '--single-file',
        action='store_true',
        help='Processar apenas um arquivo em vez de usar paralelismo'
    )

    parser.add_argument(
        '--markdown-also',
        action='store_true',
        help='Exportar documento também em formato Markdown'
    )
    
    return parser

def validate_args(args):
    """
    Valida os argumentos fornecidos.
    
    Args:
        args: Argumentos do parser
        
    Returns:
        tuple: (válido, mensagem de erro)
    """
    # Verifica o caminho de origem
    source_path = Path(args.source)
    if not source_path.exists():
        return False, f"Caminho de origem não encontrado: {args.source}"
    
    # Se for um diretório, verifica se contém PDFs
    if source_path.is_dir():
        pdf_files = list(source_path.glob("*.pdf"))
        if not pdf_files:
            return False, f"Nenhum arquivo PDF encontrado em: {args.source}"
    # Se for um arquivo, verifica se é um PDF
    elif not source_path.name.lower().endswith('.pdf'):
        return False, f"O arquivo de origem não é um PDF: {args.source}"
    
    # Verifica número de workers
    if args.workers < 1:
        return False, "O número de workers deve ser pelo menos 1"
    
    # Verifica timeout
    if args.timeout < 1:
        return False, "O timeout deve ser pelo menos 1 segundo"
    
    return True, ""

def process_single_file(args):
    """
    Processa um único arquivo PDF sem paralelismo.
    
    Args:
        args: Argumentos da linha de comando
        
    Returns:
        bool: True se o processamento foi bem-sucedido
    """
    source_path = Path(args.source)
    output_path = Path(args.output)
    
    # Configurar diretório de imagens
    if args.separate_folders:
        images_path = output_path / source_path.stem / "images"
    elif args.images:
        images_path = Path(args.images)
    else:
        images_path = output_path / "images"
    
    # Criar diretórios necessários
    ensure_path(output_path)
    ensure_path(images_path)
    
    print(f"Processando arquivo único: {source_path}")
    print(f"Resultados serão salvos em: {output_path}")
    print(f"Imagens serão salvas em: {images_path}")
    
    # Criar conversor
    doc_converter = create_converter(
        device=args.device.upper(),
        num_threads=args.workers
    )
    
    start_time = time.time()
    success = process_pdf(
        str(source_path),
        str(output_path),
        str(images_path),
        doc_converter,
        args.separate_folders,
        args.markdown_also,
    )
    
    elapsed_time = time.time() - start_time
    print(f"Tempo de processamento: {elapsed_time:.2f} segundos")
    
    if success:
        print(f"✅ Arquivo processado com sucesso!")
    else:
        print(f"❌ Falha ao processar o arquivo")
    
    return success

def main():
    """Função principal do CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Valida argumentos
    valid_args, error_msg = validate_args(args)
    if not valid_args:
        print(f"Erro: {error_msg}")
        sys.exit(1)
    
    print("=" * 50)
    print("🔵 Extrator de PDFs - Iniciando processamento")
    print("=" * 50)
    print(f"Fonte: {args.source}")
    print(f"Destino: {args.output}")
    print(f"Device: {args.device.upper()}")
    print(f"Workers: {args.workers}")
    print(f"Timeout: {args.timeout} segundos")
    print(f"Pastas separadas: {'Sim' if args.separate_folders else 'Não'}")
    print(f"Salvar markdown: {'Sim' if args.markdown_also else 'Não'}")
    print("=" * 50)
    
    try:
        # Decide entre processamento único ou em lote
        if args.single_file or Path(args.source).is_file():
            success = process_single_file(args)
            sys.exit(0 if success else 1)
        else:
            # Processamento em lote
            metrics = process_batch(
                source_path=args.source,
                output_path=args.output,
                images_path=args.images,
                separate_folders=args.separate_folders,
                max_workers=args.workers,
                timeout=args.timeout,
                device=args.device.upper(),
                markdown_also=args.markdown_also,
            )
            
            # Exibe resumo
            print("\n" + "=" * 50)
            print("🔵 Resumo do processamento:")
            print(f"Total de documentos: {metrics['Total de documentos']}")
            print(f"Processados com sucesso: {metrics['Documentos processados']}")
            print(f"Falhas: {metrics['Documentos com erro'] + metrics['Documentos com timeout']}")
            print(f"Taxa de sucesso: {(metrics['Documentos processados'] / metrics['Total de documentos']) * 100:.2f}%")
            print(f"Tempo total: {metrics['Tempo de execução']:.2f} segundos")

            # Salva métricas em arquivo JSON
            output_path = Path(args.output)
            ensure_path(output_path)

            source_name = Path(args.source).name
            filename = f"{source_name}_metrics.json"
            metrics_path = output_path / filename
            
            with open(metrics_path, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, ensure_ascii=False, indent=4)
            print(f"Métricas salvas em: {metrics_path}")
            print("=" * 50)
            
    except KeyboardInterrupt:
        print("\n Processo interrompido pelo usuário")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Erro não tratado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()