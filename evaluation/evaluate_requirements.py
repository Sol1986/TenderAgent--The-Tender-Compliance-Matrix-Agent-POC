import json
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv(override=True)


# --------------------------------------------------
# Load data
# --------------------------------------------------

with Path("evaluation/fixtures/gold_requirements.json").open(
    encoding="utf-8"
) as f:
    gold = json.load(f)["requirements"]

with Path("evaluation/fixtures/output_3_requirements.json").open(
    encoding="utf-8"
) as f:
    predictions = json.load(f)["requirements"]


print(f"Gold requirements: {len(gold)}")
print(f"Predicted requirements: {len(predictions)}")


# --------------------------------------------------
# Structured evaluator output
# --------------------------------------------------

class RequirementMatch(BaseModel):
    gold_id: str

    matched: bool

    predicted_requirement_ids: list[str] = Field(
        default_factory=list
    )

    reason: str


class EvaluationResult(BaseModel):
    matches: list[RequirementMatch]


# --------------------------------------------------
# Judge
# --------------------------------------------------

judge = ChatOpenAI(
    model="gpt-5.6-sol"
).with_structured_output(EvaluationResult)


# --------------------------------------------------
# Evaluation prompt
# --------------------------------------------------

prompt = f"""
You are evaluating an AI tender compliance extraction system.

You are given:

1. GOLD REQUIREMENTS
These are expert-verified requirements from the source tender.

2. PREDICTED REQUIREMENTS
These were produced by the AI system from the same tender.

Your task is to determine whether each GOLD requirement is represented
by the predicted requirements.

MATCHING RULES:

A predicted requirement matches a gold requirement when it preserves
the material meaning of the obligation.

Consider:

- actor
- required action
- material condition
- timing
- threshold or amount
- required document or form
- submission condition

Exact wording is NOT required.

A single predicted requirement may cover multiple gold requirements
ONLY when it explicitly preserves each distinct obligation.

Multiple predicted requirements may collectively support one gold
requirement when necessary.

Do NOT count a prediction as a match merely because it discusses the
same topic.

For example:

Gold:
"Bidder must maintain $5,000,000 CGL insurance."

Prediction:
"Bidder must maintain required insurance."

This is NOT a full match because the material $5,000,000 threshold
was lost.

Be conservative about declaring a match.

For EVERY gold requirement return:

- gold_id
- matched true/false
- predicted_requirement_ids supporting the match
- a short reason

GOLD REQUIREMENTS:

{json.dumps(gold, indent=2)}

PREDICTED REQUIREMENTS:

{json.dumps(predictions, indent=2)}
"""


# --------------------------------------------------
# Run semantic matching
# --------------------------------------------------

result = judge.invoke(prompt)


# --------------------------------------------------
# Calculate recall deterministically
# --------------------------------------------------

matched = [m for m in result.matches if m.matched]
missed = [m for m in result.matches if not m.matched]

recall = len(matched) / len(gold) if gold else 0


print("\n==============================")
print("REQUIREMENT RECALL")
print("==============================")

print(f"Gold requirements: {len(gold)}")
print(f"Matched: {len(matched)}")
print(f"Missed: {len(missed)}")
print(f"Recall: {recall:.2%}")


print("\nMISSED REQUIREMENTS:")

for item in missed:
    print(f"\n{item.gold_id}")
    print(item.reason)


# --------------------------------------------------
# Save detailed results
# --------------------------------------------------

evaluation = {
    "gold_count": len(gold),
    "prediction_count": len(predictions),
    "matched_count": len(matched),
    "missed_count": len(missed),
    "recall": recall,
    "matches": [m.model_dump() for m in result.matches],
}

output_path = Path("evaluation/fixtures/output_3_evaluation.json")

with output_path.open("w", encoding="utf-8") as f:
    json.dump(
        evaluation,
        f,
        indent=2,
        ensure_ascii=False,
    )

print(f"\nSaved evaluation to: {output_path}")