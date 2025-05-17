import os
import time
import threading
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
import fitz  # PyMuPDF
import torch
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import Qdrant as QdrantVectorStore
from langchain_openai import ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain.chains import RetrievalQA
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from langgraph.graph import StateGraph, END
from typing import TypedDict
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PDFToQdrantSystem")

@dataclass
class PDFDocument:
    file_path: str
    file_name: str
    content: str = ""
    chunks: List[str] = field(default_factory=list)
    page_count: int = 0
    extraction_status: str = "pending"
    vectorization_status: str = "pending"
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    error_message: Optional[str] = None

class State(TypedDict):
    pdf_doc: PDFDocument
    collection_name: str

class PDFExtractorAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.documents_processed = 0
        self.logger = logging.getLogger(f"PDFExtractorAgent-{agent_id}")
        self.logger.info(f"Agent {agent_id} initialized")
    
    def extract_text_from_pdf(self, state: State) -> State:
        pdf_doc = state["pdf_doc"]
        self.logger.info(f"Processing file: {pdf_doc.file_name}")
        pdf_doc.extraction_status = "processing"
        
        start_time = time.time()
        try:
            doc = fitz.open(pdf_doc.file_path)
            pdf_doc.page_count = len(doc)
            full_text = [page.get_text() for page in doc]
            pdf_doc.content = "\n".join(full_text)
            
            pdf_doc.metadata.update({
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "file_path": pdf_doc.file_path,
                "file_name": pdf_doc.file_name,
                "page_count": pdf_doc.page_count,
                "processed_by": self.agent_id,
                "exam": "CUET"
            })
            self._infer_tags_from_filename(pdf_doc)
            doc.close()
            pdf_doc.extraction_status = "completed"
            self.documents_processed += 1
        except Exception as e:
            pdf_doc.extraction_status = "failed"
            pdf_doc.error_message = f"Extraction error: {str(e)}"
            self.logger.error(f"Error processing {pdf_doc.file_name}: {str(e)}")
        
        pdf_doc.processing_time = time.time() - start_time
        self.logger.info(f"Completed processing {pdf_doc.file_name} in {pdf_doc.processing_time:.2f} seconds")
        return {"pdf_doc": pdf_doc, "collection_name": state["collection_name"]}

    def _infer_tags_from_filename(self, pdf_doc: PDFDocument):
        filename = pdf_doc.file_name.lower()
        
        # Enhanced subject detection for CUET exam
        subjects = {
            "physics": ["physics", "phy"],
            "chemistry": ["chemistry", "chem"],
            "mathematics": ["mathematics", "math", "maths"],
            "biology": ["biology", "bio"],
            "english": ["english", "eng"],
            "general_test": ["general", "gen", "gt"],
            "computer_science": ["computer", "cs", "programming"],
            "economics": ["economics", "eco"],
            "history": ["history", "hist"],
            "geography": ["geography", "geo"],
            "political_science": ["political", "polsc"],
            "psychology": ["psychology", "psych"],
            "sociology": ["sociology", "socio"],
            "commerce": ["commerce", "comm", "business"],
            "accountancy": ["accountancy", "accounts", "acc"],
            "legal_studies": ["legal", "law"],
            "environmental_science": ["environmental", "env", "evs"]
        }
        
        # Enhanced document type detection
        doc_types = {
            "syllabus": ["syllabus", "syll", "curriculum", "course"],
            "pyq": ["pyq", "previous", "question", "paper", "exam"],
            "notes": ["notes", "study", "material"],
            "reference": ["reference", "ref", "book"],
            "guide": ["guide", "handbook", "manual"]
        }
        
        # Years for CUET exam (including future years)
        years = [str(year) for year in range(2000, 2026)]
        
        # Detect subject
        subject = "unknown"
        for subj, keywords in subjects.items():
            if any(keyword in filename for keyword in keywords):
                subject = subj
                break
        
        # Detect document type
        doc_type = "unknown"
        for dtype, keywords in doc_types.items():
            if any(keyword in filename for keyword in keywords):
                doc_type = dtype
                break
        
        # Detect year
        year = next((y for y in years if y in filename), "unknown")
        
        # Detect section/domain (domain A, B, C in CUET)
        section_match = next((s for s in ["section a", "section b", "section c", "domain a", "domain b", "domain c"] if s in filename), None)
        section = section_match.split()[-1].upper() if section_match else "unknown"
        
        # Update metadata with enhanced tags
        pdf_doc.metadata.update({
            "subject": subject,
            "doc_type": doc_type,
            "year": year,
            "section": section,
            "exam": "CUET",
            "education_level": "undergraduate",
            "searchable_tags": [subject, doc_type, year, section, "CUET", "undergraduate"]
        })

class ChunkingAgent:
    def __init__(self, agent_id: str, chunk_size: int = 500, chunk_overlap: int = 50):
        self.agent_id = agent_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Default text splitter for general content
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap
        )
        
        # Specialized text splitter for syllabus content with section-aware chunking
        self.syllabus_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap * 2,  # Higher overlap for syllabus content
            separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""],
        )
        
        self.documents_chunked = 0
        self.logger = logging.getLogger(f"ChunkingAgent-{agent_id}")
        self.logger.info(f"Chunking Agent {agent_id} initialized")
    
    def chunk_document(self, state: State) -> State:
        pdf_doc = state["pdf_doc"]
        self.logger.info(f"Chunking content of: {pdf_doc.file_name}")
        
        if pdf_doc.extraction_status != "completed":
            self.logger.warning(f"Cannot chunk {pdf_doc.file_name} - extraction status: {pdf_doc.extraction_status}")
            pdf_doc.error_message = f"Cannot chunk: extraction status {pdf_doc.extraction_status}"
            return {"pdf_doc": pdf_doc, "collection_name": state["collection_name"]}
        
        try:
            # Determine document type to select appropriate chunking strategy
            doc_type = pdf_doc.metadata.get("doc_type", "unknown").lower()
            
            # Use specialized chunking for syllabus documents
            if doc_type == "syllabus":
                self.logger.info(f"Using syllabus-optimized chunking for {pdf_doc.file_name}")
                pdf_doc.chunks = self.syllabus_splitter.split_text(pdf_doc.content)
                chunking_method = "syllabus_optimized"
            else:
                # Use standard chunking for other document types
                pdf_doc.chunks = self.text_splitter.split_text(pdf_doc.content)
                chunking_method = "standard"
            
            # Add semantic headers to chunks when possible
            self._add_semantic_headers(pdf_doc)
            
            # Update metadata with chunking information
            pdf_doc.metadata["chunking"] = {
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "num_chunks": len(pdf_doc.chunks),
                "chunking_agent": self.agent_id,
                "chunking_method": chunking_method,
                "timestamp": time.time()
            }
            
            self.documents_chunked += 1
            self.logger.info(f"Created {len(pdf_doc.chunks)} chunks for {pdf_doc.file_name} using {chunking_method} method")
        except Exception as e:
            pdf_doc.error_message = f"Chunking error: {str(e)}"
            self.logger.error(f"Error chunking {pdf_doc.file_name}: {str(e)}")
        
        return {"pdf_doc": pdf_doc, "collection_name": state["collection_name"]}
    
    def _add_semantic_headers(self, pdf_doc: PDFDocument):
        """
        Add semantic headers to chunks based on content analysis.
        This helps improve retrieval by adding context to each chunk.
        """
        subject = pdf_doc.metadata.get("subject", "unknown")
        doc_type = pdf_doc.metadata.get("doc_type", "unknown")
        
        # Process each chunk to identify and add semantic headers
        for i, chunk in enumerate(pdf_doc.chunks):
            # Look for section headers in the chunk
            lines = chunk.split("\n")
            potential_header = lines[0] if lines else ""
            
            # Check if the first line looks like a header (short, ends with colon, etc.)
            is_header = (len(potential_header) < 100 and 
                        (potential_header.endswith(":") or 
                         potential_header.isupper() or 
                         any(term in potential_header.lower() for term in ["unit", "section", "chapter", "topic", "module"])))
            
            if is_header:
                # Keep the header in the chunk but also add it to metadata
                pdf_doc.chunks[i] = chunk
                if i < len(pdf_doc.chunks):
                    # Create a new enhanced chunk with the header information
                    pdf_doc.chunks[i] = f"[{subject.upper()} {doc_type.upper()} - {potential_header}]\n\n{chunk}"


class VectorizationAgent:
    def __init__(self, agent_id: str, qdrant_url: str, collection_lock: threading.Lock):
        self.agent_id = agent_id
        self.qdrant_url = qdrant_url
        self.collection_lock = collection_lock
        self.documents_vectorized = 0
        self.max_points = 10000  # Threshold for creating new collection
        
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        torch.set_num_threads(1)
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"}
        )
        self.client = QdrantClient(url=qdrant_url)
        self.logger = logging.getLogger(f"VectorizationAgent-{agent_id}")
        self.logger.info(f"Vectorization Agent {agent_id} initialized")
    
    def vectorize_document(self, state: State) -> State:
        pdf_doc = state["pdf_doc"]
        base_collection_name = state["collection_name"]
        
        # Use subject as part of collection name for better organization
        subject = pdf_doc.metadata.get("subject", "unknown")
        doc_type = pdf_doc.metadata.get("doc_type", "unknown")
        
        # Create a more specific collection name for better organization
        if subject != "unknown" and doc_type != "unknown":
            collection_name = f"cuet_{subject}_{doc_type}"
        elif subject != "unknown":
            collection_name = f"cuet_{subject}"
        else:
            collection_name = base_collection_name
            
        self.logger.info(f"Vectorizing content of: {pdf_doc.file_name} to collection {collection_name}")
        pdf_doc.vectorization_status = "processing"
        
        if not pdf_doc.chunks:
            self.logger.warning(f"No chunks available for {pdf_doc.file_name}")
            pdf_doc.vectorization_status = "failed"
            pdf_doc.error_message = "No chunks available for vectorization"
            return {"pdf_doc": pdf_doc, "collection_name": collection_name}
        
        try:
            with self.collection_lock:
                final_collection_name = self._get_available_collection(collection_name)
                
                # Check if document already exists in collection
                existing_points = self.client.scroll(
                    collection_name=final_collection_name,
                    scroll_filter=Filter(
                        must=[FieldCondition(key="metadata.file_name", match=MatchValue(value=pdf_doc.file_name))]
                    ),
                    limit=1
                )[0]
                
                if existing_points:
                    self.logger.info(f"Skipping {pdf_doc.file_name}: already exists in {final_collection_name}")
                    pdf_doc.vectorization_status = "skipped"
                    pdf_doc.error_message = "Document already exists in collection"
                    return {"pdf_doc": pdf_doc, "collection_name": final_collection_name}
            
            # Prepare documents with enhanced metadata
            docs = []
            for i, chunk in enumerate(pdf_doc.chunks):
                # Create a copy of metadata to avoid modifying the original
                chunk_metadata = pdf_doc.metadata.copy()
                
                # Add chunk-specific metadata
                chunk_metadata.update({
                    "chunk_index": i,
                    "total_chunks": len(pdf_doc.chunks),
                    "vectorization_agent": self.agent_id,
                    "chunk_position": "start" if i == 0 else "end" if i == len(pdf_doc.chunks) - 1 else "middle",
                    "processing_timestamp": time.time()
                })
                
                # Create document with enhanced metadata
                docs.append(Document(page_content=chunk, metadata=chunk_metadata))
            
            # Extract text content for embedding
            texts = [doc.page_content for doc in docs]
            
            # Generate embeddings and create points
            with self.collection_lock:
                vectors = self.embeddings.embed_documents(texts)
                
                # Create a unique ID base using filename and subject
                base_id_str = f"{subject}_{pdf_doc.file_name.replace('.', '_')}"
                
                # Create points with enhanced payload structure
                points = [
                    PointStruct(
                        id=i + hash(base_id_str) % 10000000,
                        vector=vector,
                        payload={
                            "page_content": doc.page_content,
                            "metadata": doc.metadata,
                            # Add additional payload fields for efficient filtering
                            "subject": doc.metadata.get("subject", "unknown"),
                            "doc_type": doc.metadata.get("doc_type", "unknown"),
                            "year": doc.metadata.get("year", "unknown"),
                            "section": doc.metadata.get("section", "unknown"),
                            "exam": "CUET",
                            "searchable_tags": doc.metadata.get("searchable_tags", [])
                        }
                    )
                    for i, (vector, doc) in enumerate(zip(vectors, docs))
                ]
                
                # Upsert points to collection
                self.client.upsert(collection_name=final_collection_name, points=points)
            
            # Update document status and metadata
            pdf_doc.vectorization_status = "completed"
            pdf_doc.metadata["vectorization"] = {
                "collection_name": final_collection_name,
                "vector_count": len(vectors),
                "model_name": "sentence-transformers/all-MiniLM-L6-v2",
                "vectorization_agent": self.agent_id,
                "vectorization_timestamp": time.time()
            }
            
            self.documents_vectorized += 1
            self.logger.info(f"Vectorized {len(vectors)} chunks from {pdf_doc.file_name} into {final_collection_name}")
            
        except Exception as e:
            pdf_doc.vectorization_status = "failed"
            pdf_doc.error_message = f"Vectorization error: {str(e)}"
            self.logger.error(f"Error vectorizing {pdf_doc.file_name}: {str(e)}")
        
        return {"pdf_doc": pdf_doc, "collection_name": final_collection_name}
    
    def _get_available_collection(self, base_name: str) -> str:
        with self.collection_lock:
            i = 1
            collection_name = base_name
            while True:
                try:
                    info = self.client.get_collection(collection_name)
                    point_count = info.points_count
                    if point_count < self.max_points:
                        return collection_name
                except:
                    vector_size = len(self.embeddings.embed_query("dummy"))
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                    )
                    self.logger.info(f"Created collection '{collection_name}' with vector size {vector_size}")
                    return collection_name
                i += 1
                collection_name = f"{base_name}_{i}"
    
    def get_vectorstore(self, collection_name: str) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embeddings=self.embeddings
        )

class PDFToQdrantCoordinator:
    def __init__(
        self,
        num_extractor_agents: int = 3,
        num_chunking_agents: int = 2,
        num_vectorization_agents: int = 2,
        qdrant_url: str = "http://localhost:6333"
    ):
        self.logger = logging.getLogger("PDFToQdrantCoordinator")
        self.qdrant_url = qdrant_url
        self.collection_lock = threading.Lock()
        
        self.extractor_agents = [PDFExtractorAgent(f"Extractor-{i+1}") for i in range(num_extractor_agents)]
        self.chunking_agents = [ChunkingAgent(f"Chunker-{i+1}") for i in range(num_chunking_agents)]
        self.vectorization_agents = [
            VectorizationAgent(f"Vectorizer-{i+1}", qdrant_url, self.collection_lock)
            for i in range(num_vectorization_agents)
        ]
        
        self.total_documents = 0
        self.completed_extraction = 0
        self.completed_chunking = 0
        self.completed_vectorization = 0
        self.failed_documents = 0
        self.skipped_documents = 0
        
        self.workflow = self._build_workflow()
        self.logger.info(
            f"Coordinator initialized with {num_extractor_agents} extractors, "
            f"{num_chunking_agents} chunkers, {num_vectorization_agents} vectorizers"
        )
    
    def _ensure_collection_exists(self, collection_name: str):
        with self.collection_lock:
            client = QdrantClient(url=self.qdrant_url)
            try:
                client.get_collection(collection_name)
                self.logger.info(f"Collection '{collection_name}' already exists")
            except:
                embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={"device": "cpu"}
                )
                vector_size = len(embeddings.embed_query("dummy"))
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
                self.logger.info(f"Created collection '{collection_name}' with vector size {vector_size}")
    
    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(State)
        workflow.add_node("extract", self._extract_node)
        workflow.add_node("chunk", self._chunk_node)
        workflow.add_node("vectorize", self._vectorize_node)
        workflow.add_edge("extract", "chunk")
        workflow.add_edge("chunk", "vectorize")
        workflow.add_edge("vectorize", END)
        workflow.set_entry_point("extract")
        return workflow.compile()
    
    def _extract_node(self, state: State) -> State:
        agent_idx = self.completed_extraction % len(self.extractor_agents)
        return self.extractor_agents[agent_idx].extract_text_from_pdf(state)
    
    def _chunk_node(self, state: State) -> State:
        agent_idx = self.completed_chunking % len(self.chunking_agents)
        return self.chunking_agents[agent_idx].chunk_document(state)
    
    def _vectorize_node(self, state: State) -> State:
        agent_idx = self.completed_vectorization % len(self.vectorization_agents)
        return self.vectorization_agents[agent_idx].vectorize_document(state)
    
    def enqueue_documents(self, pdf_folder_path: str) -> int:
        count = 0
        for root, dirs, files in os.walk(pdf_folder_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(root, pdf_folder_path)
                    doc_type = relative_path.split(os.path.sep)[0] if relative_path != '.' else "unknown"
                    pdf_doc = PDFDocument(file_path=file_path, file_name=file)
                    pdf_doc.metadata["doc_type"] = doc_type
                    collection_name = doc_type
                    self._ensure_collection_exists(collection_name)
                    self.workflow.invoke({"pdf_doc": pdf_doc, "collection_name": collection_name})
                    count += 1
        self.total_documents = count
        self.logger.info(f"Enqueued {count} PDF documents")
        return count
    
    def process_documents(self, pdf_folder_path: str, max_workers: int = 5) -> List[State]:
        self.logger.info("Starting document processing pipeline")
        start_time = time.time()
        
        self.enqueue_documents(pdf_folder_path)
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for root, dirs, files in os.walk(pdf_folder_path):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(root, pdf_folder_path)
                        doc_type = relative_path.split(os.path.sep)[0] if relative_path != '.' else "unknown"
                        pdf_doc = PDFDocument(file_path=file_path, file_name=file)
                        pdf_doc.metadata["doc_type"] = doc_type
                        collection_name = doc_type
                        self._ensure_collection_exists(collection_name)
                        futures.append(
                            executor.submit(self.workflow.invoke, {"pdf_doc": pdf_doc, "collection_name": collection_name})
                        )
            
            for future in futures:
                result = future.result()
                pdf_doc = result["pdf_doc"]
                if pdf_doc.extraction_status == "completed":
                    self.completed_extraction += 1
                if pdf_doc.metadata.get("chunking", {}).get("num_chunks", 0) > 0:
                    self.completed_chunking += 1
                if pdf_doc.vectorization_status == "completed":
                    self.completed_vectorization += 1
                elif pdf_doc.vectorization_status == "failed":
                    self.failed_documents += 1
                elif pdf_doc.vectorization_status == "skipped":
                    self.skipped_documents += 1
                results.append(result)
        
        processing_time = time.time() - start_time
        self.logger.info(f"Processing completed in {processing_time:.2f} seconds")
        self.logger.info(
            f"Processed {self.completed_extraction}/{self.total_documents} extractions, "
            f"{self.completed_chunking}/{self.total_documents} chunkings, "
            f"{self.completed_vectorization}/{self.total_documents} vectorizations, "
            f"{self.failed_documents} failed, {self.skipped_documents} skipped"
        )
        return results

class PDFToQdrantSystem:
    def __init__(
        self,
        num_extractor_agents: int = 3,
        num_chunking_agents: int = 2,
        num_vectorization_agents: int = 2,
        qdrant_url: str = "http://localhost:6333",
        openrouter_api_key: str = None
    ):
        self.openrouter_api_key = openrouter_api_key
        self.coordinator = PDFToQdrantCoordinator(
            num_extractor_agents=num_extractor_agents,
            num_chunking_agents=num_chunking_agents,
            num_vectorization_agents=num_vectorization_agents,
            qdrant_url=qdrant_url
        )
        self.logger = logging.getLogger("PDFToQdrantSystem")
    
    def process_folder(self, folder_path: str, max_workers: int = 5) -> Dict[str, Any]:
        self.logger.info(f"Processing folder: {folder_path}")
        results = self.coordinator.process_documents(folder_path, max_workers)
        
        failed_details = [
            {
                "file_name": state["pdf_doc"].file_name,
                "collection_name": state["collection_name"],
                "error_message": state["pdf_doc"].error_message,
                "extraction_status": state["pdf_doc"].extraction_status,
                "vectorization_status": state["pdf_doc"].vectorization_status
            }
            for state in results if state["pdf_doc"].error_message or state["pdf_doc"].vectorization_status in ["failed", "skipped"]
        ]
        
        # Group documents by subject and type for better reporting
        subject_stats = {}
        for state in results:
            if state["pdf_doc"].vectorization_status == "completed":
                subject = state["pdf_doc"].metadata.get("subject", "unknown")
                doc_type = state["pdf_doc"].metadata.get("doc_type", "unknown")
                key = f"{subject}_{doc_type}"
                
                if key not in subject_stats:
                    subject_stats[key] = 0
                subject_stats[key] += 1
        
        summary = {
            "success": self.coordinator.total_documents > 0,
            "total_documents": self.coordinator.total_documents,
            "extraction_completed": self.coordinator.completed_extraction,
            "chunking_completed": self.coordinator.completed_chunking,
            "vectorization_completed": self.coordinator.completed_vectorization,
            "failed": self.coordinator.failed_documents,
            "skipped": self.coordinator.skipped_documents,
            "failed_details": failed_details,
            "subject_stats": subject_stats,
            "results": results
        }
        
        self.logger.info(
            f"Processing complete. {summary['vectorization_completed']} documents vectorized, "
            f"{summary['failed']} failed, {summary['skipped']} skipped"
        )
        
        # Log subject-specific statistics
        if subject_stats:
            self.logger.info("Documents processed by subject and type:")
            for key, count in subject_stats.items():
                self.logger.info(f"  - {key}: {count} documents")
                
        return summary
        
    def get_cuet_syllabus(self, subject: str = None, section: str = None) -> Dict[str, Any]:
        """
        Specialized method to retrieve CUET syllabus information with filtering options.
        
        Args:
            subject: Filter by subject (e.g., "physics", "chemistry")
            section: Filter by section/domain (e.g., "A", "B", "C")
            
        Returns:
            Dictionary with syllabus information and metadata
        """
        try:
            # Construct collection name based on subject
            collection_name = f"cuet_{subject}_syllabus" if subject else "syllabus"
            
            # Check if collection exists
            try:
                self.coordinator.vectorization_agents[0].client.get_collection(collection_name)
            except Exception:
                self.logger.warning(f"Collection {collection_name} not found, trying generic collection")
                collection_name = "cuet_syllabus"
                try:
                    self.coordinator.vectorization_agents[0].client.get_collection(collection_name)
                except Exception:
                    return {"error": f"No syllabus collections found for {subject}", "success": False}
            
            # Build query based on subject
            if subject:
                query = f"What is the complete syllabus for {subject} in CUET exam?"
            else:
                query = "What is the CUET exam syllabus?"
                
            # Add section filter if provided
            if section:
                query += f" Focus on section {section}."
            
            # Get vectorstore
            vectorstore = self.coordinator.vectorization_agents[0].get_vectorstore(collection_name)
            
            # Build metadata filter
            metadata_filters = {"doc_type": "syllabus"}
            if subject:
                metadata_filters["subject"] = subject
            if section:
                metadata_filters["section"] = section.upper()
            
            # Retrieve documents with higher k for syllabus
            retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={
                    "k": 10,  # Retrieve more chunks for syllabus
                    "filter": metadata_filters
                }
            )
            
            # Get documents
            docs = retriever.get_relevant_documents(query)
            
            # Extract and organize syllabus content
            syllabus_content = []
            metadata = {}
            
            for doc in docs:
                syllabus_content.append(doc.page_content)
                
                # Collect metadata from first document if not already set
                if not metadata and doc.metadata:
                    metadata = {
                        "subject": doc.metadata.get("subject", "unknown"),
                        "year": doc.metadata.get("year", "unknown"),
                        "exam": "CUET",
                        "education_level": "undergraduate"
                    }
            
            return {
                "success": True,
                "subject": subject or "all",
                "section": section,
                "syllabus_content": syllabus_content,
                "metadata": metadata,
                "collection_used": collection_name
            }
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve CUET syllabus: {str(e)}")
            return {"error": str(e), "success": False}
    
    def process_single_pdf(self, file_path: str, collection_name: str) -> Dict[str, Any]:
        self.logger.info(f"Processing single PDF: {file_path} to collection: {collection_name}")
        pdf_doc = PDFDocument(file_path=file_path, file_name=os.path.basename(file_path))
        self.coordinator._ensure_collection_exists(collection_name)
        result = self.coordinator.workflow.invoke({"pdf_doc": pdf_doc, "collection_name": collection_name})
        pdf_doc = result["pdf_doc"]
        
        extraction_completed = 1 if pdf_doc.extraction_status == "completed" else 0
        chunking_completed = 1 if pdf_doc.metadata.get("chunking", {}).get("num_chunks", 0) > 0 else 0
        vectorization_completed = 1 if pdf_doc.vectorization_status == "completed" else 0
        failed = 1 if pdf_doc.vectorization_status == "failed" else 0
        skipped = 1 if pdf_doc.vectorization_status == "skipped" else 0
        
        failed_details = []
        if pdf_doc.error_message or pdf_doc.vectorization_status in ["failed", "skipped"]:
            failed_details.append({
                "file_name": pdf_doc.file_name,
                "collection_name": collection_name,
                "error_message": pdf_doc.error_message,
                "extraction_status": pdf_doc.extraction_status,
                "vectorization_status": pdf_doc.vectorization_status
            })
        
        summary = {
            "success": vectorization_completed == 1,
            "total_documents": 1,
            "extraction_completed": extraction_completed,
            "chunking_completed": chunking_completed,
            "vectorization_completed": vectorization_completed,
            "failed": failed,
            "skipped": skipped,
            "failed_details": failed_details,
            "results": [result]
        }
        
        status = "successfully vectorized" if vectorization_completed else "skipped" if skipped else "failed to be vectorized"
        self.logger.info(f"Processing complete. Document {status}")
        return summary
    
    def query_vectorstore(self, query: str, collection_name: str = None, subject: str = None, doc_type: str = None, 
                         year: str = None, section: str = None, model_name: str = "mistralai/mistral-7b-instruct", k: int = 5) -> dict:
        """
        Enhanced query function that supports filtering by CUET metadata.
        
        Args:
            query: The query text
            collection_name: Specific collection to query (optional)
            subject: Filter by subject (e.g., "physics", "chemistry")
            doc_type: Filter by document type (e.g., "syllabus", "pyq")
            year: Filter by year
            section: Filter by section/domain (e.g., "A", "B", "C")
            model_name: LLM model to use
            k: Number of documents to retrieve
            
        Returns:
            Dictionary with result text and metadata about the sources
        """
        if not self.openrouter_api_key:
            self.logger.error("OpenRouter API key not provided")
            return {"result": "Error: OpenRouter API key not provided", "sources": []}
        
        try:
            # Determine which collection to query based on metadata
            if collection_name is None and subject is not None:
                if doc_type is not None:
                    collection_name = f"cuet_{subject}_{doc_type}"
                else:
                    collection_name = f"cuet_{subject}"
                    
                # Check if collection exists, if not fall back to default
                try:
                    self.coordinator.vectorization_agents[0].client.get_collection(collection_name)
                except Exception:
                    self.logger.warning(f"Collection {collection_name} not found, using default collection")
                    collection_name = "unknown"
            
            # Get vectorstore
            vectorstore = self.coordinator.vectorization_agents[0].get_vectorstore(collection_name)
            
            # Build metadata filter if any filters are specified
            metadata_filters = {}
            if subject is not None:
                metadata_filters["subject"] = subject
            if doc_type is not None:
                metadata_filters["doc_type"] = doc_type
            if year is not None:
                metadata_filters["year"] = year
            if section is not None:
                metadata_filters["section"] = section.upper()
            
            # Initialize LLM
            llm = ChatOpenAI(
                model_name=model_name,
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key,
                temperature=0.5
            )
            
            # Create retriever with metadata filters
            retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={
                    "k": k,
                    "filter": metadata_filters if metadata_filters else None
                }
            )
            
            # Create QA chain
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=retriever,
                return_source_documents=True
            )
            
            # Execute query
            result = qa_chain.invoke({"query": query})
            
            # Extract source information
            sources = []
            if "source_documents" in result:
                for doc in result["source_documents"]:
                    source_info = {
                        "content_preview": doc.page_content[:100] + "...",
                        "subject": doc.metadata.get("subject", "unknown"),
                        "doc_type": doc.metadata.get("doc_type", "unknown"),
                        "file_name": doc.metadata.get("file_name", "unknown"),
                        "year": doc.metadata.get("year", "unknown"),
                        "section": doc.metadata.get("section", "unknown")
                    }
                    sources.append(source_info)
            
            return {
                "result": result["result"],
                "sources": sources,
                "collection_used": collection_name,
                "filters_applied": metadata_filters
            }
            
        except Exception as e:
            self.logger.error(f"Failed to query vectorstore: {str(e)}")
            return {
                "result": f"Error querying vectorstore: {str(e)}",
                "sources": [],
                "error": str(e)
            }

if __name__ == "__main__":
    openrouter_api_key = "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"
    pdf_system = PDFToQdrantSystem(
        num_extractor_agents=3,
        num_chunking_agents=2,
        num_vectorization_agents=2,
        openrouter_api_key=openrouter_api_key
    )
    
    # Define the path to your CUET syllabus and question papers
    cuet_data_path = r"C:\Users\DELL\Desktop\Raj\DATA"
    
    # Process all PDF files in the folder
    print("\n===== Processing CUET PDF Documents =====")
    results = pdf_system.process_folder(
        folder_path=cuet_data_path,
        max_workers=5
    )
    
    # Print processing summary
    print(f"\nProcessed {results['total_documents']} CUET PDF documents:")
    print(f"- {results['extraction_completed']} extracted successfully")
    print(f"- {results['chunking_completed']} chunked successfully")
    print(f"- {results['vectorization_completed']} vectorized successfully")
    print(f"- {results['failed']} failed")
    print(f"- {results['skipped']} skipped")
    
    # Print subject-specific statistics
    if "subject_stats" in results and results["subject_stats"]:
        print("\nDocuments processed by subject and type:")
        for key, count in results["subject_stats"].items():
            print(f"  - {key}: {count} documents")
    
    if results["failed_details"]:
        print("\nFailed or skipped documents:")
        for detail in results["failed_details"]:
            print(f"  {detail['file_name']} ({detail['collection_name']}): {detail['error_message']}")
    
    # Process a single PDF file with specific collection name
    print("\n===== Processing Single CUET PDF Document =====")
    single_result = pdf_system.process_single_pdf(
        file_path=r"C:\Users\DELL\Desktop\Raj\DATA\physics_syllabus_2023.pdf",  # Example filename
        collection_name="cuet_physics_syllabus"  # Using the enhanced collection naming
    )
    
    if single_result['vectorization_completed'] == 1:
        print("Single PDF processed successfully!")
    elif single_result['skipped'] == 1:
        print("Single PDF processing skipped: already exists.")
    else:
        print("Single PDF processing failed.")
        if single_result["failed_details"]:
            print("Failure details:", single_result["failed_details"])
    
    # Demonstrate querying with different metadata filters
    if results['vectorization_completed'] > 0 or single_result['vectorization_completed'] == 1:
        print("\n===== Querying CUET Vector Database =====")
        
        # Example 1: Query by subject only
        query1 = "What are the main topics covered in Physics syllabus?"
        print(f"\nQuery 1: {query1}")
        print("Filtering by subject='physics'")
        answer1 = pdf_system.query_vectorstore(query=query1, subject="physics")
        print(f"Answer: {answer1['result']}")
        print(f"Collection used: {answer1['collection_used']}")
        print(f"Sources: {len(answer1['sources'])} documents")
        
        # Example 2: Query by subject and document type
        query2 = "What are common questions in Chemistry previous year papers?"
        print(f"\nQuery 2: {query2}")
        print("Filtering by subject='chemistry', doc_type='pyq'")
        answer2 = pdf_system.query_vectorstore(
            query=query2, 
            subject="chemistry", 
            doc_type="pyq"
        )
        print(f"Answer: {answer2['result']}")
        
        # Example 3: Query with year filter
        query3 = "What were the important topics in the 2022 Mathematics exam?"
        print(f"\nQuery 3: {query3}")
        print("Filtering by subject='mathematics', year='2022'")
        answer3 = pdf_system.query_vectorstore(
            query=query3, 
            subject="mathematics", 
            year="2022"
        )
        print(f"Answer: {answer3['result']}")
        
        # Example 4: Query with section filter
        query4 = "What topics are covered in Section B of the Biology syllabus?"
        print(f"\nQuery 4: {query4}")
        print("Filtering by subject='biology', section='B'")
        answer4 = pdf_system.query_vectorstore(
            query=query4, 
            subject="biology", 
            section="B"
        )
        print(f"Answer: {answer4['result']}")
        
        # Print source information for the last query
        if answer4['sources']:
            print("\nSource documents for the last query:")
            for i, source in enumerate(answer4['sources']):
                print(f"Source {i+1}:")
                print(f"  Subject: {source['subject']}")
                print(f"  Document type: {source['doc_type']}")
                print(f"  File: {source['file_name']}")
                print(f"  Preview: {source['content_preview']}")
        
        # Demonstrate the specialized syllabus retrieval method
        print("\n===== Retrieving CUET Syllabus Information =====")
        
        # Get physics syllabus
        print("\nRetrieving Physics Syllabus:")
        physics_syllabus = pdf_system.get_cuet_syllabus(subject="physics")
        if physics_syllabus.get("success", False):
            print(f"Successfully retrieved {physics_syllabus['subject']} syllabus")
            print(f"Collection used: {physics_syllabus['collection_used']}")
            print(f"Number of content chunks: {len(physics_syllabus['syllabus_content'])}")
            if physics_syllabus['syllabus_content']:
                print("\nSample syllabus content:")
                print(physics_syllabus['syllabus_content'][0][:200] + "...")
        else:
            print(f"Failed to retrieve physics syllabus: {physics_syllabus.get('error', 'Unknown error')}")
        
        # Get chemistry syllabus section B
        print("\nRetrieving Chemistry Syllabus Section B:")
        chem_syllabus_b = pdf_system.get_cuet_syllabus(subject="chemistry", section="B")
        if chem_syllabus_b.get("success", False):
            print(f"Successfully retrieved {chem_syllabus_b['subject']} syllabus section {chem_syllabus_b['section']}")
            print(f"Collection used: {chem_syllabus_b['collection_used']}")
            print(f"Number of content chunks: {len(chem_syllabus_b['syllabus_content'])}")
            if chem_syllabus_b['syllabus_content']:
                print("\nSample syllabus content:")
                print(chem_syllabus_b['syllabus_content'][0][:200] + "...")
        else:
            print(f"Failed to retrieve chemistry syllabus: {chem_syllabus_b.get('error', 'Unknown error')}")
    
    print("\n===== CUET Vector Database Processing Complete =====")