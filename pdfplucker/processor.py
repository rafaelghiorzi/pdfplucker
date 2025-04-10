# Módulos padrões
import os
import json
from pathlib import Path
import fitz
import multiprocessing
import gc
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
import time

# Imports do Docling
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import (
    ImageRefMode,
    PictureItem,
    TableItem,
    TextItem,
    DocItemLabel,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult

# Função principal para extração das informações
def processar_documento(conv: ConversionResult, dados: dict, nome_arquivo, caminho_imagens):
    """
    Processa um documento convertido extraindo texto, tabelas e imagens.
    
    Args:
        conv: Resultado da conversão do documento
        dados: Dicionário para armazenar os dados extraídos
        nome_arquivo: Nome do arquivo processado
        caminho_imagens: Caminho onde as imagens serão salvas
    """
    collecting = None
    contador = 0
    for item, _level, in conv.document.iterate_items():
        if isinstance(item, TextItem):
            if item.label == DocItemLabel.SECTION_HEADER:
                if collecting is not None:
                    dados['secoes'].append(collecting)
                collecting = {'titulo': item.text, 'texto': ''}
            elif item.label in [DocItemLabel.TEXT, DocItemLabel.LIST_ITEM, DocItemLabel.CHECKBOX_SELECTED, DocItemLabel.CHECKBOX_UNSELECTED]:
                if collecting is not None:
                    collecting['texto'] += '\n' + item.text if collecting['texto'] else item.text
        elif isinstance(item, TableItem):
            table = item.export_to_dataframe()
            dados['tabelas'].append({
                "self_ref" : item.self_ref,
                "legenda" : "",
                "tabela": table.to_dict()
                })
        elif isinstance(item, PictureItem):
            image_filename = (caminho_imagens / f"{nome_arquivo}_{contador}.png")
            contador += 1
            with image_filename.open('wb') as f:
                item.get_image(conv.document).save(f, "PNG")
            dados['imagens'].append({
                'ref': f"{nome_arquivo}_{contador}.png",
                'self_ref' : item.self_ref,
                'legenda' : ""
            })

    if collecting is not None:
        dados['secoes'].append(collecting)
    for text in conv.document.texts:
        if text.label == 'caption':
            dados['legendas'].append({
                'ref': text.parent.cref,
                'texto' : text.text,
            })

# Função para associar as legendas (ou títulos) presentes nos documentos
def associar_legendas(dados: dict):
    """
    Associa legendas às imagens e tabelas.
    
    Args:
        dados: Dicionário contendo as imagens, tabelas e legendas
    """
    imagens = dados.get('imagens', [])
    tabelas = dados.get('tabelas', [])
    legendas = dados.get('legendas', [])

    # Itera sobre as imagens associando legendas
    for img in imagens:
        self_ref = img.get('self_ref')
        if self_ref is None:
            print(f"Imagem {img} não possui self_ref")
            continue
        
        # Para cada imagem, procura uma legenda com ref igual a self_ref
        for leg in legendas[:]:
            ref = leg.get('ref')
            if self_ref == ref:
                img['legenda'] = leg.get('texto', '')
                img.pop('item', None)
                # Remove a legenda associada para não processá-la novamente
                legendas.remove(leg)
                break 

    # Itera sobre as tabelas associando legendas
    for tab in tabelas:
        self_ref = tab.get('self_ref')
        if self_ref is None:
            print(f"Tabela {tab} não possui self_ref")
            continue

        # Para cada tabela, procura uma legenda com ref igual a self_ref
        for leg in legendas[:]:
            ref = leg.get('ref')
            if self_ref == ref:
                tab['legenda'] = leg.get('texto', '')
                # Remove a legenda associada para não processá-la novamente
                legendas.remove(leg)
                break

    print(f"legendas restantes: {len(legendas)}")
    for leg in legendas:
        dados['imagens'].append({
            'ref': leg.get('ref'),
            'self_ref' : None,
            'legenda' : leg.get('texto', '')
        })

    dados.pop('legendas')
    
    del legendas, tabelas, imagens

# Função para criar o conversor Docling com base nos requerimentos do usuário
def create_converter(device='CPU', num_threads=4, ocr_lang=['es']):
    """
    Cria e configura o conversor de documentos.
    
    Args:
        device: Dispositivo para aceleração ('CPU' ou 'CUDA')
        num_threads: Número de threads a serem utilizadas
        ocr_lang: Lista de idiomas para OCR
        
    Returns:
        DocumentConverter configurado
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.ocr_options.lang = ocr_lang
    
    device_type = AcceleratorDevice.CUDA if device.upper() == 'CUDA' else AcceleratorDevice.CPU if device.upper() == 'CPU' else AcceleratorDevice.AUTO if device.upper() == 'AUTO' else AcceleratorDevice.AUTO
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=num_threads, device=device_type)
    
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_table_images = True
    pipeline_options.images_scale = 2.0

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

# Função de pipeline para processar um único PDF
def process_pdf(caminho_completo, caminho_resultado, caminho_imagens, doc_converter, separate_folders=False, markdown_also=False):
    """
    Processa um único arquivo PDF extraindo seu conteúdo.
    
    Args:
        caminho_completo: Caminho completo para o arquivo PDF
        caminho_resultado: Diretório onde salvar o JSON resultante
        caminho_imagens: Diretório onde salvar as imagens extraídas
        doc_converter: Conversor de documentos configurado
        separate_folders: Se True, cria pastas separadas para cada PDF
        
    Returns:
        True se o processamento foi bem-sucedido, False caso contrário
    """
    try:
        arquivo = os.path.basename(caminho_completo)
        nome_base = os.path.splitext(arquivo)[0]
        
        # Configuração de caminhos com base no parâmetro separate_folders
        if separate_folders:
            pasta_especifica = os.path.join(caminho_resultado, nome_base)
            resultado = os.path.join(pasta_especifica, f"{nome_base}.json")
            pasta_imagens = os.path.join(pasta_especifica, "images")
            os.makedirs(pasta_especifica, exist_ok=True)
            os.makedirs(pasta_imagens, exist_ok=True)
        else:
            resultado = os.path.join(caminho_resultado, f"{nome_base}.json")
            pasta_imagens = caminho_imagens
            
        # Cria o Path para o caminho das imagens
        pasta_imagens_path = Path(pasta_imagens)
        
        print(f"📄 Processando: {arquivo}")
        
        dados = {
            "metadados": {},
            "secoes": [],
            "imagens": [],
            "tabelas": [],
            "legendas": [],
        }

        doc = fitz.open(caminho_completo)
        dados['metadados'] = doc.metadata
        dados['metadados']['filename'] = arquivo
        doc.close()

        conv = doc_converter.convert(caminho_completo)
        processar_documento(conv, dados, nome_base, pasta_imagens_path)
        associar_legendas(dados)
        if markdown_also:
                # Save markdown with embedded pictures
                md_filename = resultado.replace('.json', '.md')
                conv.document.save_as_markdown(md_filename, image_mode=ImageRefMode.EMBEDDED)


        # Salvar o json do resultado
        with open(resultado, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)

        print(f"✅ {arquivo} processado com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao processar {arquivo}: {e}")
        return False
    
    finally:
        # Liberar memória
        try:
            del conv, dados, doc
            gc.collect()
        except:
            pass

# Função para paralelizar o processamento
def run_pipeline(caminho_completo, caminho_resultado, caminho_imagens, doc_converter, separate_folders, queue, markdown_also=False):
    """
    Função para executar o pipeline em um processo separado.
    
    Args:
        caminho_completo: Caminho para o arquivo PDF
        caminho_resultado: Diretório para salvar resultados
        caminho_imagens: Diretório para salvar imagens
        doc_converter: Conversor de documentos configurado
        separate_folders: Se True, cria pastas separadas para cada PDF
        queue: Fila para comunicação entre processos
    """
    try:
        success = process_pdf(caminho_completo, caminho_resultado, caminho_imagens, doc_converter, separate_folders, markdown_also)
        queue.put(success)
    except Exception as e:
        print(f"❌ Erro não tratado: {e}")
        queue.put(False)        

# Função auxiliar do paralelismo com timeout
def run_safe_pipeline(caminho_completo, caminho_resultado, caminho_imagens, doc_converter, separate_folders, timeout, markdown_also=False):
    """
    Executa o processamento com timeout seguro.
    
    Args:
        caminho_completo: Caminho para o arquivo PDF
        caminho_resultado: Diretório para salvar resultados
        caminho_imagens: Diretório para salvar imagens
        doc_converter: Conversor de documentos configurado
        separate_folders: Se True, cria pastas separadas para cada PDF
        timeout: Tempo limite em segundos
        
    Returns:
        True se o processamento foi bem-sucedido, False caso contrário
    """
    queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=run_pipeline, 
        args=(caminho_completo, caminho_resultado, caminho_imagens, doc_converter, separate_folders, queue, markdown_also)
    )

    process.start()
    process.join(timeout)

    if process.is_alive():
        print(f"⏳ Timeout reached! Terminating {caminho_completo}")
        process.terminate()
        process.join()
        return False

    return queue.get() if not queue.empty() else False

# Função para processar um lote de PDFs em paralelo	
def process_batch(
    source_path, 
    output_path, 
    images_path=None, 
    separate_folders=False, 
    max_workers=6, 
    timeout=900, 
    device='CPU',
    markdown_also=False
):
    """
    Processa um lote de PDFs em paralelo.
    
    Args:
        source_path: Caminho para os arquivos PDF
        output_path: Caminho para salvar os resultados
        images_path: Caminho para salvar as imagens (ignorado se separate_folders=True)
        separate_folders: Se True, cria pastas separadas para cada PDF
        max_workers: Número máximo de workers em paralelo
        timeout: Tempo limite em segundos para processar cada PDF
        device: Dispositivo para processamento ('CPU' ou 'CUDA')
        
    Returns:
        Dicionário com métricas do processamento
    """
    source_path = Path(source_path)
    output_path = Path(output_path)
    
    # Configuração de caminhos
    if not separate_folders and images_path is None:
        images_path = output_path / "images"
    elif images_path is not None:
        images_path = Path(images_path)
    
    # Criar diretórios se não existirem
    os.makedirs(output_path, exist_ok=True)
    if not separate_folders:
        os.makedirs(images_path, exist_ok=True)
    
    # Criar o conversor de documentos
    doc_converter = create_converter(device=device, num_threads=max_workers)

    # Listar arquivos PDF
    arquivos = []
    if source_path.is_dir():
        for arquivo in os.listdir(source_path):
            if arquivo.lower().endswith('.pdf'):
                arquivos.append(os.path.join(source_path, arquivo))
    else:
        # Se source_path for um único arquivo
        if source_path.suffix.lower() == '.pdf':
            arquivos.append(str(source_path))
    
    total_documentos = len(arquivos)
    print(f"Total de documentos a serem processados: {total_documentos}")

    # Inicializar métricas
    metricas = {
        'Horário inicial': time.time(),
        'Tempo de execução (s)': 0,
        'Total de documentos': total_documentos,
        'Documentos processados': 0,
        'Documentos com erro': 0,
        'Documentos com timeout': 0,
        'Taxa de falha': 0,
        'Falhas': []
    }

    # Processamento em paralelo
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_safe_pipeline, 
                arquivo, 
                str(output_path), 
                str(images_path) if not separate_folders else None, 
                doc_converter, 
                separate_folders,
                timeout,
                markdown_also
            ): arquivo
            for arquivo in arquivos
        }

        for future in as_completed(futures):
            caminho_pdf = futures[future]
            try:
                resultado = future.result()
                if resultado:
                    metricas["Documentos processados"] += 1
                    print(f"✅ {caminho_pdf} processado com sucesso!")
                    print(f"🔵 Quantidade de documentos processados: {metricas['Documentos processados']}")
                else:
                    print(f"❌ Falha ao processar {caminho_pdf}")
                    metricas["Documentos com erro"] += 1
                    metricas["Falhas"].append({
                        "arquivo": caminho_pdf,
                        "erro": "Erro não especificado"
                    })
            except TimeoutError:
                print(f"❌ Timeout ao processar {caminho_pdf}")
                metricas["Documentos com timeout"] += 1
                metricas["Falhas"].append({
                    "arquivo": caminho_pdf,
                    "erro": "Timeout"
                })
            except Exception as e:
                print(f"❌ Erro ao processar {caminho_pdf}: {e}")
                metricas["Documentos com erro"] += 1
                metricas["Falhas"].append({
                    "arquivo": caminho_pdf,
                    "erro": str(e)
                })

    # Finalizar métricas
    tempo_total = time.time() - metricas['Horário inicial']
    metricas['Tempo de execução'] = tempo_total
    metricas['Taxa de falha'] = (metricas['Documentos com erro'] + metricas['Documentos com timeout']) / total_documentos

    # Gravar log de métricas
    source_name = os.path.basename(source_path)
    log_path = os.path.join(output_path, f"{source_name}_log.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(metricas, f, ensure_ascii=False, indent=4)

    print(f"🔵 Processo finalizado!")
    return metricas