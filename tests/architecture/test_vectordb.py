import pytest
from cai.rag.vector_db import QdrantConnector

@pytest.fixture
def vector_db():
    connector = QdrantConnector(model_name="all-MiniLM-L6-v2") # Using a common sentence transformer model # CRAP MODEL ONLY TEST # noqa: E501
    collection_name = "test_collection"
    # Delete collection if it exists
    try:
        connector.client.delete_collection(collection_name)
    except:
        pass
    connector.create_collection(collection_name)
    yield connector
    # Cleanup
    try:
        connector.client.delete_collection(collection_name)
    except:
        pass

def test_create_collection(vector_db):
    # Delete collection if it exists
    try:
        vector_db.client.delete_collection("new_collection")
    except:
        pass
    success = vector_db.create_collection("new_collection")
    assert success is True

def test_add_and_search_points(vector_db):
    # Test data
    texts = [
        "This is the first test document",
        "Here is the second document", 
        "And finally the third one"
    ]
    metadata = [
        {"name": "point1", "category": "test", "text": texts[0]},
        {"name": "point2", "category": "test", "text": texts[1]},
        {"name": "point3", "category": "test", "text": texts[2]}
    ]
    
    # Add points with unique id 1
    success = vector_db.add_points(1, "test_collection", texts, metadata)
    assert success is True
    
    # Search points
    query = "And finally the third one"
    results = vector_db.search("test_collection", query, limit=1, sort_by_id=False)
    print(results)
    assert isinstance(results, str)
    assert "And finally the third one" in results

def test_filter_points(vector_db):
    # Add test point first with unique id 2
    texts = ["Test document for filtering"]
    metadata = [{"name": "filtered_point", "category": "test_filter", "text": texts[0]}]
    vector_db.add_points(2, "test_collection", texts, metadata)
    
    # Test filtering
    filter_conditions = {
        "must": [
            {
                "key": "category",
                "match": {"value": "test_filter"}
            }
        ]
    }
    results = vector_db.filter_points("test_collection", filter_conditions)
    print(results)

    assert len(results) > 0
    assert results[0]["metadata"]["category"] == "test_filter"
    assert "id" in results[0]
    assert "metadata" in results[0]

def test_search_with_filter(vector_db):
    # Add test point with unique id 3
    texts = ["Document for filtered search"]
    metadata = [{"name": "search_point", "category": "test_search", "text": texts[0]}]
    vector_db.add_points(3, "test_collection", texts, metadata)
    
    # Search with filter
    query = "filtered search"
    filter_conditions = {
        "must": [
            {
                "key": "category",
                "match": {"value": "test_search"}
            }
        ]
    }
    
    results = vector_db.search("test_collection", query, filter_conditions)
    print(results)
    assert isinstance(results, str)
    assert "filtered search" in results

def test_store_ctf_info(vector_db):
    # Create collection for CTF data
    collection_name = "test_ctf_2024"
    # Delete collection if it exists
    try:
        vector_db.client.delete_collection(collection_name)
    except:
        pass
    vector_db.create_collection(collection_name)
    
    # Test data simulating CTF solutions
    texts = [
        "SQL injection vulnerability found in login form. The attack involved using UNION SELECT statements to extract administrator credentials.",
        "Binary analysis of the target executable revealed a hardcoded encryption key. The solution involved reversing the algorithm to decrypt the flag."
    ]
    metadata = [
        {
            "challenge": "web_exploit", 
            "description": "Found SQL injection in login form. Used UNION SELECT to extract admin credentials.",
            "solution": "payload: admin' UNION SELECT 'admin','pass'--",
            "difficulty": "medium",
            "text": texts[0]
        },
        {
            "challenge": "reverse_engineering",
            "description": "Binary analysis revealed hardcoded encryption key. Reversed algorithm to decrypt flag.", 
            "solution": "Used Ghidra to analyze binary, found key: 'CTF_KEY_2024'",
            "difficulty": "hard",
            "text": texts[1]
        }
    ]
    # Store CTF data with unique id 4
    success = vector_db.add_points(4, collection_name, texts, metadata)
    assert success is True

    # Search for the stored data
    query = "SQL injection login form"
    results = vector_db.search(collection_name, query, limit=1)
    print(results)
    assert isinstance(results, str)
    assert "hardcoded encryption key" in results