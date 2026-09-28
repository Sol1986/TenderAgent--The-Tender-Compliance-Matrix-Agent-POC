from langsmith import Client
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(override=True)

client = Client()

DATASET_NAME = "Tender Compliance Golden Dataset"

# Find our dataset
datasets = list(client.list_datasets(dataset_name=DATASET_NAME))

if not datasets:
    raise ValueError(f"Dataset not found: {DATASET_NAME}")

dataset = datasets[0]

print("Dataset:", dataset.name)
print("Dataset ID:", dataset.id)

# Get the single example we created
examples = list(client.list_examples(dataset_id=dataset.id))

print("Number of examples:", len(examples))

example = examples[0]

print("Input:", example.inputs)

gold_requirements = example.outputs["requirements"]

print("Number of gold requirements:", len(gold_requirements))

print("\nFirst gold requirement:")
print(gold_requirements[0])

# Save locally
output_path = Path("evaluation/fixtures/gold_requirements.json")
output_path.parent.mkdir(exist_ok=True)

with output_path.open("w", encoding="utf-8") as f:
    json.dump(
        {"requirements": gold_requirements},
        f,
        indent=2,
        ensure_ascii=False,
    )

print(f"\nSaved gold requirements to: {output_path}")