import os
from queue import Queue
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import Qdrant as QdrantVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
import torch

class PDFQueueProcessor:
    """
    A class to process PDFs from a folder, extract text into a queue, and store chunks with metadata
    in a Qdrant vector database using LangChain.
    """

    def __init__(
        self,
        folder_path: str,
        qdrant_url: str = "http://localhost:6333/",
        collection_name: str = "SYLLABUS",
        api_key: Optional[str] = None
    ):
        """
        Initialize the processor with folder path, Qdrant configuration, and optional API key.

        Args:
            folder_path (str): Path to the folder containing PDFs.
            qdrant_url (str): URL of the local Qdrant instance.
            collection_name (str): Name of the Qdrant collection.
            api_key (str, optional): OpenRouter API key, if needed for future querying.
        """
        self.folder_path = Path(folder_path)
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.api_key = api_key  # Stored for potential future use (e.g., querying)
        self.pdf_queue = Queue()  # Queue to hold PDF text or paths

        # Initialize LangChain components
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"}
        )
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

        # Optimize for single-threaded execution
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        torch.set_num_threads(1)

        # Set up Qdrant client and collection
        self.client = QdrantClient(url=self.qdrant_url)
        self._ensure_collection_exists()

        # Initialize QdrantVectorStore with LangChain
        self.vectorstore = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embeddings=self.embeddings,
            content_payload_key="page_content",
            metadata_payload_key="metadata"
        )

    def _ensure_collection_exists(self):
        """Ensure the Qdrant collection exists; create it if it doesn’t."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Determine vector size from embeddings
            dummy_vector = self.embeddings.embed_query("dummy")
            vector_size = len(dummy_vector)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            print(f"Created collection '{self.collection_name}' with vector size {vector_size}")

    def load_pdfs_to_queue(self):
        """
        Load PDF paths from the folder into the queue and extract text.
        Simulates your existing queue with extracted text.
        """
        if not self.folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")

        for pdf_file in self.folder_path.glob("*.pdf"):
            try:
                text = self._extract_text(pdf_file)
                self.pdf_queue.put((pdf_file.name, text))
            except Exception as e:
                print(f"Failed to extract text from {pdf_file}: {e}")
        print(f"Loaded {self.pdf_queue.qsize()} PDFs into the queue.")

    def _extract_text(self, pdf_path: Path) -> str:
        """Extract text from a PDF file."""
        doc = fitz.open(pdf_path)
        text = " ".join(" ".join(page.get_text().split()) for page in doc)
        doc.close()
        return text

    def process_queue(self):
        """Process each item in the queue: chunk text, add metadata, and store in Qdrant."""
        while not self.pdf_queue.empty():
            pdf_filename, text = self.pdf_queue.get()
            self._process_pdf_text(pdf_filename, text)
            self.pdf_queue.task_done()

    def _process_pdf_text(self, pdf_filename: str, text: str):
        """Process extracted text: split into chunks, create metadata, and store."""
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)
            if not chunks:
                print(f"No chunks generated for {pdf_filename}")
                return

            # Create metadata for each chunk
            metadatas = [
                {
                    "pdf_filename": pdf_filename,
                    "chunk_index": i,
                    # Additional metadata can be added here (e.g., timestamp, author)
                }
                for i in range(len(chunks))
            ]

            # Store in Qdrant using LangChain’s vector store
            self.vectorstore.add_texts(texts=chunks, metadatas=metadatas)
            print(f"Stored {len(chunks)} chunks from {pdf_filename}")

        except Exception as e:
            print(f"Failed to process text from {pdf_filename}: {e}")

# Example usage
if __name__ == "__main__":
    folder_path = r"C:\Users\DELL\Desktop\Raj\DATA"
    api_key = "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"  # Optional, included as per your code
    processor = PDFQueueProcessor(folder_path, api_key=api_key)
    processor.load_pdfs_to_queue()
    processor.process_queue()