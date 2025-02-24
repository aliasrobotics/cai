"""
Provides an interface to Qdrant vector database for storing and retrieving
embeddings used in the RAG (Retrieval Augmented Generation) system.

Usage:
    # Initialize connector
    db = QdrantConnector(model_name="text-embedding-3-large")

    # Create collection
    db.create_collection("my_collection")

    # Add points
    db.add_points(
        "my_collection",
        texts=["text1", "text2"],
        metadata=[{"key": "val1"}, {"key": "val2"}]
    )

    # Search similar texts
    results = db.search("my_collection", "query text", limit=10)

The connector supports both OpenAI and sentence-transformer embedding models.
For OpenAI models, use model names starting with "text-".
For sentence-transformers, use any other model name.
(Ensure is available and supported by sentence-transformers)

Key Features:
- Automatic embedding generation using OpenAI or sentence-transformers
- Collection management (create, delete, add points)
- Similarity search with optional filtering
- Metadata storage alongside vectors
- Support for both cosine and euclidean distance metrics
"""

import os
from typing import Dict, List, Optional
import openai  # pylint: disable=import-error
from qdrant_client import QdrantClient, models  # pylint: disable=import-error
from sentence_transformers import (  # pylint: disable=import-error
    SentenceTransformer
)
from dotenv import load_dotenv  # pylint: disable=import-error
load_dotenv()


class QdrantConnector:
    """
    A connector class for interacting with a Qdrant vector database.

    This class provides methods to:
    - Create and manage collections in Qdrant
    - Generate embeddings using OpenAI or sentence-transformers models
    - Add document vectors with metadata to collections
    - Perform similarity searches across collections

    The connector handles embeddings based on model name:
    - OpenAI: Use "text-*" models
    - Sentence-transformers: Use any other model

    Attributes:
        client (QdrantClient): The Qdrant client instance
        model_name (str): Name of the embedding model being used
        openai_client (openai.Client): OpenAI client for text-* models
        model (SentenceTransformer): Sentence transformer model instance
        vector_size (int): Dimension size of the embedding vectors
    """

    def __init__(
        self,
        model_name: str = "text-embedding-3-large",
        host: str = "192.168.2.13",
        port: int = 6333
    ):
        """
        Initialize the Qdrant connector with embedding model.

        Args:
            model_name: Name of embedding model to use
                (text-* for OpenAI, others for sentence-transformers)
            host: Qdrant server host
            port: Qdrant server port
        """
        self.client = QdrantClient(host=host, port=port)
        self.model_name = model_name

        if model_name.startswith("text"):
            # OpenAI model
            self.openai_client = openai.Client(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url="https://api.openai.com/v1"
            )
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
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error creating collection: {e}")
            return False

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using configured model"""
        if self.model_name.startswith("text"):
            result = self.openai_client.embeddings.create(
                input=texts,
                model=self.model_name
            )
            vectors = [data.embedding for data in result.data]
        else:
            vectors = self.model.encode(texts).tolist()
        return vectors

    def add_points(
        self,
        id_point: int,
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
            for idx, (vector, meta, text) in enumerate(  # pylint: disable=unused-variable # noqa: E501
                zip(vectors, metadata, texts)
            ):
                point_id = id_point
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
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error adding points: {e}")
            return False

    def search(  # pylint: disable=too-many-arguments,too-many-locals # noqa: E501
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
            List of dictionaries containing id, score, metadata and text for
            matching points
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

                # Extract texts from ordered results
                extracted_texts = []
                if results:
                    numeric_points = [
                        p for p in results
                        if isinstance(p.id, (int, float))
                    ]
                    sorted_points = sorted(
                        numeric_points,
                        key=lambda x: x.id
                    )
                    for i, point in enumerate(sorted_points, 1):
                        if hasattr(point, 'payload') and isinstance(
                            point.payload, dict
                        ):
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
                    if hasattr(point, 'payload') and isinstance(
                        point.payload, dict
                    ):
                        extracted_texts.append(
                            point.payload.get("text", "")
                        )
            return "\n".join(extracted_texts)
        except Exception as e:  # pylint: disable=broad-exception-caught
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
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error filtering: {e}")
            return []


def get_previous_memory(query: str, top_k: int = 20) -> str:
    """
    Get the previous memory from the vector database.
    Returns steps ordered by ID from 1 to top_k.
    """

    if query != "":  # Semantic
        collection_name = "_all_"  # pylint: disable=W0621
    else:  # Episodic
        collection_name = os.getenv('CAI_MEMORY_COLLECTION', 'default')
    vector_db = QdrantConnector()

    if collection_name == "_all_":
        results = vector_db.search(
            collection_name=collection_name,
            query_text=query,
            limit=top_k,
            sort_by_id=False)
    else:
        results = vector_db.search(
            collection_name=collection_name,
            query_text=query,
            limit=top_k,
            sort_by_id=True)

    return results
