import os
import fitz  # PyMuPDF
import streamlit as st
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_openai import ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain  # Correct import
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import torch
import tempfile

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
        torch.set_num_threads(1)

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

        # Create vectorstore
        vectorstore = QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=embeddings
        )
        st.success(f"✅ Vectorstore created in Qdrant collection '{collection_name}'")
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

        # Create a prompt template for the QA chain
        prompt = ChatPromptTemplate.from_template(
            "Answer the following question based on the provided context:\n\n"
            "Context: {context}\n\n"
            "Question: {question}\n\n"
            "Answer:"
        )

        # Create a stuff documents chain
        chain = create_stuff_documents_chain(llm, prompt)

        # Invoke the chain
        response = chain.invoke({
            "context": docs,
            "question": query
        })

        return response
    except Exception as e:
        raise RuntimeError(f"Failed to query vectorstore: {e}")

# Streamlit app
st.title("PDF Question Answering with Qdrant and OpenRouter")
st.write("Upload a PDF file and ask a question to get answers based on its content.")

# File uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# Query input
query = st.text_input("Enter your question:", "What is the main topic of the PDF?")

# Collection name and Qdrant URL
collection_name = st.text_input("Qdrant collection name:", "pdf_knowledge_base")
qdrant_url = "http://localhost:6333"

# Process button
if st.button("Process PDF and Get Answer"):
    if uploaded_file is None:
        st.error("Please upload a PDF file.")
    elif not query.strip():
        st.error("Please enter a question.")
    else:
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.read())
                pdf_path = tmp_file.name

            # Extract text
            with st.spinner("Extracting text from PDF..."):
                text = extract_text(pdf_path)

            # Create vectorstore
            with st.spinner("Creating Qdrant vectorstore..."):
                client, vectorstore = create_vectorstore(text, collection_name, qdrant_url)

            # Query the vectorstore
            with st.spinner("Querying the vectorstore..."):
                api_key = "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"
                response = query_vectorstore(vectorstore, query, api_key)

            # Display answer
            st.subheader("Answer:")
            st.write(response)

            # Clean up temporary file
            os.unlink(pdf_path)
        except Exception as e:
            st.error(f"Error: {e}")