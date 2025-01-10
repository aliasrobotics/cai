from cai.tools.reconnaissance.filesystem import list_dir, cat_file

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List


class TestListDir:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # Setup - create temporary test directory
        self.test_dir = tempfile.mkdtemp()
        yield
        # Teardown - cleanup temporary directory
        shutil.rmtree(self.test_dir)

    def create_test_files(self, files: List[str]) -> None:
        """Helper to create test files in temporary directory"""
        for file in files:
            path = Path(self.test_dir) / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def test_basic_directory_listing(self):
        """Test basic directory listing functionality"""
        test_files = ['file1.txt', 'file2.txt']
        self.create_test_files(test_files)

        result = list_dir(self.test_dir)
        assert len(result) == 20  # 14 without break line
        assert all(file in result for file in test_files)

    def test_hidden_files(self):
        """Test list_dir args and hidden files"""
        test_files = ['.file1.txt', '.file2.txt']
        self.create_test_files(test_files)

        result = list_dir(self.test_dir, "-a")
        assert ".file1.txt" in result  # 14 without break line
        assert all(file in result for file in test_files)

    def test_permission_extraction(self):
        """Test permission extraction"""
        self.create_test_files(["file1.txt"])
        result = list_dir(self.test_dir, "-lia")
        assert "-rw-r--r--" in result
        assert "file1.txt" in result


class TestReadFile:
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
            path.write_text(content)

    def test_basic_file_read(self):
        """Test basic file reading functionality"""
        test_content = "Hello World!"
        test_file = "test.txt"
        self.create_test_files([test_file], test_content)

        result = cat_file(str(Path(self.test_dir) / test_file))
        assert result == test_content

    def test_read_empty_file(self):
        """Test reading an empty file"""
        test_file = "empty.txt"
        self.create_test_files([test_file])

        result = cat_file(str(Path(self.test_dir) / test_file))
        assert result == ""

    def test_read_with_line_numbers(self):
        """Test reading file with line numbers"""
        test_content = "Line 1\nLine 2\nLine 3"
        test_file = "numbered.txt"
        self.create_test_files([test_file], test_content)

        result = cat_file(str(Path(self.test_dir) / test_file), "-n")
        assert "1\tLine 1" in result
        assert "2\tLine 2" in result
        assert "3\tLine 3" in result

    def test_read_with_show_ends(self):
        """Test reading file with show ends option"""
        test_content = "Line 1\nLine 2\n"
        test_file = "ends.txt"
        self.create_test_files([test_file], test_content)

        result = cat_file(str(Path(self.test_dir) / test_file), "-E")
        assert "Line 1$\n" in result
        assert "Line 2$\n" in result

    def test_read_with_show_tabs(self):
        """Test reading file with show tabs option"""
        test_content = "Column1\tColumn2"
        test_file = "tabs.txt"
        self.create_test_files([test_file], test_content)

        result = cat_file(str(Path(self.test_dir) / test_file), "-T")
        assert "Column1^IColumn2" in result

    def test_read_with_multiple_options(self):
        """Test reading file with multiple options"""
        test_content = "Line 1\tLine2\nLine 3"
        test_file = "multiple.txt"
        self.create_test_files([test_file], test_content)

        result = cat_file(str(Path(self.test_dir) / test_file), "-nTE")
        assert "     1\tLine 1^ILine2$\n" in result
        assert "     2\tLine 3" in result
