from dotenv import load_dotenv
load_dotenv(override=True)

from langsmith import Client

client = Client()
root = client.read_run("01a0e3e8-20f4-78a3-88ad-6081ae1a1ed9")

runs = client.list_runs(project_name="compliance-matrix-agent", trace_id=root.trace_id)
total_tokens = 0
total_cost = 0
for r in sorted(runs, key=lambda r: r.start_time):
    latency = (r.end_time - r.start_time).total_seconds() if r.end_time else 0
    tokens = r.total_tokens or 0
    cost = float(r.total_cost or 0)
    if r.run_type == "llm":
        total_tokens += tokens
        total_cost += cost
    print(f"{r.name:40} {latency:>8.2f}s  tokens={tokens:>7}  cost=${cost:.4f}")

wall_time = (root.end_time - root.start_time).total_seconds()
print(f"\nTotal time: {wall_time:.2f}s")
print(f"Total tokens: {total_tokens}")
print(f"Total LLM cost: ${total_cost:.4f}")