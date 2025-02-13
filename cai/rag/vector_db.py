from typing import Dict, List, Optional, Union
import openai
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import uuid

load_dotenv()

class QdrantConnector:
    def __init__(self, model_name: str = "text-embedding-3-large", host: str = "192.168.2.13", port: int = 6333):
        """
        Initialize the Qdrant connector with embedding model.
        
        Args:
            model_name: Name of embedding model to use (text-* for OpenAI, others for sentence-transformers)
            host: Qdrant server host
            port: Qdrant server port
        """
        self.client = QdrantClient(host=host, port=port)
        self.model_name = model_name
        
        if model_name.startswith("text"):
            # OpenAI model
            self.openai_client = openai.Client()
            self.vector_size = 3072  
        else:
            # Sentence transformers model
            self.model = SentenceTransformer(model_name)
            self.vector_size = self.model.get_sentence_embedding_dimension()
        
    def create_collection(
        self, 
        collection_name: str,
        distance: str = "Cosine"
    ) -> bool:
        """
        Create a new collection in Qdrant.
        
        Args:
            collection_name: Name of the collection
            distance: Distance metric ("Cosine", "Euclid" or "Dot")
        """
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=distance
                )
            )
            return True
        except Exception as e:
            print(f"Error creating collection: {e}")
            return False

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using configured model"""
        if self.model_name.startswith("text"):
            result = self.openai_client.embeddings.create(
                input=texts,
                model=self.model_name
            )
            return [data.embedding for data in result.data]
        else:
            return self.model.encode(texts).tolist()

    def add_points(
        self,
        id: int,
        collection_name: str,
        texts: List[str],
        metadata: List[Dict],
    ) -> bool:
        """
        Add points to collection.
        
        Args:
            collection_name: Name of collection
            texts: List of texts to embed
            metadata: List of metadata dictionaries
            ids: Optional list of IDs for points
        """
        try:
            vectors = self._get_embeddings(texts)
            points = []
            for idx, (vector, meta, text) in enumerate(zip(vectors, metadata, texts)):
                point_id = id
                meta["text"] = text
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=meta
                    )
                )
                
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            return True
        except Exception as e:
            print(f"Error adding points: {e}")
            return False
        
    def search(
        self,
        collection_name: str,
        query_text: str,
        filter_conditions: Optional[Dict] = None,
        limit: int = 10,
        sort_by_id: bool = False
    ) -> List[Dict]:
        """
        Search similar points with optional filtering.
        
        Args:
            collection_name: Name of collection
            query_text: Query text to search for
            filter_conditions: Filter conditions for search
            limit: Maximum number of results to return
            sort_by_id: Whether to sort results by ID instead of similarity
        
        Returns:
            List of dictionaries containing id, score, metadata and text for matching points
        """
        try:
            if sort_by_id:
                # Get first 10 points by ID
                results = self.client.scroll(
                    collection_name=collection_name,
                    limit=10,  # Fixed limit of 10
                    with_payload=True,
                    with_vectors=False,
                    offset=0  # Start from beginning
                )[0]  # scroll returns (points, offset)
                #print(results)
                # Extract texts from ordered results
                extracted_texts = []
                if results:
                    numeric_points = [p for p in results if isinstance(p.id, (int, float))]
                    sorted_points = sorted(numeric_points, key=lambda x: x.id)
                    for i, point in enumerate(sorted_points, 1):
                        if hasattr(point, 'payload') and isinstance(point.payload, dict):
                            text = point.payload.get("text", "")
                            extracted_texts.append(f"Step: {i}. {text}")
                return "\n".join(extracted_texts)
            
            # Original similarity search logic
            query_vector = self._get_embeddings([query_text])[0]
            
            search_filter = None
            if filter_conditions:
                search_filter = models.Filter(**filter_conditions)
            
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=search_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            
            extracted_texts = []
            if results and hasattr(results, 'points'):
                for point in results.points:
                    if hasattr(point, 'payload') and isinstance(point.payload, dict):
                        extracted_texts.append(point.payload.get("text", ""))
            return "\n".join(extracted_texts)
        except Exception as e:
            print(f"Error searching: {e}")
            return ""

    def filter_points(
        self,
        collection_name: str,
        filter_conditions: Dict
    ) -> List[Dict]:
        """
        Retrieve points based on structured filtering only.
        
        Args:
            collection_name: Name of collection
            filter_conditions: Filter conditions
        """
        try:
            results = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(**filter_conditions),
                limit=100  # Adjust as needed
            )[0]  # scroll returns (points, offset)
            
            return [
                {
                    "id": point.id,
                    "metadata": point.payload
                } for point in results
            ]
        except Exception as e:
            print(f"Error filtering: {e}")
            return []