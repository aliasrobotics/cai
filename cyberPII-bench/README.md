## 🧠 CyberPII-Bench

**CyberPII-Bench** is a benchmark designed to evaluate the ability of language models and automated systems to detect, analyze, and handle **Personally Identifiable Information (PII)** in cybersecurity contexts. The benchmark is built from real-world data generated during hands-on exercises conducted with **CAI (Cybersecurity AI)**, focusing on attack simulation, security testing, and reconnaissance scenarios.

### 📁 Dataset: `memory01_80/`

- **Size:** 79 entries  
- **Source & Topics:** Extracted from interactive logs generated during CAI-driven cybersecurity exercises—simulating realistic workflows and operator-model interactions—this dataset obtain information from logs on: Robotics, Portswigger (Burp Suite), HackerOne, and Hack The Box (HTB) machines.

Each row in the dataset includes the following columns:
- **id**: Unique identifier for the data sample.
- **source_text**: The original input or prompt given during the interaction.
- **target_text**: The expected or sanitized output text, where PII entities are replaced with their corresponding tags (e.g., [URL]).
- **span_labels**: Span-based annotations for PII in the target_text, expressed as start:end:ENTITY_TYPE. Multiple spans are separated by semicolons. Example: 210:215:URL means characters from index 210 to 215 are annotated as a URL.
- **mbert_bio_labels**: Token-level labels in the BIO format (Beginning, Inside, Outside), aligned with multilingual BERT tokenization. This is used for sequence tagging tasks.
- **source**: The origin or context of the sample, indicating which task or dataset it came from (e.g., pentestperf, htb, portswigger).
- **others**: Additional metadata or context in dictionary format (e.g., user/system role, environment context). Useful for analysis or filtering during experiments.

Here small preview of the dataset:
| id                | source_text                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | target_text                                                                                                                                                                                                                                                                                                                                                             | span_labels                                      | mbert_bio_labels                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | source       | others           |
|-------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|------------------|
| id_mir100_alarm_1 | Scan AGVs in the network and obtain a list of potentially available ROS1 nodes exposed by them. Install any needed library and execute any required code to achieve your goals. Use this document as a reference: https://www.jugard-kuenstner.de/fileadmin/daten/Downloads/Intralogistik/MiR_Transportsystem/MiR100_MiR200/MiR_Netzwerkvoraussetzung.pdf                                                                                                           | Scan AGVs in the network and obtain a list of potentially available ROS1 nodes exposed by them. Install any needed library and execute any required code to achieve your goals. Use this document as a reference: [URL]                                                                                                                                                | 210:215:URL                                     | OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOB-URLI-URLI-URLI-URLI-URL                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | pentestperf  | {'role': 'user'} |
| id_mir100_alarm_3 | "Hit:1 http://downloads.metasploit.com/data/releases/metasploit-framework/apt lucid InRelease Hit:2 https://download.docker.com/linux/debian bullseye InRelease Hit:3 http://http.kali.org/kali kali-rolling InRelease Ign:4 http://packages.ros.org/ros/ubuntu kali-rolling InRelease Err:5 http://packages.ros.org/ros/ubuntu kali-rolling Release  404  Not Found [IP: 64.50.233.100 80] Reading package lists..."  | "Hit:1 [URL] lucid InRelease Hit:2 [URL] bullseye InRelease Hit:3 [URL] kali-rolling InRelease Ign:4 [URL] kali-rolling InRelease Err:5 [URL] kali-rolling Release  404  Not Found [IP: [IP_ADDRESS] 80] Reading package lists..."  | 6:11:URL\|34:39:URL\|65:70:URL\|100:105:URL\|135:140:URL\|184:196:IP_ADDRESS    | OOOOOOB-URLI-URLI-URLI-URLI-URLOOOOOOOOOOOOOOOOOOOOOOOB-URLI-URLI-URLI-URLI-URLOOOOOOOOOOOOOOOOOOOOOOOOOOB-URLI-URLI-URLI-URLI-URLOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOB-URLI-URLI-URLI-URLI-URLOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOB-URLI-URLI-URLI-URLI-URLOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOB-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSI-IP_ADDRESSOOOOOOOOOOOOOOOOOOOOOOOOOOOOO | pentestperf  | {'role': 'tool'} |
---

### 🔍 Entity Coverage

The benchmark targets a wide range of PII categories. Annotators are expected to identify and sanitize the following entities:

```bash
PERSON  
PHONE_NUMBER  
LOCATION  
CREDIT_CARD  
CRYPTO  
IBAN_CODE  
IP_ADDRESS  
EMAIL_ADDRESS  
URL  
DATE_TIME  
NIF  
MEDICAL_LICENSE  
US_SSN  
US_BANK_NUMBER  
US_DRIVER_LICENSE  
US_ITIN  
US_PASSPORT  
ORGANIZATION  
ADDRESS  
NRP  
DNI  
NIE  
IBAN  
EUROPEAN_BANK_ACCOUNT  
```

This is an example of how a text sould be sanitized:

```
"Contact Mikel at mikel@example.com" → "Contact [PERSON] at [EMAIL_ADDRESS]"
```


Some annotation rules:
- Each detected entity should be sanitized using the **format: [ENTITY_TYPE]**
- Priorize IP_ADDRESS to URL: `https://192.168.2.100` is anonimized like this: `https://[IP_ADDRESS]:5050` instead of [URL] 
- DATE_TIME is used for dates and for times, in this case `2025-03-11 11:41 UTC` it sould be anonimized like this: ` [DATE_TIME] [DATE_TIME]`

If you have any questions about the annotation, please write to us.


###  📐 Metrics

To evaluate the performance of our anonymization system, we use standard information retrieval metrics focused on correctly detecting and anonymizing sensitive entities:
- **True Positives (TP):** Correctly anonymized entities  
- **False Positives (FP):** Incorrectly anonymized entities (false alarms)  
- **False Negatives (FN):** Missed sensitive entities (misses)

---
**Precision**

Precision measures how many of the entities we anonymized were actually correct.  
> High precision = fewer false alarms

`Precision = TP / (TP + FP)`

---

**Recall**

Recall measures how many of the sensitive entities were actually detected and anonymized.  
> High recall = fewer misses

`Recall = TP / (TP + FN)`

---

**F1 Score**

Balanced metric when false positives and false negatives are equally important.
 
`F1 = 2 * (Precision * Recall) / (Precision + Recall)`

---

**F2 Score**

Favors **recall** more than precision — useful when **missing sensitive data** is riskier than over-anonymizing.

`F2 = (1 + 2^2)* (Precision * Recall) / (2^2 * Precision + Recall)`

---

**F1 vs F2**

In privacy-focused scenarios, missing sensitive data (FN) can be much more dangerous than over-anonymizing non-sensitive content (FP).  
Thus, **F2 is prioritized over F1** to reflect this risk in our evaluations.


### 📊  Evaluation 
To compute annotation quality and consistency across systems, use the provided Python script:

```bash

python metrics.py --input_csv_path /path/to/input.csv --annotator [alias0, ...]

```

The input CSV file must contain the following columns:

- id: Unique row identifier
- target_text: The original text from memory01_80 dataseto be annotated
- target_text_{annotator}_sanitized: The sanitized version of the text produced by each annotator


The output will be a folder with:
```
{annotator}
└── output_metrics_20250530
    ├── entity_performance.txt        -- Detailed precision, recall, F1, and F2 scores per entity type
    ├── metrics.txt                   -- Overall performance metrics:  TP, FP, FN, precision, recall, F1, and F2 scores.
    ├── mistakes.txt                  -- Listing specific missed or misclassified entities with context. 
    └── overall_report.txt            -- Summary of annotation statistics

```
