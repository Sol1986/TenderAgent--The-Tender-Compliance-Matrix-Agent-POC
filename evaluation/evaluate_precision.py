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
    gold_data = json.load(f)

with Path("evaluation/fixtures/output_3_requirements.json").open(
    encoding="utf-8"
) as f:
    prediction_data = json.load(f)


gold = gold_data["requirements"]
negative_controls = gold_data.get("negative_controls", [])
predictions = prediction_data["requirements"]


print(f"Gold requirements: {len(gold)}")
print(f"Negative controls: {len(negative_controls)}")
print(f"Predicted requirements: {len(predictions)}")


# --------------------------------------------------
# Structured evaluator output
# --------------------------------------------------

class PredictionAssessment(BaseModel):
    prediction_id: str

    supported: bool

    gold_ids: list[str] = Field(
        default_factory=list
    )

    duplicate: bool = False

    duplicate_of: list[str] = Field(
        default_factory=list
    )

    negative_control_ids: list[str] = Field(
        default_factory=list
    )

    reason: str


class PrecisionEvaluation(BaseModel):
    assessments: list[PredictionAssessment]


# --------------------------------------------------
# Judge
# --------------------------------------------------

judge = ChatOpenAI(
    model="gpt-5.6-sol"
).with_structured_output(PrecisionEvaluation)


# --------------------------------------------------
# Prompt
# --------------------------------------------------

prompt = f"""
You are evaluating the PRECISION of an AI tender compliance system.

You are given:

1. GOLD REQUIREMENTS
These are expert-verified obligations from the tender.

2. NEGATIVE CONTROLS
These describe claims the system must NOT incorrectly turn into
requirements.

3. PREDICTED REQUIREMENTS
These are the final requirements produced by the AI system.


YOUR TASK

Evaluate EVERY predicted requirement.


SUPPORTED

A prediction is supported when its material obligation is represented
by one or more gold requirements.

The prediction must preserve the material meaning of the source,
including where applicable:

- actor
- required action
- condition
- timing
- threshold
- amount
- document
- form
- submission condition


UNSUPPORTED

Mark supported=false when the prediction:

- invents an obligation
- materially overstates the source
- converts informational text into an obligation
- converts a government action into a bidder obligation
- treats a website listing or heading as an obligation
- asserts details that exist only in an unseen external document
- conflicts with a negative control
- cannot be supported by the gold requirements


IMPORTANT EXTERNAL REFERENCE RULE

A prediction about an incorporated external document is supported
ONLY to the extent stated in the supplied tender.

Do not treat unknown contents of an external document as established
requirements.


DUPLICATES

Multiple predicted rows must NOT receive precision credit for merely
repeating the same gold obligation.

If multiple predictions represent substantially the same obligation:

- choose the single best prediction as supported
- mark the additional predictions as duplicate=true
- duplicate predictions should have supported=false
- list the prediction ID(s) they duplicate in duplicate_of


COMBINED PREDICTIONS

One prediction MAY legitimately cover multiple gold requirements when
it explicitly preserves each distinct obligation.

In that case:

supported=true

and list every applicable gold ID.


NEGATIVE CONTROLS

If a prediction violates a negative control:

supported=false

and place the applicable negative-control ID in negative_control_ids.


IMPORTANT

Do not reward a prediction merely because it discusses the same topic.

For example:

Gold:
"Commercial general liability coverage must be at least $5,000,000."

Prediction:
"Contractor must maintain required insurance."

This does NOT preserve the material threshold and is not sufficient
to represent that specific gold obligation.

Evaluate all {len(predictions)} predicted requirements.

Return exactly one assessment for every prediction.


GOLD REQUIREMENTS:

{json.dumps(gold, indent=2)}


NEGATIVE CONTROLS:

{json.dumps(negative_controls, indent=2)}


PREDICTED REQUIREMENTS:

{json.dumps(predictions, indent=2)}
"""


# --------------------------------------------------
# Run evaluation
# --------------------------------------------------

result = judge.invoke(prompt)


# --------------------------------------------------
# Deterministic calculations
# --------------------------------------------------

assessments = result.assessments

supported = [
    a for a in assessments
    if a.supported
]

unsupported = [
    a for a in assessments
    if not a.supported and not a.duplicate
]

duplicates = [
    a for a in assessments
    if a.duplicate
]

negative_control_violations = [
    a for a in assessments
    if a.negative_control_ids
]


precision = (
    len(supported) / len(predictions)
    if predictions
    else 0
)


# --------------------------------------------------
# Display results
# --------------------------------------------------

print("\n==============================")
print("REQUIREMENT PRECISION")
print("==============================")

print(f"Predictions: {len(predictions)}")
print(f"Supported: {len(supported)}")
print(f"Unsupported: {len(unsupported)}")
print(f"Duplicates: {len(duplicates)}")
print(
    "Negative-control violations: "
    f"{len(negative_control_violations)}"
)

print(f"Precision: {precision:.2%}")


print("\n==============================")
print("UNSUPPORTED PREDICTIONS")
print("==============================")

for item in unsupported:
    print(f"\n{item.prediction_id}")
    print(item.reason)


print("\n==============================")
print("DUPLICATE PREDICTIONS")
print("==============================")

for item in duplicates:
    print(f"\n{item.prediction_id}")
    print(f"Duplicate of: {item.duplicate_of}")
    print(item.reason)


print("\n==============================")
print("NEGATIVE CONTROL VIOLATIONS")
print("==============================")

for item in negative_control_violations:
    print(f"\n{item.prediction_id}")
    print(
        "Controls:",
        item.negative_control_ids
    )
    print(item.reason)


# --------------------------------------------------
# Save evaluation
# --------------------------------------------------

evaluation = {
    "gold_count": len(gold),
    "prediction_count": len(predictions),

    "supported_count": len(supported),
    "unsupported_count": len(unsupported),
    "duplicate_count": len(duplicates),

    "negative_control_violation_count":
        len(negative_control_violations),

    "precision": precision,

    "assessments": [
        a.model_dump()
        for a in assessments
    ],
}


output_path = Path(
    "evaluation/fixtures/output_3_precision_evaluation.json"
)

with output_path.open(
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        evaluation,
        f,
        indent=2,
        ensure_ascii=False,
    )


print(
    f"\nSaved precision evaluation to: "
    f"{output_path}"
)