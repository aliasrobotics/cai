import os
import pytest
from mako.template import Template
from cai.rag.vector_db import QdrantConnector

@pytest.fixture
def template():
    return Template(filename="cai/prompts/master_template.md")

@pytest.fixture
def base_agent():
    return type('Agent', (), {'instructions': 'Test instructions'})()

@pytest.fixture
def vector_db():
    db = QdrantConnector()
    db.create_collection("test_ctf")
    # Add some test data
    texts = [
        "Found flag in /etc/passwd",
        "Exploited SQL injection vulnerability",
        "Discovered open port 22"
    ]
    metadata = [
        {"step": 1},
        {"step": 2}, 
        {"step": 3}
    ]
    for i, (text, meta) in enumerate(zip(texts, metadata)):
        db.add_points(i, "test_ctf", [text], [meta])
    return db

def test_master_template_basic(template, base_agent):
    """Test basic master template rendering without optional components"""
    result = template.render(agent=base_agent)
    print(result)
    assert 'Test instructions' in result
    assert 'CTF_INSIDE' not in result

def test_master_template_with_ctf_inside_true(template, base_agent):
    """Test master template with CTF_INSIDE=true"""
    os.environ['CTF_INSIDE'] = 'true'
    result = template.render(agent=base_agent)
    print(result)
    assert 'You are INSIDE the target machine' in result
    del os.environ['CTF_INSIDE']

def test_master_template_with_ctf_inside_false(template, base_agent):
    """Test master template with CTF_INSIDE=false"""
    os.environ['CTF_INSIDE'] = 'false'
    result = template.render(agent=base_agent)
    print(result)
    assert 'You are OUTSIDE the target machine' in result
    del os.environ['CTF_INSIDE']

def test_master_template_with_env_vars(template, base_agent, vector_db):
    """Test master template with environment variables and vector DB"""
    os.environ['CTF_NAME'] = 'test_ctf'
    os.environ['CTF_RAG_MEMORY'] = 'true'
    result = template.render(agent=base_agent, get_previous_memory=lambda x, top_k: "\n".join([
        f"Step: {meta['step']}. {text}" 
        for text, meta in zip(
            ["Found flag in /etc/passwd", "Exploited SQL injection vulnerability", "Discovered open port 22"],
            [{"step": 1}, {"step": 2}, {"step": 3}]
        )
    ]))
    print(result)
    assert 'SQL injection' in result
    assert 'Found flag in /etc/passwd' in result
    del os.environ['CTF_NAME']
    del os.environ['CTF_RAG_MEMORY']

def test_master_template_no_instructions(template):
    """Test master template without agent instructions"""
    agent = type('Agent', (), {})()
    result = template.render(agent=agent)
    print(result)
    assert result.strip().startswith('')
