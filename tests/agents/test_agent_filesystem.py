import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List
from cai.core import CAI, Agent
from cai.tools.reconnaissance.filesystem import list_dir, cat_file


class TestFilesystemAgent:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # Setup - create temporary test directory
        self.test_dir = tempfile.mkdtemp()
        yield
        # Teardown - cleanup temporary directory
        shutil.rmtree(self.test_dir)

    def create_test_files(self, files: List[str], content: str = "") -> None:
        """Helper to create test files in temporary directory"""
        for file in files:
            path = Path(self.test_dir) / file
            path.parent.mkdir(parents=True, exist_ok=True)
            if content:
                path.write_text(content)
            else:
                path.touch()

    @pytest.mark.flaky(reruns=3)
    def test_agent_list_directories(self):
        """Test filesystem agent with basic files"""
        client = CAI()

        filesystem_agent = Agent(
            model="qwen2.5:14b",
            name="Filesystem Agent",
            instructions="You are an agent that helps users explore and interact with the filesystem.",
            functions=[list_dir, cat_file]
        )
        test_files = ['visible.txt', '.hidden.txt', 'test.log', '.config']
        self.create_test_files(test_files)

        show_prompts = [
            f"List all files in {self.test_dir}",
            f"Show me everything in {self.test_dir}",
            f"What files are in {self.test_dir}?",
            f"Display directory contents of {self.test_dir}"
        ]

        for prompt in show_prompts:
            messages = [{"role": "user", "content": prompt}]
            response = client.run(
                agent=filesystem_agent,
                messages=messages,
                debug=False)
            result = response.messages[-1]["content"]

            assert 'visible.txt' in result
            assert 'test.log' in result

    @pytest.mark.flaky(reruns=3)
    def test_agent_list_hidden_files(self):
        """Test filesystem agent with hidden files"""
        client = CAI()

        filesystem_agent = Agent(
            model="qwen2.5:14b",
            name="Filesystem Agent",
            instructions="You are an agent that helps users explore and interact with the filesystem.",
            functions=[list_dir, cat_file]
        )

        test_files = ['regular.txt', '.hidden1', '.hidden2', '.secret']
        self.create_test_files(test_files)

        hidden_prompts = [
            f"Show hidden files in {self.test_dir}",
            f"List all files including hidden ones in {self.test_dir}",
            f"Display hidden files in {self.test_dir}",
            f"Show me dot files in {self.test_dir}"
        ]

        for prompt in hidden_prompts:
            messages = [{"role": "user", "content": prompt}]
            response = client.run(
                agent=filesystem_agent,
                messages=messages,
                debug=False)
            result = response.messages[-1]["content"]

            # Should show hidden files
            for hidden_file in ['.hidden1', '.hidden2', '.secret', "tmp"]:
                assert hidden_file in result

    @pytest.mark.flaky(reruns=3)
    def test_agent_read_file(self):
        """Test filesystem agent reading file contents"""
        client = CAI()

        filesystem_agent = Agent(
            model="qwen2.5:14b",
            name="Filesystem Agent",
            instructions="You are an agent that helps users explore and interact with the filesystem.",
            functions=[list_dir, cat_file]
        )

        test_files = {
            'simple.txt': 'Hello World!',
            'multiline.txt': 'Line 1\nLine 2\nLine 3',
            'tabs.txt': 'Column1\tColumn2',
            '.hidden.txt': 'Secret content'
        }

        for filename, content in test_files.items():
            self.create_test_files([filename], content)

        read_prompts = [
            f"Show me the contents of {self.test_dir}/simple.txt",
            f"Read {self.test_dir}/multiline.txt with line numbers",
            f"Display {self.test_dir}/tabs.txt and show tabs",
            f"What's in {self.test_dir}/simple.txt?",
            f"Cat {self.test_dir}/multiline.txt"
        ]

        for prompt in read_prompts:
            messages = [{"role": "user", "content": prompt}]
            response = client.run(
                agent=filesystem_agent,
                messages=messages,
                debug=False)
            result = response.messages[-1]["content"]

            # Should contain file contents
            if 'simple.txt' in prompt:
                assert 'Hello World!' in result
            elif 'multiline.txt' in prompt:
                assert 'Line 1' in result
                assert 'Line 2' in result
            elif 'tabs.txt' in prompt:
                assert 'Column1' in result
                assert 'Column2' in result
