from typing import Dict, List, Optional, Union
import openai
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

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
        collection_name: str,
        texts: List[str],
        metadata: List[Dict],
        ids: Optional[List[int]] = None
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
                point_id = ids[idx] if ids else idx
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
        limit: int = 10
    ) -> List[Dict]:
        """
        Search similar points with optional filtering.
        
        Args:
            collection_name: Name of collection
            query_text: Query text to search for
            filter_conditions: Filter conditions for search
            limit: Maximum number of results to return
        
        Returns:
            List of dictionaries containing id, score, metadata and text for matching points
        """
        try:
            # Get query embedding
            query_vector = self._get_embeddings([query_text])[0]
            
            # Build search filter if conditions provided
            search_filter = None
            if filter_conditions:
                search_filter = models.Filter(**filter_conditions)
            
            # Execute search query
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=search_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
            print(results)
            # Format results
            return [
                {
                    "text": hit.payload.get("text", "")
                } for hit in results
            ]
            
        except Exception as e:
            print(f"Error searching: {e}")
            return []

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