import os
import time
import queue
import threading
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

# For PDF processing
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PDFProcessingSystem")

@dataclass
class PDFDocument:
    """Data structure to store PDF information and content."""
    file_path: str
    file_name: str
    content: str = ""
    page_count: int = 0
    extraction_status: str = "pending"  # pending, processing, completed, failed
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    processing_agent: str = ""
    error_message: Optional[str] = None

class PDFExtractorAgent:
    """Agent responsible for extracting text from PDF documents."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.documents_processed = 0
        self.logger = logging.getLogger(f"PDFExtractorAgent-{agent_id}")
        self.logger.info(f"Agent {agent_id} initialized")
    
    def extract_text_from_pdf(self, pdf_doc: PDFDocument) -> PDFDocument:
        """Extract text content from a PDF file."""
        self.logger.info(f"Processing file: {pdf_doc.file_name}")
        pdf_doc.extraction_status = "processing"
        pdf_doc.processing_agent = self.agent_id
        
        start_time = time.time()
        
        try:
            # Open the PDF file
            doc = fitz.open(pdf_doc.file_path)
            pdf_doc.page_count = len(doc)
            
            # Extract content from each page
            full_text = []
            for page_num in range(pdf_doc.page_count):
                page = doc[page_num]
                full_text.append(page.get_text())
            
            pdf_doc.content = "\n".join(full_text)
            
            # Extract metadata
            pdf_doc.metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "keywords": doc.metadata.get("keywords", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "mod_date": doc.metadata.get("modDate", ""),
            }
            
            doc.close()
            pdf_doc.extraction_status = "completed"
            self.documents_processed += 1
            
        except Exception as e:
            pdf_doc.extraction_status = "failed"
            pdf_doc.error_message = str(e)
            self.logger.error(f"Error processing {pdf_doc.file_name}: {str(e)}")
        
        pdf_doc.processing_time = time.time() - start_time
        self.logger.info(f"Completed processing {pdf_doc.file_name} in {pdf_doc.processing_time:.2f} seconds")
        
        return pdf_doc

class PDFValidatorAgent:
    """Agent responsible for validating the extracted content from PDFs."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.documents_validated = 0
        self.logger = logging.getLogger(f"PDFValidatorAgent-{agent_id}")
        self.logger.info(f"Validator {agent_id} initialized")
    
    def validate_extraction(self, pdf_doc: PDFDocument) -> PDFDocument:
        """Validate that the PDF content was extracted correctly."""
        self.logger.info(f"Validating extraction of: {pdf_doc.file_name}")
        
        if pdf_doc.extraction_status != "completed":
            self.logger.warning(f"Cannot validate {pdf_doc.file_name} - extraction status: {pdf_doc.extraction_status}")
            return pdf_doc
        
        # Validation checks
        validation_results = {
            "has_content": len(pdf_doc.content) > 0,
            "page_count_valid": pdf_doc.page_count > 0,
        }
        
        # Content sanity checks
        if validation_results["has_content"]:
            # Check if content seems reasonable (not just garbage characters)
            # This is a simple heuristic - you might want to improve this
            alphabetic_ratio = sum(c.isalpha() for c in pdf_doc.content[:1000]) / max(1, len(pdf_doc.content[:1000]))
            validation_results["content_looks_valid"] = alphabetic_ratio > 0.2
        else:
            validation_results["content_looks_valid"] = False
        
        pdf_doc.metadata["validation"] = validation_results
        pdf_doc.metadata["validation_agent"] = self.agent_id
        
        # Overall validation result
        if all(validation_results.values()):
            pdf_doc.metadata["validation_status"] = "valid"
            self.logger.info(f"Validation passed for {pdf_doc.file_name}")
        else:
            pdf_doc.metadata["validation_status"] = "invalid"
            self.logger.warning(f"Validation failed for {pdf_doc.file_name}: {validation_results}")
        
        self.documents_validated += 1
        return pdf_doc

class PDFProcessingCoordinator:
    """Coordinates the extraction and validation of PDF documents."""
    
    def __init__(self, num_extractor_agents: int = 3, num_validator_agents: int = 2):
        self.logger = logging.getLogger("PDFProcessingCoordinator")
        
        # Create agents
        self.extractor_agents = [PDFExtractorAgent(f"Extractor-{i+1}") for i in range(num_extractor_agents)]
        self.validator_agents = [PDFValidatorAgent(f"Validator-{i+1}") for i in range(num_validator_agents)]
        
        # Create queues for communication
        self.extraction_queue = queue.Queue()
        self.validation_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # Processing statistics
        self.total_documents = 0
        self.completed_documents = 0
        self.failed_documents = 0
        
        self.logger.info(f"Coordinator initialized with {num_extractor_agents} extractors and {num_validator_agents} validators")
    
    def enqueue_documents(self, pdf_folder_path: str) -> int:
        """Find PDF files in the specified folder and add them to the processing queue."""
        if not os.path.exists(pdf_folder_path):
            self.logger.error(f"Folder path does not exist: {pdf_folder_path}")
            return 0
        
        count = 0
        for file_name in os.listdir(pdf_folder_path):
            if file_name.lower().endswith('.pdf'):
                file_path = os.path.join(pdf_folder_path, file_name)
                pdf_doc = PDFDocument(file_path=file_path, file_name=file_name)
                self.extraction_queue.put(pdf_doc)
                count += 1
        
        self.total_documents = count
        self.logger.info(f"Enqueued {count} PDF documents for processing")
        return count
    
    def _extraction_worker(self):
        """Worker function for extraction thread."""
        while True:
            try:
                # Get a document from the queue with a timeout
                pdf_doc = self.extraction_queue.get(timeout=1)
                
                # Assign to an extractor agent based on simple round-robin
                agent_idx = self.completed_documents % len(self.extractor_agents)
                agent = self.extractor_agents[agent_idx]
                
                # Process the document
                processed_doc = agent.extract_text_from_pdf(pdf_doc)
                
                # Send to validation queue
                self.validation_queue.put(processed_doc)
                
                # Mark as done
                self.extraction_queue.task_done()
                
            except queue.Empty:
                # No more documents to process
                break
            except Exception as e:
                self.logger.error(f"Error in extraction worker: {str(e)}")
    
    def _validation_worker(self):
        """Worker function for validation thread."""
        while True:
            try:
                # Get a document from the queue with a timeout
                pdf_doc = self.validation_queue.get(timeout=1)
                
                # Assign to a validator agent based on simple round-robin
                agent_idx = self.completed_documents % len(self.validator_agents)
                agent = self.validator_agents[agent_idx]
                
                # Validate the document
                validated_doc = agent.validate_extraction(pdf_doc)
                
                # Send to result queue
                self.result_queue.put(validated_doc)
                
                # Update statistics
                if validated_doc.extraction_status == "completed":
                    self.completed_documents += 1
                else:
                    self.failed_documents += 1
                
                # Mark as done
                self.validation_queue.task_done()
                
            except queue.Empty:
                # No more documents to process
                break
            except Exception as e:
                self.logger.error(f"Error in validation worker: {str(e)}")
    
    def process_documents(self, max_workers: int = 5) -> List[PDFDocument]:
        """Process all documents in the queue using multiple workers."""
        self.logger.info("Starting document processing")
        start_time = time.time()
        
        # Start extraction workers
        extraction_threads = []
        for _ in range(min(max_workers, self.total_documents)):
            thread = threading.Thread(target=self._extraction_worker)
            thread.daemon = True
            thread.start()
            extraction_threads.append(thread)
        
        # Start validation workers
        validation_threads = []
        for _ in range(min(max_workers, self.total_documents)):
            thread = threading.Thread(target=self._validation_worker)
            thread.daemon = True
            thread.start()
            validation_threads.append(thread)
        
        # Wait for all extraction threads to complete
        for thread in extraction_threads:
            thread.join()
        
        # Wait for all validation threads to complete
        for thread in validation_threads:
            thread.join()
        
        # Collect results
        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get())
        
        processing_time = time.time() - start_time
        self.logger.info(f"Document processing completed in {processing_time:.2f} seconds")
        self.logger.info(f"Processed {self.completed_documents} documents successfully, {self.failed_documents} failed")
        
        return results

class PDFProcessingSystem:
    """Main system that handles the entire PDF processing workflow."""
    
    def __init__(self, num_extractor_agents: int = 5, num_validator_agents: int = 2):
        self.coordinator = PDFProcessingCoordinator(
            num_extractor_agents=num_extractor_agents,
            num_validator_agents=num_validator_agents
        )
        self.logger = logging.getLogger("PDFProcessingSystem")
    
    def process_folder(self, folder_path: str, max_workers: int = 5) -> Dict[str, Any]:
        """Process all PDF files in the specified folder."""
        self.logger.info(f"Processing folder: {folder_path}")
        
        # Enqueue documents
        num_documents = self.coordinator.enqueue_documents(folder_path)
        
        if num_documents == 0:
            self.logger.warning(f"No PDF files found in folder: {folder_path}")
            return {"success": False, "message": "No PDF files found", "results": []}
        
        # Process documents
        results = self.coordinator.process_documents(max_workers=max_workers)
        
        # Create summary
        summary = {
            "success": True,
            "total_documents": num_documents,
            "completed": self.coordinator.completed_documents,
            "failed": self.coordinator.failed_documents,
            "results": results
        }
        
        self.logger.info(f"Processing complete. {summary['completed']} successful, {summary['failed']} failed.")
        return summary
    
    def extract_single_pdf(self, file_path: str) -> PDFDocument:
        """Extract content from a single PDF file."""
        if not os.path.exists(file_path) or not file_path.lower().endswith('.pdf'):
            self.logger.error(f"Invalid PDF file path: {file_path}")
            return PDFDocument(file_path=file_path, file_name=os.path.basename(file_path), 
                              extraction_status="failed", error_message="Invalid PDF file path")
        
        # Create a document object
        pdf_doc = PDFDocument(file_path=file_path, file_name=os.path.basename(file_path))
        
        # Use the first extractor agent
        extractor = self.coordinator.extractor_agents[0]
        processed_doc = extractor.extract_text_from_pdf(pdf_doc)
        
        # Use the first validator agent
        validator = self.coordinator.validator_agents[0]
        validated_doc = validator.validate_extraction(processed_doc)
        
        return validated_doc


# Example usage
if __name__ == "__main__":
    # Create the processing system with 5 extractor agents
    pdf_system = PDFProcessingSystem(num_extractor_agents=5, num_validator_agents=2)
    
    # Process a folder of PDFs
    results = pdf_system.process_folder(r"C:\Users\DELL\Desktop\Raj\DATA", max_workers=8)
    
    # Print summary
    print(f"Processed {results['total_documents']} PDF documents:")
    print(f"- {results['completed']} completed successfully")
    print(f"- {results['failed']} failed")
    
    # Example of how to access the extracted content
    for idx, doc in enumerate(results['results']):
        if doc.extraction_status == "completed":
            print(f"\nDocument {idx+1}: {doc.file_name}")
            print(f"Processed by: {doc.processing_agent}")
            print(f"Page count: {doc.page_count}")
            print(f"Content length: {len(doc.content)} characters")
            print(f"First 150 characters: {doc.content[:150]}...")
        else:
            print(f"\nDocument {idx+1}: {doc.file_name} - Processing failed: {doc.error_message}")