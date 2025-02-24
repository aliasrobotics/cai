import os
import pytest
from mako.template import Template

@pytest.fixture
def template():
    return Template(filename="cai/prompts/core/system_master_template.md")

@pytest.fixture
def base_agent():
    return type('Agent', (), {'instructions': 'Test instructions'})()

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

def test_master_template_with_env_vars(template, base_agent):
    """Test master template with environment variables and vector DB"""
    os.environ['CTF_NAME'] = 'test_ctf'
    result = template.render(agent=base_agent)
    print(result)
    assert "Test instructions" in result
    del os.environ['CTF_NAME']

def test_master_template_no_instructions(template):
    """Test master template without agent instructions"""
    agent = type('Agent', (), {'instructions': ''})()
    result = template.render(agent=agent)
    print(result)
    assert result.strip().startswith('')
