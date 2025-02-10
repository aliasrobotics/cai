import pytest
from cai.rag.vector_db import QdrantConnector

@pytest.fixture
def vector_db():
    connector = QdrantConnector()
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
        {"name": "point1", "category": "test"},
        {"name": "point2", "category": "test"},
        {"name": "point3", "category": "test"}
    ]
    
    # Add points
    success = vector_db.add_points("test_collection", texts, metadata)
    assert success is True
    
    # Search points
    query = "first test document"
    results = vector_db.search("test_collection", query, limit=2)
    print(results)
    assert len(results) > 0
    assert "id" in results[0]
    assert "score" in results[0]
    assert "metadata" in results[0]
    assert results[0]["metadata"]["name"] == "point1"

def test_filter_points(vector_db):
    # Add test points first
    texts = ["Test document for filtering"]
    metadata = [{"name": "filtered_point", "category": "test_filter"}]
    vector_db.add_points("test_collection", texts, metadata)
    
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
    # Add test points
    texts = ["Document for filtered search"]
    metadata = [{"name": "search_point", "category": "test_search"}]
    vector_db.add_points("test_collection", texts, metadata)
    
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
    assert len(results) > 0
    assert results[0]["metadata"]["category"] == "test_search"

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
            "difficulty": "medium"
        },
        {
            "challenge": "reverse_engineering",
            "description": "Binary analysis revealed hardcoded encryption key. Reversed algorithm to decrypt flag.",
            "solution": "Used Ghidra to analyze binary, found key: 'CTF_KEY_2024'",
            "difficulty": "hard"
        }
    ]
    # Store CTF data
    success = vector_db.add_points(collection_name, texts, metadata)
    assert success is True
    
    # Verify data can be retrieved
    filter_conditions = {
        "must": [
            {
                "key": "challenge",
                "match": {"value": "web_exploit"}
            }
        ]
    }
    
    results = vector_db.filter_points(collection_name, filter_conditions)
    print(results)
    assert len(results) > 0
    assert results[0]["metadata"]["challenge"] == "web_exploit"
    assert "solution" in results[0]["metadata"]
    assert "difficulty" in results[0]["metadata"]
