
"""
Benchmark Evaluation Script

This script provides utilities to evaluate language models on cybersecurity-related multiple-choice, question-answering, and PII anonymization benchmarks.

Usage:
    python benchmarks/eval.py --model MODEL_NAME --dataset_file INPUT_FILE --eval EVAL_TYPE --backend BACKEND

Arguments:
    -m, --model           Specify the model to evaluate (e.g., "gpt-4", "qwen2.5:14b", etc.)
    -d, --dataset_file    Path to the dataset file (JSON, TSV, or CSV) containing questions to evaluate
    -B, --backend         Backend to use: "openai", "openrouter", "ollama", "anthropic", "deepseek", etc.
                          (is important to set the api key and api base in environment variables for the backend)
    -e, --eval            Specify the evaluation benchmark (cybermetric, seceval, cti_bench, cyberpii-bench)
    -s, --save_interval   (optional) Save intermediate results every X questions.

Example:

     python benchmarks/eval.py --model ollama/qwen2.5:14b --dataset_file benchmarks/cybermetric/CyberMetric-80-v1.json --eval cybermetric --backend ollama
     python benchmarks/eval.py --model ollama/qwen2.5:14b --dataset_file benchmarks/utils/seceval_dataset/questions-2.json --eval seceval --backend ollama
     python benchmarks/eval.py --model ollama/qwen2.5:14b --dataset_file benchmarks/cti_bench/data/cti-mcq.tsv --eval cti_bench --backend ollama

     python benchmarks/eval.py --model qwen/qwen3-32b:free --dataset_file benchmarks/utils/cybermetric_dataset/CyberMetric-2-v1.json --eval cybermetric --backend openrouter

     python benchmarks/eval.py --model gpt-4o-mini --dataset_file benchmarks/utils/cybermetric_dataset/CyberMetric-2-v1.json --eval cybermetric --backend openai

     python benchmarks/eval.py --model claude-3-7-sonnet-20250219 --dataset_file benchmarks/utils/cybermetric_dataset/CyberMetric-2-v1.json --eval cybermetric --backend anthropic

     python benchmarks/eval.py --model deepseek-chat  --dataset_file benchmarks/utils/cti_bench_dataset/cti-mcq1.tsv --eval cti_bench --backend deepseek

     python benchmarks/eval.py --model alias1 --dataset_file benchmarks/cyberPII-bench/memory01_gold.csv --eval cyberpii-bench --backend alias
       
Some environment variables are required:
    {BACKEND}_API_KEY:  API key for OpenRouter (if using OpenRouter models)
    {BACKEND}_API_BASE:
    
    Most common api base used are:
        OpenRouter: https://openrouter.ai/api/v1
        Ollama: http://localhost:8000/v1
        OpenAI API: https://api.openai.com/v1)
        DeepSeek: https://api.deepseek.com/v1

If you want to see the current cost of the benchmark in real-time, add the pricing of your model in PRICING variable:
    "model": {
            "input_per_million": $/M tokens
            "output_per_million": $/M tokens
        }
"""
import json
import re
import time
import os
import datetime
import random
import string
import argparse
from tqdm import tqdm
import litellm
import requests
import csv
import os
import datetime
import dotenv
import sys
import pandas as pd
from typing import Set

# Import functions from annotation_metrics.py
sys.path.append(os.path.join(os.path.dirname(__file__), 'cyberPII-bench'))
from annotation_metrics import (
    find_entities_with_positions,
    normalize_annotations,
    calculate_metrics,
    generate_overall_report,
    generate_entity_report,
    generate_mistakes_report,
    generate_metrics_report,
    get_output_dir
)


dotenv.load_dotenv()

LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
model_pricing_cache = {}

# Global variables for token costs
input_cost_per_token = 0.0
output_cost_per_token = 0.0


def fetch_model_pricing(model_name):
    """
    Fetch pricing information for a model from LiteLLM's GitHub repository.
    Updates the global token cost variables.
    """
    global input_cost_per_token, output_cost_per_token
    
    # Check cache first
    if model_name in model_pricing_cache:
        input_cost_per_token, output_cost_per_token = model_pricing_cache[model_name]
        return
    try:
        response = requests.get(LITELLM_URL, timeout=5)
        if response.status_code == 200:
            model_pricing_data = response.json()
            pricing_info = model_pricing_data.get(model_name, {})
            input_cost_per_token = pricing_info.get("input_cost_per_token", 0.0)
            output_cost_per_token = pricing_info.get("output_cost_per_token", 0.0)
            model_pricing_cache[model_name] = (input_cost_per_token, output_cost_per_token)
    except Exception as e:
        print(f"Warning: Could not fetch model pricing. Cost will be $0.0. Error: {e}", file=sys.stderr)
        input_cost_per_token = 0.0
        output_cost_per_token = 0.0

def estimate_cost(token_info):
    """
    Estimate the cost using the global variables input_cost_per_token and output_cost_per_token.

    Parameters:
    - token_info: dict with 'input_tokens' and 'output_tokens'

    Returns:
    - cost: total cost in USD
    - pt: prompt tokens
    - rt: response tokens
    """
    global input_cost_per_token, output_cost_per_token

    pt = token_info.get("input_tokens", 0)
    rt = token_info.get("output_tokens", 0)

    prompt_cost = pt * input_cost_per_token
    response_cost = rt * output_cost_per_token
    cost = prompt_cost + response_cost

    return cost, pt, rt

def ask_model(question_obj, instruction, model, api_base, api_key=None, custom_llm_provider=None, is_pii=False):
    """
    Calls the model with the question and choices, returns the extracted answer.
    For PII tasks, uses specialized instructions and system prompt.
    """
    if is_pii:
        # PII anonymization specific setup
        system_prompt = "You are a privacy expert specializing in PII anonymization."
        pii_instruction = """You are a privacy expert. Anonymize the following text by replacing sensitive information with appropriate placeholders.

Replace the following entities with their corresponding placeholders:
- Person names → [PERSON]
- Phone numbers → [PHONE_NUMBER]
- Locations (cities, addresses, etc.) → [LOCATION]
- Credit card numbers → [CREDIT_CARD]
- Cryptocurrency addresses → [CRYPTO]
- IBAN codes → [IBAN_CODE]
- IP addresses → [IP_ADDRESS]
- Email addresses → [EMAIL_ADDRESS]
- URLs → [URL]
- Dates and times → [DATE_TIME]
- Spanish NIF → [NIF]
- Medical license numbers → [MEDICAL_LICENSE]
- US SSN → [US_SSN]
- US bank account numbers → [US_BANK_NUMBER]
- US driver licenses → [US_DRIVER_LICENSE]
- US ITIN → [US_ITIN]
- US passport numbers → [US_PASSPORT]
- Organization names → [ORGANIZATION]
- Street addresses → [ADDRESS]
- Portuguese NRP → [NRP]
- Spanish DNI → [DNI]
- Spanish NIE → [NIE]
- IBAN → [IBAN]
- European bank accounts → [EUROPEAN_BANK_ACCOUNT]

Examples:
- "Contact Mikel at mikel@example.com" → "Contact [PERSON] at [EMAIL_ADDRESS]"
- "Call 555-123-4567 for details" → "Call [PHONE_NUMBER] for details"
- "Visit https://example.com" → "Visit [URL]"

Some annotation rules:

- Each detected entity should be sanitized using the format: [ENTITY_TYPE]
- Priorize IP_ADDRESS to URL: https://192.168.2.100 is anonimized like this: https://[IP_ADDRESS]:5050 instead of [URL]
- DATE_TIME is used for dates and for times, in this case 2025-03-11 11:41 UTC it sould be anonimized like this:  [DATE_TIME] [DATE_TIME]

Anonymize this text, JUST RETURN THE TEXT ANONYMIZED PLEASE:
"""
        prompt = pii_instruction + question_obj
    else:
        # Standard evaluation setup
        system_prompt = "You are a security expert who answers questions."
        prompt = question_obj["Question"] + "\n" + instruction
        if question_obj.get("Choices"):
            prompt += "\nChoices:\n" + question_obj["Choices"]

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider=custom_llm_provider,
        )
        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            # Intenta obtener los tokens usados
            token_info = {}
            if hasattr(response, "usage"):
                token_info = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return content, token_info
    except Exception as e:
        print(f"Error: {e}.")
        return None, {}


def load_dataset(dataset_file, eval_type):
    questions = []  # list of questions: {question: str, answers: dict, solution: str}
    if eval_type == "seceval":
        with open(dataset_file, "r") as f:
            data = json.load(f)
            for question in data:
                questions.append(
                    {
                        "Question": question["question"],
                        "Choices": "\n".join(question["choices"]),
                        "Solution": question["answer"],
                    }
                )

    elif eval_type == "cybermetric":
        with open(dataset_file, "r") as f:
            data = json.load(f)
            for question in data.get("questions", []):
                questions.append(
                    {
                        "Question": question.get("question", ""),
                        "Choices": "\n".join(
                            [f"{k}: {v}" for k, v in question.get("answers", {}).items()]
                        ),
                        "Solution": question.get("solution", ""),
                    }
                )
    elif eval_type == "cti_bench":
        with open(dataset_file, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader, None)
            for row in reader:
                # Handle three possible formats:
                # Format 1: [URL, Question, Option A, Option B, Option C, Option D, Prompt, GT] (8 columns)
                # Format 2: [URL, Platform, Description, Prompt, GT] (5 columns)
                # Format 3: [URL, Description, Prompt, GT] (4 columns)

                if len(row) == 8:
                    # MCQ format
                    questions.append(
                        {
                            "Question": row[1],
                            "Choices": f"A: {row[2]}\nB: {row[3]}\nC: {row[4]}\nD: {row[5]}",
                            "Solution": row[7],
                        }
                    )
                elif len(row) == 5:
                    # ATE format (no choices, just open-ended)
                    questions.append(
                        {
                            "Question": row[2] + row[3],  # Description + Prompt
                            "Choices": "",  # No choices for ATE
                            "Solution": row[4],  # GT
                        }
                    )
                elif len(row) == 4:
                    # RCM format: [URL, Description, Prompt, GT]
                    questions.append(
                        {
                            "Question": row[1] + row[2],  # Description + Prompt
                            "Choices": "",  # No choices for RCM
                            "Solution": row[3],  # GT
                        }
                    )

    return questions

def run_evaluation_pii(model, api_base=None, api_key=None, custom_llm_provider=None, dataset_file=None, skip_entities=None):
    """Run PII anonymization evaluation and append results to original CSV with new column, then calculate metrics."""
    total_cost = 0.0
    total_prompt_tokens = 0
    total_response_tokens = 0
    processed_count = 0

    # Create a safe model name for column naming
    safe_model = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in str(model)])

    # Default skip entities if not provided
    if skip_entities is None:
        skip_entities = set()
    else:
        skip_entities = set(skip_entities)

    # Read the original CSV file
    original_rows = []
    with open(dataset_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = list(reader.fieldnames)
        for row in reader:
            original_rows.append(row)

    # Add new column name for sanitized text if it doesn't exist
    new_column = f"target_text_{safe_model}_sanitized"
    if new_column not in fieldnames:
        fieldnames.append(new_column)

    start_time = datetime.datetime.now()
    print(f"\nStarting PII Anonymization Benchmark")
    print(f"Model: {model}")
    print(f"Dataset: {dataset_file}")
    print(f"Total texts to process: {len(original_rows)}")
    if skip_entities:
        print(f"Skipping entities: {', '.join(sorted(skip_entities))}")
    print("="*50)

    for idx, row in enumerate(original_rows):
        text_to_anonymize = row.get("source_text", "")

        if not text_to_anonymize:
            print(f"Skipping row {idx+1}: No text found")
            continue

        model_answer, token_info = ask_model(text_to_anonymize, "", model, api_base, api_key, custom_llm_provider, is_pii=True)

        print(f"\n[{idx+1}/{len(original_rows)}] Processing ID: {row.get('id', 'unknown')}")
        print(f"Original: {text_to_anonymize[:100]}..." if len(text_to_anonymize) > 100 else f"Original: {text_to_anonymize}")
        print(f"Anonymized: {model_answer[:100]}..." if model_answer and len(model_answer) > 100 else f"Anonymized: {model_answer}")

        # Add the anonymized text to the row
        row[new_column] = model_answer if model_answer else ""
        processed_count += 1

        cost, pt, rt = estimate_cost(token_info)
        total_cost += cost
        total_prompt_tokens += pt
        total_response_tokens += rt
        print(f"Cost: ${cost:.7f} | Total: ${total_cost:.7f}")

        if total_cost > 10:
            print("\n⚠️ Cost limit exceeded ($10). Stopping evaluation.")
            break

    # Save the updated CSV to a new file: memory01_{model}.csv
    base_name = os.path.basename(dataset_file).replace('.csv', '')
    output_file = os.path.join(os.path.dirname(dataset_file), f"{base_name}_{safe_model}.csv")
    with open(output_file, "w", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(original_rows)

    end_time = datetime.datetime.now()
    duration = end_time - start_time

    print("\n" + "="*50)
    print("PII Anonymization Benchmark Completed")
    print("="*50)
    print(f"Model: {model}")
    print(f"Texts processed: {processed_count}/{len(original_rows)}")
    print(f"Total cost: ${total_cost:.7f}")
    print(f"Total tokens - Input: {total_prompt_tokens}, Output: {total_response_tokens}")
    print(f"Duration: {duration}")
    print(f"Results saved to: {output_file} (column: {new_column})")

    # Now calculate metrics using the annotation_metrics functions
    print("\n" + "="*50)
    print("Calculating Evaluation Metrics")
    print("="*50)

    # Load the updated CSV as a DataFrame for metrics calculation
    df = pd.read_csv(output_file, sep=";")

    # Create annotator config for the model
    annotator_config = {
        safe_model: {
            "target_text": new_column,
            "span_labels": f"span_labels_{safe_model}",
            "mbert_bio_labels": f"mbert_bio_labels_{safe_model}",
        }
    }

    # Normalize annotations
    print("Normalizing annotations...")
    df = normalize_annotations(df, annotator_config, skip_entities)

    # Calculate metrics
    print("Calculating metrics...")
    stats = calculate_metrics(df, annotator_config, skip_entities)

    # Generate reports
    base_dir = os.path.dirname(os.path.abspath(output_file))
    dir_annotator = os.path.join(base_dir, safe_model)
    output_dir = get_output_dir(dir_annotator)

    print("Generating evaluation reports...")
    generate_overall_report(stats, output_dir, output_file, annotator_config, skip_entities)
    generate_entity_report(stats, output_dir, list(annotator_config.keys()), skip_entities)
    generate_mistakes_report(stats, output_dir, list(annotator_config.keys()), skip_entities)
    generate_metrics_report(stats, output_dir, list(annotator_config.keys()), skip_entities)

    # Print summary metrics
    if safe_model in stats["metrics_per_annotator"]:
        metrics = stats["metrics_per_annotator"][safe_model]
        print(f"\nOverall Performance:")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall: {metrics['recall']:.4f}")
        print(f"  F1 Score: {metrics['f1_score']:.4f}")
        print(f"  F2 Score: {metrics['f2_score']:.4f}")

    print(f"\nDetailed reports saved in: {output_dir}/")
    if skip_entities:
        print(f"Note: The following entities were excluded from evaluation: {', '.join(sorted(skip_entities))}")

def run_evaluation(dataset, instruction, model, api_base=None, api_key=None, custom_llm_provider=None, save_interval=None, eval_type=None, dataset_file=None):
    results = []
    total_cost = 0.0
    total_prompt_tokens = 0
    total_response_tokens = 0

    # Create a timestamp for this evaluation run
    run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in str(model)])

    start_time = datetime.datetime.now()

    for idx, q in enumerate(dataset):
        model_answer, token_info = ask_model(q, instruction, model, api_base, api_key, custom_llm_provider)
        print(f"---------------{idx+1}/{len(dataset)}----------------")
        print(f"Evaluating question: {q['Question']}")
        print(f"Choices: {q['Choices']}")
        print(f"Solution: {q['Solution']}")
        print(f"Model Answer: {model_answer}")
        results.append({
            "Question": q["Question"],
            "Choices": q["Choices"],
            "ModelAnswer": model_answer,
            "Solution": q["Solution"]
        })
        cost, pt, rt = estimate_cost(token_info)
        total_cost += cost
        total_prompt_tokens += pt
        total_response_tokens += rt
        print(f"Cost request: ${cost:.7f}")
        print(f"Total cost: ${total_cost:.7f}")
        print(f"Total tokens (Prompt: {total_prompt_tokens}, Response: {total_response_tokens})")
        print("--------------------------------")
        # Save intermediate results if save_interval is set and we've reached that interval
        if save_interval and (idx + 1) % save_interval == 0:
            current_time = datetime.datetime.now()
            
            # Calculate current accuracy
            if eval_type and dataset_file:
                accuracy, correct_count, total_count = compute_accuracy(results, eval_type, dataset_file)
                
                # Save intermediate results
                intermediate_dir = os.path.join(os.getcwd(), "benchmarks", "outputs", eval_type, f"{safe_model}_{run_timestamp}", "intermediate")
                if not os.path.exists(intermediate_dir):
                    os.makedirs(intermediate_dir)
                    
                checkpoint_file = os.path.join(intermediate_dir, f"checkpoint_{idx+1}.json")
                with open(checkpoint_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                
                # Save intermediate information
                info_file = os.path.join(intermediate_dir, f"info_{idx+1}.txt")
                with open(info_file, "w") as f:
                    f.write(f"{eval_type} Intermediate Evaluation\n")
                    f.write("=====================\n\n")
                    f.write(f"Model: {model}\n")
                    f.write(f"Dataset: {os.path.basename(dataset_file)}\n")
                    f.write(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Questions Processed: {idx+1}/{len(dataset)}\n")
                    
                    # Display appropriate metrics based on evaluation type
                    if eval_type.lower() == "cti_bench" and 'cti-vsp' in dataset_file:
                        f.write(f"Mean Absolute Deviation: {accuracy:.2f}\n")
                    elif eval_type.lower() == "cti_bench" and 'cti-ate' in dataset_file:
                        f.write(f"F1-macro Score: {accuracy:.2f}\n")
                        f.write(f"Accuracy: {correct_count:.2f}%\n")
                    else:
                        f.write(f"Correct Answers: {correct_count}\n")
                        f.write(f"Accuracy: {accuracy:.2f}%\n")
                        
                    f.write(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Duration so far: {current_time - start_time}\n")
                    
                print(f"Saved intermediate results at question {idx+1}/{len(dataset)}")
                
        if total_cost > 20: 
            print("Cost limit exceeded. Stopping evaluation.")
            break
            
    return results, start_time, total_cost



def parse_result_seceval(result):
    # Expecting format: 'ANSWER: X', 'ANSWER: XY', or 'ANSWER: XYZ' (1, 2, or 3 letters A-D)
    if result is None:
        return None
    match = re.search(r"ANSWER:?\s*([A-D]{1,3})", result, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_result_cybermetric(result):
    # Expecting format: 'ANSWER: X'
    if result is None:
        return None
    match = re.search(r"ANSWER:?\s*([A-D])", result, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_result_cti_bench(result, dataset_file):
    # Accepts answers like 'ANSWER: X', 'ANSWER: XY', or 'ANSWER: XYZ' (A-D), and also 'ANSWER: Txxxx' (MITRE ATT&CK IDs)
    if result is None:
        return None
    # Try to match CWE IDs (e.g., CWE-416, CWE-79, etc.)
    if "cti-rcm" in dataset_file:
        cwe_match = re.search(r"(CWE-\d+)", result, re.IGNORECASE)
        if cwe_match:
            return cwe_match.group(1).upper()
    # Try to match A-D answers (1-3 letters)
    if "cti-mcq" in dataset_file:
        match = re.search(r"ANSWER:?\s*([A-D])", result, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    # Find all MITRE ATT&CK technique IDs (e.g., T1071, T1059, etc.) anywhere in the result
    if "cti-ate" in dataset_file:
        ids = re.findall(r"T\d{4}", result, re.IGNORECASE)
        if ids:
            # Return all found IDs as uppercase, comma-separated
            return ", ".join([x.upper() for x in ids])
    if "cti-vsp" in dataset_file:
        # Try to match CVSS vector strings (e.g., CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)
        cvss_match = re.search(
            r"(CVSS:3\.1/AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH])",
            result,
            re.IGNORECASE,
        )
        if cvss_match:
            return cvss_match.group(1).upper()
        # Also accept vector without prefix
        vector_match = re.search(
            r"(AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH])",
            result,
            re.IGNORECASE,
        )
        if vector_match:
            return "CVSS:3.1/" + vector_match.group(1).upper()
        return result.upper()
    return None


def extract_cvss_score(vector):
    """
    Extracts a score from a CVSS vector string using the CVSS library.
    """
    try:
        from cvss import CVSS3

        c = CVSS3(vector)
        return c.scores()[0]
    except Exception as e:
        print(f"Error calculating CVSS score: {e}")
        return None


def compute_vsp_mad(results):
    """
    Compute Mean Absolute Deviation for CVSS scores, following the original implementation.
    """
    try:
        from cvss import CVSS3
    except ImportError:
        print("CVSS library not found. Please install it with 'pip install cvss'")
        return None

    cvss_prefix = "CVSS:3.1/"  # Use 3.1 to match current data
    error_sum = 0
    total = 0

    for item in results:
        gt = item.get("Solution")
        pred = item.get("ModelAnswer")

        try:
            # Parse prediction
            pred_vector = parse_result_cti_bench(pred, "cti-vsp")

            # Ensure vectors have prefix
            if pred_vector and not pred_vector.startswith("CVSS:"):
                pred_vector = cvss_prefix + pred_vector

            # Calculate scores
            if gt and pred_vector:
                c_gt = CVSS3(gt)
                c_pred = CVSS3(pred_vector)

                gt_score = c_gt.scores()[0]
                pred_score = c_pred.scores()[0]

                error = abs(pred_score - gt_score)
                error_sum += error
                total += 1
        except Exception as e:
            print(f"Error processing CVSS vector: {e}")
            continue

    return error_sum / total if total > 0 else None


def compute_ate_metrics(results):
    """
    Compute F1-macro score and accuracy for CTI-ATE task.

    For F1-macro, we calculate F1 separately for each sample and then average them.

    Args:
        results (list of dict): Each dict should have the ground truth answer and model answer.

    Returns:
        tuple: (f1_macro, accuracy, precision_macro, recall_macro)
    """
    # For storing per-sample metrics
    f1_scores = []
    precision_scores = []
    recall_scores = []

    correct_predictions = 0
    total_predictions = 0

    for item in results:
        gt = item.get("Solution", "")
        pred = item.get("ModelAnswer", "")

        # Extract technique IDs
        gt_ids = [tid.strip().upper() for tid in gt.split(",") if tid.strip()]
        pred_vector = parse_result_cti_bench(pred, "cti-ate")
        pred_ids = [tid.strip().upper() for tid in (pred_vector or "").split(",") if tid.strip()]

        # Calculate true positives, false positives, and false negatives for this sample
        sample_tp = len(set(gt_ids) & set(pred_ids))
        sample_fp = len(set(pred_ids) - set(gt_ids))
        sample_fn = len(set(gt_ids) - set(pred_ids))

        # Calculate precision and recall for this sample
        if sample_tp + sample_fp > 0:
            sample_precision = sample_tp / (sample_tp + sample_fp)
        else:
            sample_precision = 0

        if sample_tp + sample_fn > 0:
            sample_recall = sample_tp / (sample_tp + sample_fn)
        else:
            sample_recall = 0

        # Calculate F1 for this sample
        if sample_precision + sample_recall > 0:
            sample_f1 = 2 * (sample_precision * sample_recall) / (sample_precision + sample_recall)
        else:
            sample_f1 = 0

        # Add to list of scores
        precision_scores.append(sample_precision)
        recall_scores.append(sample_recall)
        f1_scores.append(sample_f1)

        # Calculate exact match for accuracy
        if set(gt_ids) == set(pred_ids):
            correct_predictions += 1
        total_predictions += 1

    # Calculate macro metrics (average of per-sample metrics)
    precision_macro = sum(precision_scores) / len(precision_scores) if precision_scores else 0
    recall_macro = sum(recall_scores) / len(recall_scores) if recall_scores else 0
    f1_macro = sum(f1_scores) / len(f1_scores) if f1_scores else 0
    accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0

    return f1_macro, accuracy, precision_macro, recall_macro


def compute_accuracy(results, benchmark_name, dataset_file=None):
    """
    Compute accuracy for a benchmark result set.

    Args:
        results (list of dict): Each dict should have the ground truth answer and model answer.
        benchmark_name (str): The name of the benchmark.
    Returns:
        accuracy (float): Accuracy as a percentage (0-100).
        correct_count (int): Number of correct answers.
        total_count (int): Total number of evaluated items.
    """
    correct_count = 0
    total_count = 0

    # For VSP, use the mean absolute deviation instead of accuracy
    if benchmark_name.lower() == "cti_bench" and dataset_file and "cti-vsp" in dataset_file:
        mad = compute_vsp_mad(results)
        # Return MAD as the "accuracy" value, with 0 correct count and total items processed
        return mad, 0, len(results)

    # For ATE, calculate F1-macro score and return it with accuracy
    if benchmark_name.lower() == "cti_bench" and dataset_file and "cti-ate" in dataset_file:
        f1_macro, accuracy, precision_macro, recall_macro = compute_ate_metrics(results)
        # We'll return f1_macro as the primary metric, and pass accuracy as correct_count (as a percentage)
        # and total items processed as total_count
        return f1_macro, accuracy * 100, len(results)

    for item in results:
        sol = item.get("Solution")
        pred = item.get("ModelAnswer")
        # For cybermetric, parse both gt and pred using parse_result_cybermetric
        if benchmark_name.lower() == "cybermetric":
            from benchmarks.eval import parse_result_cybermetric

            pred_parsed = parse_result_cybermetric(pred)
            if sol is not None and pred_parsed is not None:
                if sol == pred_parsed:
                    correct_count += 1
                total_count += 1
        elif benchmark_name.lower() == "seceval":
            pred_parsed = parse_result_seceval(pred)
            if sol is not None and pred_parsed is not None:
                if sol == pred_parsed:
                    correct_count += 1
                total_count += 1
        elif (
            benchmark_name.lower() == "cti_bench"
            and "vsp" not in dataset_file
            and "ate" not in dataset_file
        ):
            pred_parsed = parse_result_cti_bench(pred, dataset_file)
            if sol is not None and pred_parsed is not None:
                if sol == pred_parsed:
                    correct_count += 1
                total_count += 1
        else:
            if sol is not None and pred is not None:
                # Accept either exact match or case-insensitive match
                if str(sol).strip().upper() == str(pred).strip().upper():
                    correct_count += 1
                total_count += 1
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0.0
    return accuracy, correct_count, total_count


def save_benchmark_results(
    benchmark_name,
    model,
    dataset_file,
    start_time,
    end_time,
    questions_processed,
    correct_count,
    accuracy,
    total_count,
    result,
    cost
):
    """
    Save benchmark results in CyberMetric-style format to output_dir/information.txt.
    """
    output_dir = os.path.join(os.getcwd(), "benchmarks", "outputs", benchmark_name)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save information file as: <model>_<YYYYMMDD_HHMMSS>.txt
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in str(model)])
    info_file = os.path.join(output_dir, f"{safe_model}_{now_str}.txt")
    duration = end_time - start_time

    # Create a subdirectory for this run, named after info_file (without extension)
    run_dir = os.path.splitext(info_file)[0]
    if not os.path.exists(run_dir):
        os.makedirs(run_dir)

    # Save the info file as .tct inside the run_dir
    info_file = "information.txt"
    info_file_tct = os.path.join(run_dir, os.path.basename(os.path.splitext(info_file)[0] + ".txt"))
    with open(info_file_tct, "w") as f:
        f.write(f"{benchmark_name} Evaluation\n")
        f.write("=====================\n\n")
        f.write(f"Model: {model}\n")
        f.write(f"Dataset: {os.path.basename(dataset_file)}\n")
        f.write(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Questions Processed: {questions_processed}\n")

        # Check if it's a VSP evaluation
        if benchmark_name.lower() == "cti_bench" and "cti-vsp" in dataset_file:
            f.write(f"Mean Absolute Deviation: {accuracy:.2f}\n")
        # Check if it's an ATE evaluation
        elif benchmark_name.lower() == "cti_bench" and "cti-ate" in dataset_file:
            f.write(f"F1-macro Score: {accuracy:.2f}\n")
            f.write(f"Accuracy: {correct_count:.2f}%\n")
        else:
            f.write(f"Correct Answers: {correct_count}\n")
            f.write(f"Accuracy: {accuracy:.2f}%\n")

        f.write(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {duration}\n")
        f.write(f"Cost of evaluation {cost}\n")

    # Save the results as answers.json inside the run_dir
    results_file = os.path.join(run_dir, "answers.json")
    with open(results_file, "w", encoding="utf-8") as rf:
        json.dump(result, rf, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="SecEval Evaluation CLI")
    parser.add_argument("-d", "--dataset_file", type=str, required=True, help="Specify the dataset file to evaluate on.")
    parser.add_argument("-B", "--backend", type=str, required=True, help="Specify the llm type. openai: openai model, ollama: ollama model, openrouter: openrouter model, deepseek: deepseek model")
    parser.add_argument("-m", "--model", type=str, required=True, help="Specify the models.")
    parser.add_argument("-e", "--eval", type=str, required=True, help="Specify the evaluation benchmark.")
    parser.add_argument("-s", "--save_interval", type=int, help="Save intermediate results every X questions.")
    args = parser.parse_args()

    model = args.model

    print(f"Evaluating model: {model}")
    fetch_model_pricing(model)
    print(f"Cost input tokens: {input_cost_per_token}")
    print(f"Cost output tokens: {output_cost_per_token}")
    if args.backend:
        backend_upper = args.backend.upper()
        api_base = os.environ.get(f"{backend_upper}_API_BASE")
        custom_llm_provider = args.backend
        api_key=""
        if args.backend!='ollama':
            api_key = os.environ.get(f"{backend_upper}_API_KEY").strip()
            if api_key is None:
                raise RuntimeError(f"API_BASE or API_KEY not found for backend {args.backend}")
        if args.backend=='alias':
            api_base = "https://api.aliasrobotics.com:666/"
            custom_llm_provider="openai"
    else:
        raise RuntimeError("Unknown backend")

    if args.eval == "seceval":
        instruction = """Below are multiple-choice questions concerning cybersecurity. 
        Please select the correct answers and respond with the correct letters A, B, C, or D.
        You could select more than one letter
        Always return in this format: 'ANSWER: XYZ' or 'ANSWER: X'.
        """
        if args.dataset_file == "":
            args.dataset_file = "benchmarks/utils/seceval_dataset/questions-2.json"
        dataset = load_dataset(args.dataset_file, "seceval")
    elif args.eval == "cybermetric":
        instruction = """Choose the correct answer (A, B, C, or D) only. 
        Always return in this format: 'ANSWER: X'.
        """
        if args.dataset_file == "":
            args.dataset_file = "benchmarks/utils/cybermetric_dataset/CyberMetric-2-v1.json"
        dataset = load_dataset(args.dataset_file, "cybermetric")
        dataset = dataset[:4500]
    elif args.eval == "cyberpii-bench":
        # For PII anonymization benchmark
        if args.dataset_file == "":
            args.dataset_file = "benchmarks/cyberPII-bench/memory01_gold.csv"

        # Optional: specify entities to skip in evaluation (if needed)
        skip_entities = []  # You can add entities to skip like ['EMAIL_ADDRESS', 'PHONE_NUMBER']

        # Run PII evaluation with specialized function - it handles everything internally
        run_evaluation_pii(
            model,
            api_base,
            api_key,
            custom_llm_provider,
            args.dataset_file,
            skip_entities=skip_entities
        )
        return  # Exit after PII evaluation, no accuracy metrics or benchmark results needed

    elif args.eval == "cti_bench":
        if args.dataset_file == "":
            args.dataset_file = "benchmarks/utils/cti_bench_dataset/cti-mcq1.tsv"
        if "ate" in args.dataset_file:
            instruction = """
            Return your answer in the MITRE ATT&CK technique ID format.
            You could select more than one technique ID. Be brief and concise.
            Return your answer in this format: 'ANSWER: TXXXX' or 'ANSWER: TXXXX, TXXXX, TXXXX'
            Remember they are just an example, the important is the format."""
        elif "rcm" in args.dataset_file:
            instruction = """ #CWE
           Return CWE ID.
           Return your answer in this format: 'ANSWER: CWE-XXXX' (X are numbers)."""
        elif "mcq" in args.dataset_file:
            instruction = """
            Select the correct answer (A, B, C, or D) only.
            Return your answer in this format: 'ANSWER: A'"""
        elif "vsp" in args.dataset_file:
            instruction = """
            Return your answer in this CVSS format: 'ANSWER: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'"""
        dataset = load_dataset(args.dataset_file, "cti_bench")

    start_time = datetime.datetime.now()
    # Pass save_interval and eval args to run_evaluation
    result, eval_start_time, cost = run_evaluation(
        dataset,
        instruction,
        model,
        api_base,
        api_key,
        custom_llm_provider,
        args.save_interval,
        args.eval,
        args.dataset_file
    )
    end_time = datetime.datetime.now()

    accuracy, correct_count, total_count = compute_accuracy(
        result, args.eval, dataset_file=args.dataset_file
    )

    if args.eval.lower() == "cti_bench" and "cti-vsp" in args.dataset_file:
        print(f"Mean Absolute Deviation: {accuracy:.2f}")
    elif args.eval.lower() == "cti_bench" and "cti-ate" in args.dataset_file:
        print(f"F1-macro Score: {accuracy:.2f}")
        print(f"Accuracy: {correct_count:.2f}%")
    else:
        print(f"Accuracy: {accuracy:.2f}% ({correct_count}/{total_count})")

    save_benchmark_results(args.eval, model, args.dataset_file, eval_start_time, end_time, len(dataset), correct_count, accuracy, total_count, result, cost)

if __name__ == "__main__":
    main()
