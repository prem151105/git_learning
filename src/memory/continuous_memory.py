"""
Continuous Memory module for the Memory & Learning Layer.

This module implements both short-term and long-term memory capabilities,
with vector-based storage and retrieval for continuous learning.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple

import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContinuousMemory:
    """
    Implements memory systems for storing and learning from experiences.
    
    This class provides both short-term memory for action history and page states,
    and long-term vector storage for patterns and task experiences.
    """
    
    def __init__(self):
        """Initialize the ContinuousMemory."""
        # Short-term memory (recency-based)
        self.recent_actions = []  # List of recent actions
        self.recent_states = {}   # Map of URL -> recent page state
        self.max_recent_actions = 100
        self.max_recent_states = 20
        
        # Long-term memory (vector database)
        self.vector_db_client = None
        self.vector_db_collection = None
        self.vector_db_type = os.environ.get("VECTOR_DB_TYPE", "chromadb")
        self.vector_db_url = os.environ.get("VECTOR_DB_URL", "")
        self.vector_db_dimensions = 1536  # Default for OpenAI embeddings
        
        # Embedding client
        self.embedding_client = None
        self.embedding_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large")
        
        logger.info("ContinuousMemory instance created")
    
    async def initialize(self):
        """Initialize vector database and embedding clients."""
        try:
            # Initialize embedding client
            import openai
            self.embedding_client = openai.AsyncClient(
                api_key=os.environ.get("OPENAI_API_KEY")
            )
            
            # Initialize vector database based on configuration
            if self.vector_db_type == "chromadb":
                await self._initialize_chromadb()
            elif self.vector_db_type == "pinecone":
                await self._initialize_pinecone()
            elif self.vector_db_type == "weaviate":
                await self._initialize_weaviate()
            else:
                # Default to in-memory vector store if configured type is not available
                await self._initialize_in_memory_vector_store()
            
            logger.info(f"ContinuousMemory initialized with {self.vector_db_type} vector database")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing continuous memory: {str(e)}")
            # Fall back to in-memory vector store
            await self._initialize_in_memory_vector_store()
            return False
    
    async def _initialize_chromadb(self):
        """Initialize ChromaDB vector database."""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Connect to ChromaDB
            self.vector_db_client = chromadb.Client(
                Settings(
                    chroma_api_impl="rest",
                    chroma_server_host=self.vector_db_url.split("://")[1].split(":")[0] if "://" in self.vector_db_url else "localhost",
                    chroma_server_http_port=int(self.vector_db_url.split(":")[-1]) if ":" in self.vector_db_url else 8000
                )
            )
            
            # Create or get collection
            self.vector_db_collection = self.vector_db_client.get_or_create_collection(
                name="agent_memory",
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info("ChromaDB vector database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {str(e)}")
            # Fall back to in-memory vector store
            await self._initialize_in_memory_vector_store()
    
    async def _initialize_pinecone(self):
        """Initialize Pinecone vector database."""
        try:
            import pinecone
            
            # Initialize connection
            pinecone.init(
                api_key=os.environ.get("PINECONE_API_KEY", ""),
                environment=os.environ.get("PINECONE_ENVIRONMENT", "us-west1-gcp")
            )
            
            # Get or create index
            index_name = "agent-memory"
            if index_name not in pinecone.list_indexes():
                pinecone.create_index(
                    name=index_name,
                    dimension=self.vector_db_dimensions,
                    metric="cosine"
                )
            
            self.vector_db_client = pinecone
            self.vector_db_collection = pinecone.Index(index_name)
            
            logger.info("Pinecone vector database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {str(e)}")
            # Fall back to in-memory vector store
            await self._initialize_in_memory_vector_store()
    
    async def _initialize_weaviate(self):
        """Initialize Weaviate vector database."""
        try:
            import weaviate
            from weaviate.auth import AuthApiKey
            
            # Connect to Weaviate
            auth_config = None
            weaviate_key = os.environ.get("WEAVIATE_API_KEY")
            if weaviate_key:
                auth_config = AuthApiKey(api_key=weaviate_key)
            
            client = weaviate.Client(
                url=self.vector_db_url or "http://localhost:8080",
                auth_client_secret=auth_config,
            )
            
            # Create schema if it doesn't exist
            if not client.schema.exists("AgentMemory"):
                class_obj = {
                    "class": "AgentMemory",
                    "description": "Memory entries for the agent's experiences",
                    "vectorizer": "text2vec-openai",
                    "moduleConfig": {
                        "text2vec-openai": {
                            "model": self.embedding_model,
                            "type": "text"
                        }
                    },
                    "properties": [
                        {
                            "name": "task",
                            "dataType": ["text"],
                            "description": "The task description",
                        },
                        {
                            "name": "content",
                            "dataType": ["text"],
                            "description": "The memory content",
                        },
                        {
                            "name": "type",
                            "dataType": ["string"],
                            "description": "The type of memory",
                        },
                        {
                            "name": "timestamp",
                            "dataType": ["number"],
                            "description": "When the memory was created",
                        }
                    ]
                }
                client.schema.create_class(class_obj)
            
            self.vector_db_client = client
            self.vector_db_collection = "AgentMemory"  # Collection is the class name in Weaviate
            
            logger.info("Weaviate vector database initialized")
            
        except Exception as e:
            logger.error(f"Error initializing Weaviate: {str(e)}")
            # Fall back to in-memory vector store
            await self._initialize_in_memory_vector_store()
    
    async def _initialize_in_memory_vector_store(self):
        """Initialize a simple in-memory vector store as fallback."""
        logger.warning("Using in-memory vector store (data will not persist)")
        
        # Simple in-memory vector store
        self.vector_db_client = {
            "vectors": [],  # List of (id, vector, metadata) tuples
            "type": "in-memory"
        }
        self.vector_db_collection = "memory"
        self.vector_db_type = "in-memory"
    
    async def store_experience(self, task: str, actions: List[Dict], outcome: Dict) -> str:
        """
        Store an experience in long-term memory.
        
        Args:
            task: Task description
            actions: List of action steps taken
            outcome: Result of the task execution
            
        Returns:
            str: ID of the stored memory
        """
        try:
            # Generate a unique ID for this memory
            memory_id = str(uuid.uuid4())
            
            # Format the experience for storage
            content = json.dumps({
                "task": task,
                "actions": actions,
                "outcome": outcome,
                "timestamp": time.time()
            })
            
            # Get embedding for the task and content
            embedding = await self._get_embedding(f"{task}\n{content}")
            
            # Store in vector database
            if self.vector_db_type == "chromadb":
                self.vector_db_collection.add(
                    ids=[memory_id],
                    embeddings=[embedding],
                    metadatas=[{"task": task, "success": outcome.get("success", False)}],
                    documents=[content]
                )
                
            elif self.vector_db_type == "pinecone":
                self.vector_db_collection.upsert([
                    (memory_id, embedding, {"task": task, "success": outcome.get("success", False), "content": content})
                ])
                
            elif self.vector_db_type == "weaviate":
                self.vector_db_client.data_object.create(
                    {
                        "task": task,
                        "content": content,
                        "type": "experience",
                        "timestamp": time.time()
                    },
                    class_name=self.vector_db_collection,
                    uuid=memory_id,
                    vector=embedding
                )
                
            elif self.vector_db_type == "in-memory":
                self.vector_db_client["vectors"].append((
                    memory_id,
                    embedding,
                    {
                        "task": task,
                        "success": outcome.get("success", False),
                        "content": content
                    }
                ))
            
            logger.info(f"Experience stored in memory with ID {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Error storing experience: {str(e)}")
            return ""
    
    async def retrieve_similar_tasks(self, current_task: str, limit: int = 5) -> List[Dict]:
        """
        Retrieve experiences related to the current task.
        
        Args:
            current_task: Current task description
            limit: Maximum number of experiences to retrieve
            
        Returns:
            List[Dict]: List of related experiences
        """
        try:
            # Get embedding for the current task
            embedding = await self._get_embedding(current_task)
            
            results = []
            
            # Query vector database based on type
            if self.vector_db_type == "chromadb":
                query_results = self.vector_db_collection.query(
                    query_embeddings=[embedding],
                    n_results=limit
                )
                
                for i, (doc_id, doc, metadata, distance) in enumerate(zip(
                    query_results["ids"][0],
                    query_results["documents"][0],
                    query_results["metadatas"][0],
                    query_results["distances"][0]
                )):
                    # Parse stored JSON
                    content = json.loads(doc)
                    results.append({
                        "id": doc_id,
                        "task": metadata["task"],
                        "actions": content["actions"],
                        "outcome": content["outcome"],
                        "similarity": 1 - distance  # Convert distance to similarity score
                    })
                    
            elif self.vector_db_type == "pinecone":
                query_results = self.vector_db_collection.query(
                    vector=embedding,
                    top_k=limit,
                    include_metadata=True
                )
                
                for match in query_results["matches"]:
                    # Parse stored JSON
                    content = json.loads(match["metadata"]["content"])
                    results.append({
                        "id": match["id"],
                        "task": match["metadata"]["task"],
                        "actions": content["actions"],
                        "outcome": content["outcome"],
                        "similarity": match["score"]
                    })
                    
            elif self.vector_db_type == "weaviate":
                query_results = (
                    self.vector_db_client.query
                    .get(self.vector_db_collection, ["task", "content", "_additional {certainty}"])
                    .with_near_vector({"vector": embedding})
                    .with_limit(limit)
                    .do()
                )
                
                for obj in query_results["data"]["Get"][self.vector_db_collection]:
                    # Parse stored JSON
                    content = json.loads(obj["content"])
                    results.append({
                        "id": obj["_additional"]["id"],
                        "task": obj["task"],
                        "actions": content["actions"],
                        "outcome": content["outcome"],
                        "similarity": obj["_additional"]["certainty"]
                    })
                    
            elif self.vector_db_type == "in-memory":
                # Simple cosine similarity search
                similarities = []
                for memory_id, memory_vector, metadata in self.vector_db_client["vectors"]:
                    similarity = self._cosine_similarity(embedding, memory_vector)
                    similarities.append((memory_id, similarity, metadata))
                
                # Sort by similarity and get top results
                similarities.sort(key=lambda x: x[1], reverse=True)
                for memory_id, similarity, metadata in similarities[:limit]:
                    # Parse stored JSON
                    content = json.loads(metadata["content"])
                    results.append({
                        "id": memory_id,
                        "task": metadata["task"],
                        "actions": content["actions"],
                        "outcome": content["outcome"],
                        "similarity": similarity
                    })
            
            logger.info(f"Retrieved {len(results)} similar tasks")
            return results
            
        except Exception as e:
            logger.error(f"Error retrieving similar tasks: {str(e)}")
            return []
    
    def record_action(self, action: Dict, result: Dict):
        """
        Record an action in short-term memory.
        
        Args:
            action: Action configuration
            result: Action execution result
        """
        # Add to recent actions list
        self.recent_actions.append({
            "timestamp": time.time(),
            "action": action,
            "result": result
        })
        
        # Maintain maximum size
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions.pop(0)  # Remove oldest action
    
    def record_state(self, url: str, state: Dict):
        """
        Record a page state in short-term memory.
        
        Args:
            url: Page URL
            state: Page state data
        """
        # Add to recent states map
        self.recent_states[url] = {
            "timestamp": time.time(),
            "state": state
        }
        
        # Maintain maximum size
        if len(self.recent_states) > self.max_recent_states:
            # Remove oldest state
            oldest_url = min(self.recent_states.keys(), key=lambda k: self.recent_states[k]["timestamp"])
            del self.recent_states[oldest_url]
    
    def get_recent_actions(self, count: int = 10) -> List[Dict]:
        """
        Get recent actions from short-term memory.
        
        Args:
            count: Maximum number of actions to retrieve
            
        Returns:
            List[Dict]: List of recent actions
        """
        return self.recent_actions[-count:]
    
    def get_recent_state(self, url: str) -> Optional[Dict]:
        """
        Get the recent state for a URL.
        
        Args:
            url: Page URL
            
        Returns:
            Optional[Dict]: Recent state if available
        """
        return self.recent_states.get(url, {}).get("state")
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get an embedding vector for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Embedding vector
        """
        if self.embedding_client:
            try:
                response = await self.embedding_client.embeddings.create(
                    input=text,
                    model=self.embedding_model
                )
                return response.data[0].embedding
            except Exception as e:
                logger.error(f"Error getting embedding: {str(e)}")
        
        # Fallback to random embedding if client fails
        return list(np.random.randn(self.vector_db_dimensions).astype(float))
    
    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec_a: First vector
            vec_b: Second vector
            
        Returns:
            float: Cosine similarity (-1 to 1)
        """
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0
        
        return dot_product / (norm_a * norm_b)
    
    async def shutdown(self):
        """Clean up resources."""
        logger.info("ContinuousMemory resources cleaned up")
