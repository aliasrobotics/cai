import pytest
from cai.accountability.llm_cost import calculate_conversation_cost

@pytest.mark.parametrize("total_input_tokens, total_output_tokens, model, expected", [
    (1000, 2000, "gpt-4", {"input_cost": 0.03, "output_cost": 0.12, "total_cost": 0.15, "input_tokens": 1000, "output_tokens": 2000}),
    (5000, 10000, "gpt-4o", {"input_cost": 0.0125, "output_cost": 0.1, "total_cost": 0.1125, "input_tokens": 5000, "output_tokens": 10000}),
    (10000, 20000, "gpt-4o-mini", {"input_cost": 0.0015, "output_cost": 0.012, "total_cost": 0.0135, "input_tokens": 10000, "output_tokens": 20000}),
    (15000, 30000, "o1-mini", {"input_cost": 0.0165, "output_cost": 0.132, "total_cost": 0.1485, "input_tokens": 15000, "output_tokens": 30000}),
    (20000, 40000, "gpt-3.5-turbo", {"input_cost": 0.03, "output_cost": 0.08, "total_cost": 0.11, "input_tokens": 20000, "output_tokens": 40000}),
    (1000, 2000, "claude-3-5-sonnet-20240620", {"input_cost": 0.003, "output_cost": 0.03, "total_cost": 0.033, "input_tokens": 1000, "output_tokens": 2000}),
])

def test_calculate_conversation_cost(total_input_tokens, total_output_tokens, model, expected):
    result = calculate_conversation_cost(total_input_tokens, total_output_tokens, model)
    print(result)
    assert result == expected

