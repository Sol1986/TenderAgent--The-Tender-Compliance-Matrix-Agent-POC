from langsmith import Client
from dotenv import load_dotenv
load_dotenv(override=True)
import json
from pathlib import Path


client = Client()

RUN_ID = "01a0e3ea-b43f-7183-a268-d7f30f0db871"

run = client.read_run(RUN_ID)

print("Run name:", run.name)
print("Output keys:", run.outputs.keys() if run.outputs else None)

requirements = run.outputs["reconciled_requirements"]

print("Number of requirements:", len(requirements))
print("\nFirst requirement:")
print(requirements[0])



output_path = Path("eval_fixtures/output_3_requirements.json")
output_path.parent.mkdir(exist_ok=True)

with output_path.open("w", encoding="utf-8") as f:
    json.dump(
        {"requirements": requirements},
        f,
        indent=2,
        ensure_ascii=False,
    )

print(f"\nSaved predictions to: {output_path}")