import os

OPENROUTER_API_KEY = "sk-or-xxxxxxxxxxxxxxxxx"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS_TO_TEST = [
    "openai/gpt-5.2",
    "google/gemini-3-pro-preview",
    "x-ai/grok-4",
    "qwen/qwen3-235b-a22b",
    "z-ai/glm-4.7",
    "deepseek/deepseek-v3.2"
]

PROJECT_ROOT = r"E:\py_project\Urban_Cognition_Framework"
NET_FILE = os.path.join(PROJECT_ROOT, "data", "xian_north_final", "xian_north_final.net.xml")
GRAPH_PKL = os.path.join(PROJECT_ROOT, "data", "graph", "xian_road_graph.pkl")
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "dataset_raw")
BATCH_FOLDER = "dataset_final_publication"
BASELINE_CSV = os.path.join(RAW_DIR, "baseline", "normal_log.csv")

DIAGNOSIS_TIME = 2300
TIME_WINDOW_HALF = 50
TOP_K_DETECTOR = 10
TOP_K_AGENT = 5

SYSTEM_PROMPT_STAGE1 = (
    "You are an expert Traffic Control AI. Analyze the provided traffic flow chain and statistical evidence.\n"
    "Your task is to identify valid bottlenecks in this specific chain.\n\n"
    "**Input Data:**\n"
    "1. **Traffic Chain:** A sequence of road segments from the potential congestion center upwards.\n"
    "2. **Granger Causality Stats:** Statistical tests checking if the downstream node's speed drops CAUSED the upstream node's speed drop.\n"
    "   - High F-score / Low p-value (<0.05) indicates strong causal propagation.\n\n"
    "**Logic:**\n"
    "1. Identify JAMMED -> FREE-FLOW transitions (Bottlenecks).\n"
    "2. **Verify with Granger:** If you identify a bottleneck at Node A causing jams at Node B (upstream), check the Granger stat for A->B.\n"
    "3. Calculate impact: Sum of vehicles in the continuous jam upstream of the bottleneck.\n\n"
    "**Output JSON:**\n"
    "Return a JSON list of identified bottlenecks.\n"
    "{\n"
    "  \"predictions\": [\n"
    "    {\n"
    "      \"predicted_root_id\": \"Edge_ID\",\n"
    "      \"impact_vehicle_count\": 120,\n"
    "      \"confidence\": 0.9,\n"
    "      \"reasoning\": \"Clear speed drop and strong Granger causality.\"\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "If no clear bottleneck, return empty list."
)

SYSTEM_PROMPT_STAGE2 = (
    "You are the Chief Traffic Engineer. You have received diagnosis reports from 5 parallel investigation chains.\n"
    "Your goal is to aggregate these findings into a single ranked list of Root Causes.\n\n"
    "**Fusion Logic (STRICTLY FOLLOW):**\n"
    "1. **Deduplicate Same Chain:** If a single chain reports the same Root Cause multiple times, keep only the one with the highest confidence.\n"
    "2. **Merge Different Chains:**\n"
    "   - If **different chains** point to the **SAME** predicted_root_id, you must **SUM** their impact_vehicle_count to get the total global impact.\n"
    "   - If they point to different roots, treat them as separate.\n"
    "3. **Ranking:** Rank the final fused root causes by their **Total Impact Score** (descending).\n\n"
    "**Output Format:**\n"
    "Provide your reasoning in <think> tags, then output the final fused JSON list.\n"
    "{\n"
    "  \"fused_results\": [\n"
    "    {\n"
    "      \"root_cause_id\": \"Edge_X\",\n"
    "      \"total_impact_score\": 350,\n"
    "      \"vote_count\": 3,\n"
    "      \"final_reasoning\": \"Identified by 3 chains. Total impact is sum of impacts.\"\n"
    "    }\n"
    "  ]\n"
    "}"
)