from cai.util import function_to_json


def test_basic_function():
    def basic_function(arg1, arg2):
        return arg1 + arg2

    result = function_to_json(basic_function, format='original')
    assert result == {
        "type": "function",
        "function": {
            "name": "basic_function",
            "description": "",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "string", "description": ""},
                    "arg2": {"type": "string", "description": ""},
                },
                "required": ["arg1", "arg2"],
            },
        },
    }


def test_complex_function():
    def complex_function_with_types_and_descriptions(
        arg1: int, arg2: str, arg3: float = 3.14, arg4: bool = False
    ):
        """This is a complex function with a docstring."""
        pass

    result = function_to_json(complex_function_with_types_and_descriptions, format='original')
    assert result == {
        "type": "function",
        "function": {
            "name": "complex_function_with_types_and_descriptions",
            "description": "This is a complex function with a docstring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "integer", "description": ""},
                    "arg2": {"type": "string", "description": ""},
                    "arg3": {"type": "number", "description": ""},
                    "arg4": {"type": "boolean", "description": ""},
                },
                "required": ["arg1", "arg2"],
            },
        },
    }



def test_gemini_format():
    def sample_function(arg1: str, arg2: int = 0):
        """A sample function for testing Gemini format."""
        pass
    
    result = function_to_json(sample_function, format='gemini')
    assert result == {
        "name": "sample_function",
        "description": "A sample function for testing Gemini format.",
        "parameters": {
            "type": "object",
            "properties": {
                "arg1": {"type": "string", "description": ""},
                "arg2": {"type": "integer", "description": ""},
            },
            "required": ["arg1"],
        },
    }
