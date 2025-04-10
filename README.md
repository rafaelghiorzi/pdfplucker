# pdfplucker

Uma ferramenta completa para extração e processamento de documentos PDF.

## Características

- Extração de texto, tabelas e imagens de documentos PDF
- Processamento em paralelo para alta performance
- Suporte para aceleração via CPU ou CUDA
- Interface de linha de comando simples e intuitiva
- Criação de estruturas de saída personalizáveis

## Instalação

```bash
pip install pdf-processor
Ou diretamente do repositório:
bashgit clone https://github.com/yourusername/pdf-processor.git
cd pdf-processor
pip install -e .
```

## Dependências
Este pacote requer as seguintes bibliotecas:

- docling
- PyMuPDF (fitz)
- PyPDF2
- Ainda preciso descobrir o resto das dependências

## Uso
### Linha de Comando
Processar todos os PDFs em um diretório:
```bash
pdf-processor /caminho/para/pdfs -o /caminho/de/saida -w 4
```
Processar um único arquivo PDF:
```bash
pdf-processor /caminho/para/arquivo.pdf --single-file
```
Usar aceleração CUDA:
```bash
pdf-processor /caminho/para/pdfs -d CUDA -w 4
```

## Opções
```bash
usage: pdf-processor [-h] [-o OUTPUT] [-i IMAGES] [-s] [-w WORKERS] [-t TIMEOUT]
                     [-d {CPU,CUDA,cuda,cpu}] [--single-file]
                     source

Extrator de PDFs - Processador de documentos PDF

positional arguments:
  source                Caminho para os arquivos PDF (diretório ou arquivo único)

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Diretório para salvar os resultados (default: ./resultados)
  -i IMAGES, --images IMAGES
                        Diretório para salvar as imagens extraídas (ignorado se
                        --separate-folders estiver ativado) (default: None)
  -s, --separate-folders
                        Criar pastas separadas para cada PDF processado (default: False)
  -w WORKERS, --workers WORKERS
                        Número de processos paralelos a serem usados (default: 4)
  -t TIMEOUT, --timeout TIMEOUT
                        Tempo limite em segundos para processamento de cada PDF (default: 900)
  -d {CPU, CUDA, AUTO}, --device {CPU, CUDA, AUTO}
                        Dispositivo para processamento (CPU, CUDA ou AUTO) (default: CPU)
  --single-file         
                        Processar apenas um arquivo em vez de usar paralelismo (default: False)
```

## Exemplo de uso
```bash
python cli.py --source //storage6/usuarios/CGDTI/IpeaDataLab/projetos/ted_mdic/BrasilMaisProdutivo/pastas_pdfs/TDs --output D:/Users/B19943781742/Desktop/teste --separate-folders --workers 6 --timeout 720 --device CPU --markdown-also
```


## Como Funciona
O PDF Processor extrai informações estruturadas de documentos PDF:

- Texto: Extrai o conteúdo textual, preservando a estrutura de seções e parágrafos
- Tabelas: Identifica e extrai tabelas, preservando sua estrutura em formato JSON
- Imagens: Extrai imagens contidas nos documentos PDF

Os resultados são salvos em formato JSON estruturado para facilitar o processamento posterior.
Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.