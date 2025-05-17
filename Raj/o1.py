import os
import fitz  # PyMuPDF
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import Qdrant as QdrantVectorStore  # Updated import
from langchain_community.chat_models import ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.chains.question_answering import load_qa_chain
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import torch

def extract_text(pdf_path):
    """Extract and clean text from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = " ".join(" ".join(page.get_text().split()) for page in doc)
        doc.close()
        return text
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")

def create_vectorstore(text, collection_name, qdrant_url="http://localhost:6333"):
    """Create a Qdrant vectorstore from text with manual embedding."""
    try:
        # Split text into chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = [Document(page_content=chunk) for chunk in splitter.split_text(text)]

        # Disable parallelism to avoid threading issues
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        torch.set_num_threads(1)  # Limit PyTorch threads to 1

        # Initialize embeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"}
        )

        # Manually embed documents
        texts = [doc.page_content for doc in docs]
        vectors = embeddings.embed_documents(texts)

        # Connect to Qdrant
        client = QdrantClient(url=qdrant_url)

        # Create collection if it doesn't exist
        try:
            client.get_collection(collection_name)
        except:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE)
            )

        # Upload vectors to Qdrant with correct payload key
        points = [
            PointStruct(id=i, vector=vector, payload={"page_content": doc.page_content})
            for i, (vector, doc) in enumerate(zip(vectors, docs))
        ]
        client.upsert(collection_name=collection_name, points=points)

        # Create vectorstore with correct keyword
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embeddings=embeddings  # Changed from 'embedding' to 'embeddings'
        )
        print(f"✅ Vectorstore created in Qdrant collection '{collection_name}'")
        return client, vectorstore
    except Exception as e:
        raise RuntimeError(f"Failed to create vectorstore: {e}")

def query_vectorstore(vectorstore, query, api_key, model_name="mistralai/mistral-7b-instruct"):
    """Query the vectorstore and get an answer using a language model."""
    try:
        # Retrieve relevant documents
        docs = vectorstore.similarity_search(query, k=3)

        # Debug: Check retrieved documents
        for i, doc in enumerate(docs):
            if not isinstance(doc.page_content, str):
                raise ValueError(f"Document {i} has invalid page_content: {doc.page_content}")

        # Configure OpenRouter API
        llm = ChatOpenAI(
            model_name=model_name,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            temperature=0.5
        )

        # Run QA chain
        chain = load_qa_chain(llm, chain_type="stuff")
        response = chain.run(input_documents=docs, question=query)
        return response
    except Exception as e:
        raise RuntimeError(f"Failed to query vectorstore: {e}")

def main(pdf_path, query, collection_name="pdf_knowledge_base", qdrant_url="http://localhost:6333"):
    """Main function to process PDF, build vectorstore, and query it."""
    try:
        # Define OpenRouter API key directly
        api_key = "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"

        # Verify PDF exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Extract text from PDF
        text = extract_text(pdf_path)

        # Create vectorstore
        client, vectorstore = create_vectorstore(text, collection_name, qdrant_url)

        # Query the vectorstore
        response = query_vectorstore(vectorstore, query, api_key)
        print("🧠 Answer:", response)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Example usage
    pdf_path = r"C:\Users\DELL\Desktop\program\2402.01680v2.pdf"
    query = "What is the main topic of the PDF?"
    collection_name = "pdf_knowledge_base"

    main(pdf_path, query, collection_name)