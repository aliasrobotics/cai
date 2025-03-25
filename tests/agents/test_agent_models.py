import pytest
import tempfile
import shutil
import statistics
import os
from pathlib import Path
from typing import List, Union
from cai.core import CAI, Agent


class TestFunctionCallBenchmarksBasic:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        yield
        shutil.rmtree(self.test_dir)

    def _test_function_call(self, model_name: str, is_multi: bool) -> bool:
        client = CAI()

        test_agent = Agent(
            model=model_name,
            name="Function Call Demo Agent",
            instructions="You are an agent that demonstrates function calling capabilities.",
            parallel_tool_calls=is_multi
        )

        def add_numbers(a: Union[int, str], b: Union[int, str]) -> str:
            try:
                return str(int(a) + int(b))
            except (ValueError, TypeError):
                return "error"

        def analyze_text(text: str) -> dict:
            try:
                words = str(text).split()
                return {
                    "word_count": str(len(words)),
                    "char_count": str(len(str(text)))
                }
            except (ValueError, TypeError):
                return {
                    "word_count": "error",
                    "char_count": "error"
                }

        test_agent.functions.extend([add_numbers, analyze_text])

        if is_multi:
            prompt = """Please:
            1. Add 5 and 7
            2. Analyze text: 'Hello world'"""
        else:
            prompt = "Add 5 and 7"

        try:
            response = client.run(agent=test_agent, messages=[
                                  {"role": "user", "content": prompt}], debug=False)
            success = "error" not in response.messages[-1]["content"]
            test_type = "Multi" if is_multi else "Single"
            if success:
                print(f"\n✅ {test_type}-function test passed for {model_name}")
            else:
                print(f"\n❌ {test_type}-function test failed for {model_name}")
            return success
        except Exception as e:
            print(f"\n❌ Test failed for {model_name}: {str(e)}")
            return False
    @pytest.mark.parametrize("model", [
        "dwightfoster03/functionary-small-v3.1",
        "llama3.1:8b",
        "qwen2.5:14b",
        "qwen2.5:32b",
        # "marco-o1:7b-fp16"
    ])
    @pytest.mark.xfail(reason="Undeterministic")
    def test_function_call_benchmark(self, model):
        results = []
        print(f"\nTesting {model}")
        single_results = []
        multi_results = []

        for i in range(3):
            print(f"Iteration {i + 1}:")
            single_results.append(self._test_function_call(model, False))
            multi_results.append(self._test_function_call(model, True))

        single_avg = statistics.mean(single_results)
        multi_avg = statistics.mean(multi_results)
        overall = (single_avg + multi_avg) / 2

        print(f"Results for {model}:")
        print(f"Single: {single_avg * 100:.1f}%")
        print(f"Multi: {multi_avg * 100:.1f}%")
        print(f"Overall: {overall * 100:.1f}%")

        results.append({
            "model": model,
            "single": single_avg,
            "multi": multi_avg
        })

        total = statistics.mean([
            (r["single"] + r["multi"]) / 2
            for r in results
        ])

        print(f"\nOverall success rate: {total * 100:.1f}%")
        assert total >= 0.5, "Success rate below 50%"

    def test_agent_model_property(self):
        """
        Test that the Agent model property is correctly set and accessed.
        """
        # Create agent with explicit model
        test_agent = Agent(
            model="o3-mini",
            name="Model Property Test Agent",
            instructions="You are an agent that tests model property functionality."
        )

        # Test that the model property returns the expected value
        assert test_agent.model == "o3-mini", f"Expected 'o3-mini', got '{test_agent.model}'"
        print(f"✅ Model property correctly returned: {test_agent.model}")
        
        # Test changing the model
        test_agent.model = "another-model"
        assert test_agent.model == "another-model", f"Expected 'another-model', got '{test_agent.model}'"
        print(f"✅ Model property correctly updated: {test_agent.model}")
        
        # Test default model when none specified
        test_agent = Agent(
            name="Default Model Test Agent", 
            instructions="You are an agent that tests default model functionality."
        )
        assert test_agent.model == "qwen2.5:14b", f"Expected 'qwen2.5:14b', got '{test_agent.model}'"
        print(f"✅ Default model correctly used: {test_agent.model}")
