


#import pymupdf # 


from langchain_core.documents import Document
import fitz

def load_pdf(files="data/2306.02707.pdf"):
    """
    Loads documents from PDF files using PyMuPDF.

    Parameters:
    - files: A string representing a single file path or a list of strings representing multiple file paths.

    Returns:
    - A list of Document objects loaded from the provided PDF files.

    Raises:
    - FileNotFoundError: If any of the provided file paths do not exist.
    - Exception: For any other issues encountered during file loading.

    The function applies post-processing steps such as cleaning extra whitespace and grouping broken paragraphs.
    """
    if not isinstance(files, list):
        files = [files]  # Ensure 'files' is always a list
    
    # list of text
    documents = []
    for file_path in files:
        try:
            # Open the PDF file
            doc = fitz.open(file_path)
            text = ""
            # Extract text from each page
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # one line of code, get_text("text")
                # docling, pdfplumber are alternatives
                # there are more
                text += page.get_text("text")

            # Apply post-processing steps
            # is this used?
            text = clean_extra_whitespace(text)
            text = group_broken_paragraphs(text)

            # Create a Document object
            # this is never used. it returns a list under documents. 
            document = Document(
                page_content=text,
                metadata={"source": file_path}
            )
            documents.append(document)
        except FileNotFoundError as e:
            print(f"File not found: {e.filename}")
            raise
        except Exception as e:
            print(f"An error occurred while loading {file_path}: {e}")
            raise

    return documents

def clean_extra_whitespace(text):
    """
    Cleans extra whitespace from the provided text.

    Parameters:
    - text: A string representing the text to be cleaned.

    Returns:
    - A string with extra whitespace removed.
    """
    return ' '.join(text.split())

def group_broken_paragraphs(text):
    """
    Groups broken paragraphs in the provided text.

    Parameters:
    - text: A string representing the text to be processed.

    Returns:
    - A string with broken paragraphs grouped.
    """
    return text.replace("\n", " ").replace("\r", " ")

import os

directory = "./data"
# Get all files in the directory
files = os.listdir(directory)
# Filter out only PDF files
pdf_files = [f"{directory}/{file}" for file in files if file.endswith('.pdf')]
print(pdf_files)

# this is the pdf
documents = load_pdf(files=pdf_files)
print(len(documents))


EMBEDDING_MODEL_NAME = 'BAAI/bge-small-en-v1.5'
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_documents(
    chunk_size: int,
    knowledge_base,
    tokenizer_name= EMBEDDING_MODEL_NAME,
):
    """
    Splits documents into chunks of maximum size `chunk_size` tokens, using a specified tokenizer.

    Parameters:
    - chunk_size: The maximum number of tokens for each chunk.
    - knowledge_base: A list of LangchainDocument objects to be split.
    - tokenizer_name: (Optional) The name of the tokenizer to use. Defaults to `EMBEDDING_MODEL_NAME`.

    Returns:
    - A list of LangchainDocument objects, each representing a chunk. Duplicates are removed based on `page_content`.

    Raises:
    - ImportError: If necessary modules for tokenization are not available.
    """
    # this si different than the RCTS which is graphed
    #
    text_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        AutoTokenizer.from_pretrained(tokenizer_name),
        chunk_size=chunk_size,
        chunk_overlap=int(chunk_size / 10),
        add_start_index=True,
        strip_whitespace=True,
    )

    docs_processed = (text_splitter.split_documents([doc]) for doc in knowledge_base)
    # Flatten list and remove duplicates more efficiently
    unique_texts = set()
    docs_processed_unique = []
    # these are langchain docs
    for doc_chunk in docs_processed:
        for doc in doc_chunk:
            if doc.page_content not in unique_texts:
                unique_texts.add(doc.page_content)
                docs_processed_unique.append(doc)

    return docs_processed_unique