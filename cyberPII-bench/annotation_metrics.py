"""
Annotation Evaluation Script

This script processes entity-tagged text data from multiple annotators and computes performance metrics 
(precision, recall, F1, F2) by comparing them to ground truth annotations. It supports multiple annotation 
formats (BIO, span labels) and handles reports generation including mistakes analysis, per-entity type 
breakdowns, and overall statistics.

Main Features:
- Entity extraction and normalization
- Label generation (BIO, span)
- Per-annotator comparison and evaluation
- Metrics computation (precision, recall, F1, F2)
- Report generation in structured text format

The input csv file should have the following columns:
- id: the id of the row
- target_text: the text to be annotated
- target_text_{annotator}_sanitized: the text annotated by the annotator

Arguments:
    --input_csv_path (str): Path to the CSV file containing annotations. The file should include columns identifying the text, entities, and annotator.
    --annotator (str): Name of the annotator whose annotations are to be evaluated.
    --skip_entities (List[str], optional): List of entity types to skip during evaluation (e.g., EMAIL_ADDRESS, PHONE_NUMBER).

Example usage:
    python evaluate_annotations.py --input_csv_path path/to/file.csv --annotator alias0 --skip_entities EMAIL_ADDRESS PHONE_NUMBER


"""
import pandas as pd
import re
import os
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from datetime import datetime
import argparse

# Define valid entity types
VALID_ENTITIES = {
    'PERSON', 'PHONE_NUMBER', 'LOCATION', 'CREDIT_CARD', 'CRYPTO', 'IBAN_CODE',
    'IP_ADDRESS', 'EMAIL_ADDRESS', 'URL', 'DATE_TIME', 'NIF', 'MEDICAL_LICENSE',
    'US_SSN', 'US_BANK_NUMBER', 'US_DRIVER_LICENSE', 'US_ITIN', 'US_PASSPORT',
    'ORGANIZATION', 'ADDRESS', 'NRP', 'DNI', 'NIE', 'IBAN', 'EUROPEAN_BANK_ACCOUNT'
}

# ============ DATA NORMALIZATION FUNCTIONS ============

def find_entities_with_positions(text: str, skip_entities: Set[str] = set()) -> List[Tuple[str, int, int, str]]:
    """
    Find entities marked with brackets and their positions in the text.
    Returns: List of (entity_type, start_pos, end_pos, full_tag)
    """
    if not isinstance(text, str) or pd.isna(text):
        return []
    
    entities = []
    valid_entities = VALID_ENTITIES - skip_entities
    pattern = r'\[({})\]'.format('|'.join(valid_entities))
    
    for match in re.finditer(pattern, text):
        entity_type = match.group(1)
        if entity_type not in skip_entities:  
            start = match.start()
            end = match.end()
            full_tag = match.group(0)
            entities.append((entity_type, start, end, full_tag))
    
    return sorted(entities, key=lambda x: x[1])

def generate_span_labels(text: str, entities: List[Tuple[str, int, int, str]]) -> str:
    """
    Generate span labels in format: start:end:entity_type|start:end:entity_type
    """
    if not isinstance(text, str) or pd.isna(text) or not entities:
        return ""
    
    spans = []
    for entity_type, start, end, _ in entities:
        spans.append(f"{start}:{end}:{entity_type}")
    
    return "|".join(spans)

def generate_bio_labels(text: str, entities: List[Tuple[str, int, int, str]]) -> str:
    """
    Generate BIO labels for each character in the text
    """
    if not isinstance(text, str) or pd.isna(text):
        return ""
    
    # Initialize all positions as O (Outside)
    bio_labels = ['O'] * len(text)
    
    # Mark entity positions
    for entity_type, start, end, _ in entities:
        # Mark B (Beginning)
        if start < len(bio_labels):
            bio_labels[start] = f"B-{entity_type}"
        
        # Mark I (Inside) for the rest of the entity
        for i in range(start + 1, end):
            if i < len(bio_labels):
                bio_labels[i] = f"I-{entity_type}"
    
    return "".join(bio_labels)

def normalize_annotations(df: pd.DataFrame, annotator_config: Dict[str, Dict[str, str]], skip_entities: Set[str] = set()) -> pd.DataFrame:
    """
    Normalize annotations for ground truth and all annotators.
    """
    # First normalize ground truth
    ground_truth_entities = df['target_text'].apply(lambda x: find_entities_with_positions(x, skip_entities))
    df['span_labels'] = df.apply(lambda row: generate_span_labels(row['target_text'], ground_truth_entities[row.name]), axis=1)
    df['mbert_bio_labels'] = df.apply(lambda row: generate_bio_labels(row['target_text'], ground_truth_entities[row.name]), axis=1)
    
    # Then normalize each annotator's data
    for annotator, config in annotator_config.items():
        target_col = config['target_text']
        if target_col not in df.columns:
            print(f"Warning: Column {target_col} not found for annotator {annotator}")
            continue
            
        # Fill NaN values with empty string to avoid errors
        df[target_col] = df[target_col].fillna("")
            
        # Generate entities and labels
        annotator_entities = df[target_col].apply(lambda x: find_entities_with_positions(x, skip_entities))
        df[f'span_labels_{annotator}'] = df.apply(
            lambda row: generate_span_labels(row[target_col], annotator_entities[row.name]), 
            axis=1
        )
        df[f'mbert_bio_labels_{annotator}'] = df.apply(
            lambda row: generate_bio_labels(row[target_col], annotator_entities[row.name]),
            axis=1
        )
    
    return df

# ============ METRICS CALCULATION FUNCTIONS ============

def calculate_metrics(df: pd.DataFrame, annotator_config: Dict[str, Dict[str, str]], skip_entities: Set[str] = set()) -> Dict:
    """
    Calculate metrics comparing ground truth with annotators
    """
    stats = {
        'total_rows': len(df),
        'entity_counts': defaultdict(lambda: defaultdict(int)),
        'metrics_per_annotator': defaultdict(dict),
        'metrics_per_entity_type': defaultdict(lambda: defaultdict(dict)),
        'mistakes': defaultdict(list)
    }
    
    # First calculate ground truth entities once for all annotators
    all_true_entities = []
    for idx, row in df.iterrows():
        ground_truth = find_entities_with_positions(row['target_text'], skip_entities)
        # Store entities with row index for exact matching
        for entity in ground_truth:
            all_true_entities.append((idx, entity[0], entity[1], entity[2]))
            stats['entity_counts']['ground_truth'][entity[0]] += 1
    
    true_set = set(all_true_entities)
    total_ground_truth = len(true_set)
    
    # Process each annotator
    for annotator, config in annotator_config.items():
        target_col = config['target_text']
        if target_col not in df.columns:
            print(f"Warning: Column {target_col} not found in the dataset")
            continue
        
        # Collect predicted entities
        all_pred_entities = []
        
        # Process each row
        for idx, row in df.iterrows():
            pred_entities = find_entities_with_positions(row[target_col], skip_entities)
            
            # Store entities with row index for exact matching
            for entity in pred_entities:
                all_pred_entities.append((idx, entity[0], entity[1], entity[2]))
                stats['entity_counts'][annotator][entity[0]] += 1
            
            # Record mistakes
            ground_truth = [e for e in all_true_entities if e[0] == idx]
            gt_set = {(e[1], e[2], e[3]) for e in ground_truth}
            pred_set = {(e[0], e[1], e[2]) for e in pred_entities}
            
            if gt_set != pred_set:
                false_positives = list(pred_set - gt_set)
                false_negatives = list(gt_set - pred_set)
                
                if false_positives or false_negatives:
                    stats['mistakes'][annotator].append({
                        'id': row.get('id', idx),
                        'text': row['target_text'],
                        'annotated_text': row[target_col],
                        'ground_truth': list(gt_set),
                        'prediction': list(pred_set),
                        'false_positives': false_positives,
                        'false_negatives': false_negatives
                    })
        
        # Calculate overall metrics
        pred_set = set(all_pred_entities)
        
        tp = len(true_set & pred_set)
        fp = len(pred_set - true_set)
        fn = len(true_set - pred_set)
        
        precision = tp / len(pred_set) if pred_set else 0
        recall = tp / len(true_set) if true_set else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        f2 = 5 * (precision * recall) / (4 * precision + recall) if (precision + recall) > 0 else 0
        
        stats['metrics_per_annotator'][annotator] = {
            'true_positives': tp,
            'false_positives': fp,
            'false_negatives': fn,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'f2_score': f2,
            'total_entities': total_ground_truth  # Use the same ground truth count for all annotators
        }
        
        # Calculate per-entity type metrics
        for entity_type in VALID_ENTITIES - skip_entities:  # Only evaluate non-skipped entities
            true_type = {e for e in true_set if e[1] == entity_type}
            pred_type = {e for e in pred_set if e[1] == entity_type}
            
            if not true_type and not pred_type:
                continue
            
            tp_type = len(true_type & pred_type)
            fp_type = len(pred_type - true_type)
            fn_type = len(true_type - pred_type)
            
            precision_type = tp_type / len(pred_type) if pred_type else 0
            recall_type = tp_type / len(true_type) if true_type else 0
            f1_type = 2 * (precision_type * recall_type) / (precision_type + recall_type) if (precision_type + recall_type) > 0 else 0
            f2_type = 5 * (precision_type * recall_type) / (4 * precision_type + recall_type) if (precision_type + recall_type) > 0 else 0
            
            if tp_type > 0 or fp_type > 0 or fn_type > 0:
                stats['metrics_per_entity_type'][annotator][entity_type] = {
                    'true_positives': tp_type,
                    'false_positives': fp_type,
                    'false_negatives': fn_type,
                    'precision': precision_type,
                    'recall': recall_type,
                    'f1_score': f1_type,
                    'f2_score': f2_type,
                    'total_entities': len(true_type)
                }
    
    return stats

# ============ REPORT GENERATION FUNCTIONS ============

def generate_overall_report(stats: Dict, output_dir: str, input_file: str, annotator_config: Dict[str, Dict[str, str]], skip_entities: Set[str] = set()):
    """Generate overall statistics report"""
    with open(os.path.join(output_dir, 'overall_report.txt'), 'w') as f:
        f.write("=== Overall Annotation Statistics ===\n\n")
        
        # Add input file information
        f.write(f"Input File: {input_file}\n")
        
        # Add information about skipped entities
        if skip_entities:
            f.write(f"\nExcluded Entity Types: {', '.join(sorted(skip_entities))}\n")
        
        # Add annotator configuration information
        f.write("\nAnnotator Configurations:\n")
        for annotator, config in annotator_config.items():
            f.write(f"\n{annotator}:\n")
            for key, value in config.items():
                f.write(f"  {key}: {value}\n")
        f.write("\n" + "=" * 50 + "\n\n")
        
        f.write(f"Total rows analyzed: {stats['total_rows']}\n\n")
        
        f.write("Ground Truth Entity Counts:\n")
        for entity_type, count in sorted(stats['entity_counts']['ground_truth'].items()):
            f.write(f"[{entity_type}]: {count}\n")
        
        f.write("\nAnnotator Entity Counts:\n")
        for annotator in stats['entity_counts']:
            if annotator != 'ground_truth':
                f.write(f"\n{annotator}:\n")
                for entity_type, count in sorted(stats['entity_counts'][annotator].items()):
                    f.write(f"[{entity_type}]: {count}\n")

def generate_entity_report(stats: Dict, output_dir: str, annotator_names: List[str], skip_entities: Set[str] = set()):
    """Generate per-entity type performance report"""
    with open(os.path.join(output_dir, 'entity_performance.txt'), 'w') as f:
        f.write("=== Entity Type Performance by Annotator ===\n\n")
        
        # Add information about skipped entities
        if skip_entities:
            f.write(f"Note: The following entity types were excluded from evaluation:\n")
            f.write(f"{', '.join(sorted(skip_entities))}\n\n")
            f.write("=" * 50 + "\n\n")
        
        for annotator in annotator_names:
            if annotator in stats['metrics_per_entity_type']:
                f.write(f"\n{annotator.upper()}:\n")
                for entity_type in sorted(VALID_ENTITIES - skip_entities):
                    if entity_type in stats['metrics_per_entity_type'][annotator]:
                        metrics = stats['metrics_per_entity_type'][annotator][entity_type]
                        f.write(f"\n  {entity_type}:\n")
                        f.write(f"    Precision: {metrics['precision']:.4f}\n")
                        f.write(f"    Recall: {metrics['recall']:.4f}\n")
                        f.write(f"    F1 Score: {metrics['f1_score']:.4f}\n")
                        f.write(f"    F2 Score: {metrics['f2_score']:.4f}\n")
                        f.write(f"    True Positives: {metrics['true_positives']}\n")
                        f.write(f"    False Positives: {metrics['false_positives']}\n")
                        f.write(f"    False Negatives: {metrics['false_negatives']}\n")

def generate_mistakes_report(stats: Dict, output_dir: str, annotator_names: List[str], skip_entities: Set[str] = set()):
    """Generate detailed mistakes report"""
    with open(os.path.join(output_dir, 'mistakes.txt'), 'w') as f:
        f.write("=== Detailed Mistakes Analysis ===\n\n")
        
        # Add information about skipped entities
        if skip_entities:
            f.write(f"Note: The following entity types were excluded from evaluation:\n")
            f.write(f"{', '.join(sorted(skip_entities))}\n\n")
            f.write("=" * 50 + "\n\n")
        
        for annotator in annotator_names:
            if annotator in stats['mistakes'] and stats['mistakes'][annotator]:
                f.write(f"\n{annotator.upper()} Mistakes ({len(stats['mistakes'][annotator])} total):\n")
                for mistake in stats['mistakes'][annotator]:
                    f.write(f"\nExample {mistake['id']}:\n")
                    f.write(f"Original text: {mistake['text']}\n")
                    f.write(f"Annotated text: {mistake['annotated_text']}\n")
                    
                    if mistake['false_negatives']:
                        f.write("\nMissed entities (should have been anonymized):\n")
                        for entity_type, start, end in mistake['false_negatives']:
                            f.write(f"- {entity_type} at position {start}-{end}\n")
                    
                    if mistake['false_positives']:
                        f.write("\nIncorrect anonymizations:\n")
                        for entity_type, start, end in mistake['false_positives']:
                            f.write(f"- {entity_type} at position {start}-{end}\n")
                    
                    f.write("-" * 80 + "\n")
            else:
                f.write(f"\n{annotator.upper()}: No mistakes found\n")

def generate_metrics_report(stats: Dict, output_dir: str, annotator_names: List[str], skip_entities: Set[str] = set()):
    """Generate overall metrics report"""
    with open(os.path.join(output_dir, 'metrics.txt'), 'w') as f:
        f.write("=== Overall Metrics by Annotator ===\n\n")
        
        # Add information about skipped entities
        if skip_entities:
            f.write(f"Note: The following entity types were excluded from evaluation:\n")
            f.write(f"{', '.join(sorted(skip_entities))}\n\n")
            f.write("=" * 50 + "\n\n")
        
        for annotator in annotator_names:
            if annotator in stats['metrics_per_annotator']:
                metrics = stats['metrics_per_annotator'][annotator]
                f.write(f"\n{annotator.upper()}:\n")
                f.write(f"  Total Entities in Ground Truth: {metrics['total_entities']}\n")
                f.write(f"  True Positives: {metrics['true_positives']}\n")
                f.write(f"  False Positives: {metrics['false_positives']}\n")
                f.write(f"  False Negatives: {metrics['false_negatives']}\n")
                f.write(f"  Precision: {metrics['precision']:.4f}\n")
                f.write(f"  Recall: {metrics['recall']:.4f}\n")
                f.write(f"  F1 Score: {metrics['f1_score']:.4f}\n")
                f.write(f"  F2 Score: {metrics['f2_score']:.4f}\n")

def get_output_dir(base_dir: str) -> str:
    """Create and return the output directory name with date and sequence number in the same directory as the input file"""
    # Get the directory of the input file
    
    base_name = f"output_metrics_{datetime.now().strftime('%Y%m%d')}"
    counter = 1
    while True:
        dir_name = os.path.join(base_dir, f"{base_name}_{counter}")
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            return dir_name
        counter += 1

# ============ MAIN EXECUTION ============

def main():
    parser = argparse.ArgumentParser(description="Annotator Evaluation Script")
    parser.add_argument('--input_csv_path', type=str, required=True, help='Path to input CSV file')
    parser.add_argument('--annotator', type=str, required=True, help='Annotator used to generate the input CSV file, options: alias0, privateAI')
    parser.add_argument('--skip_entities', type=str, nargs='+', default=[], help='List of entity types to skip in evaluation')
    args = parser.parse_args()

    # Convert skip_entities to a set for faster lookups
    skip_entities = set(args.skip_entities)
    
    # Validate skip_entities
    invalid_entities = skip_entities - VALID_ENTITIES
    if invalid_entities:
        raise ValueError(f"Invalid entities to skip: {invalid_entities}. Valid entities are: {VALID_ENTITIES}")

    df = pd.read_csv(args.input_csv_path, sep=";")

    ANNOTATOR_CONFIG = {
            args.annotator: {
                'target_text': f'target_text_{args.annotator}_sanitized',
                'span_labels': f'span_labels_{args.annotator}_sanitized',
                'mbert_bio_labels': f'mbert_bio_labels_{args.annotator}_sanitized'
        }
    }
  
 
    print("Normalizing annotations...")
    df = normalize_annotations(df, ANNOTATOR_CONFIG, skip_entities)
        
    print("Calculating metrics...")
    stats = calculate_metrics(df, ANNOTATOR_CONFIG, skip_entities)
        
    # Determine output directory
    base_dir = os.path.dirname(os.path.abspath(args.input_csv_path))
    dir_annotator = os.path.join(base_dir, args.annotator)
    print(dir_annotator)
    output_dir = get_output_dir(dir_annotator)
    print(output_dir)

    print("Generating reports...")
    generate_overall_report(stats, output_dir, args.input_csv_path, ANNOTATOR_CONFIG, skip_entities)
    generate_entity_report(stats, output_dir, list(ANNOTATOR_CONFIG.keys()), skip_entities)
    generate_mistakes_report(stats, output_dir, list(ANNOTATOR_CONFIG.keys()), skip_entities)
    generate_metrics_report(stats, output_dir, list(ANNOTATOR_CONFIG.keys()), skip_entities)
        
    print(f"\nAnalysis complete. Reports have been generated in {output_dir}/")
    if skip_entities:
        print(f"Note: The following entities were excluded from evaluation: {', '.join(sorted(skip_entities))}")


if __name__ == "__main__":
    main()