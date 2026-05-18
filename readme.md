# TRACER: Physics-Guided Causal Evidence Construction for Zero-Shot Traffic Anomaly Diagnosis

[![DOI](https://shields.io)](https://doi.org/10.5281/zenodo.20267314)

**TRACER** is a traffic congestion root cause analysis framework that integrates traffic simulation (SUMO), statistical causal inference (Granger Causality), and Large Language Model (LLM) agents.

Through a workflow of **"Detection -> Parallel Diagnosis -> Fusion Reasoning"**, this project utilizes physical knowledge (road network topology) and statistical evidence (Granger causality test) to assist LLMs in accurately pinpointing the source of traffic congestion.

## 🧠 Core Algorithm Logic (Agent & LLM)

TRACER's diagnostic process is one of **"parallel hypothesis verification + global fusion"**. The code logic is primarily implemented in `main.py` and `utils.py`.

### 1. Anomaly Detection and Candidate Generation (Detector)

* **Input**: Traffic flow logs (CSV).
* **Logic**: Uses a weighted detector algorithm to calculate anomaly scores based on speed drop rate, occupancy increase, and vehicle count.
* **Output**: Top-5 abnormal road segments (Candidates), serving as the starting points for parallel diagnosis.

### 2. Stage 1: Parallel Chain Diagnosis (Parallel Workers)

For each candidate segment in the Top-5, an independent Worker process is launched (implemented via `utils.py/worker_process_candidate`):

1. **Chain Tracking (Pruner)**: Uses `GradientSubgraphRetriever` to greedily search upstream and downstream from the candidate point, constructing a "congestion propagation chain."
2. **Statistical Verification (Statistical Check)**:
* Performs the **Granger Causality Test** on adjacent node pairs within the chain.
* Calculates the F-score and P-value to determine whether downstream congestion is the statistical cause of upstream congestion.


3. **LLM Single-Chain Reasoning**:
* Injects the **chain data** + **Granger statistical evidence** into `SYSTEM_PROMPT_STAGE1`.
* The LLM outputs the potential root cause and its confidence level within that specific chain.



### 3. Stage 2: Global Fusion Reasoning (Fusion)

After all Workers complete their tasks, the fusion stage begins (implemented via `main.py/perform_fusion_analysis`):

* **Input**: Diagnostic result summaries from the 5 chains.
* **Fusion Logic**:
* **Intra-chain Deduplication**: If there are duplicate reports within a single chain, the one with the highest confidence is selected.
* **Inter-chain Superposition**: If different chains point to the same root cause (Edge ID), their Impact Scores (number of affected vehicles) are **accumulated**. This is because multiple independent evidence chains pointing to the same source strengthen the validity of the evidence.


* **Output**: The final ranked list of root causes.

## 🚦 Simulation Environment Construction (Simulation)

Before running the analysis, a high-quality simulation scenario needs to be constructed. The scripts under the `simulation/` directory form a closed-loop workflow:

1. **Network Building (Steps 1-3)**:
* `step1`: Downloads OSM data to generate the base road network.
* `step2`: Automatically identifies complex junctions (e.g., those with multiple connections).
* `step3`: Forcibly upgrades these junctions to traffic light control, generating `xian_north_final.net.xml`.


2. **Demand Generation**: `generate_demand.py` generates random traffic flows with straight-driving tendencies and destination guidance based on the road network hierarchy (arterial/secondary roads).
3. **Detector Deployment**: `generate_detectors.py` automatically deploys E1 detectors and induction loops.
4. **Fault Simulation**: `simulator.py` supports the injection of Lane Blockage, All-Red traffic lights, and Road Damage faults.

## 🚀 Quick Start

### 1. Environment Preparation

Ensure SUMO and the required Python dependencies are installed:

```bash
# Set the SUMO_HOME environment variable (adjust to your installation path)
export SUMO_HOME="/path/to/sumo"

# Install Python libraries
pip install numpy pandas scipy statsmodels networkx traci sumolib requests tqdm

```

### 2. Build Simulation Scenario

Execute the scripts in order to generate data (or write a shell script to run them in batch):

```bash
cd src/simulation
python step1_build_base_network.py
python step2_find_major_junctions.py
python step3_build_final_network.py
python generate_demand.py
python generate_detectors.py
# At this point, the complete road network files will be generated in the data/ directory

```

### 3. Run Root Cause Analysis (RCA)

Configure your API Key:
Open `src/config_and_prompts.py` and fill in your `OPENROUTER_API_KEY`.

Execute the main program:

```bash
cd src
python main.py

```

The program will automatically:

1. Load the road network graph (`graph_builder`).
2. Read the CSV logs located in `data/dataset_raw`.
3. Start 5 Workers in parallel to analyze the Top-5 anomaly points.
4. Call the LLM to perform Stage 2 fusion.
5. Output the results to the `results/` directory.

## ⚙️ Configuration Guide

Key parameters can be adjusted in `src/config_and_prompts.py`:

* `MODELS_TO_TEST`: List of LLMs to be evaluated.
* `DIAGNOSIS_TIME`: The specific time slice for diagnosis.
* `TOP_K_AGENT`: Number of candidate nodes for parallel analysis (default is 5).
* `SYSTEM_PROMPT_STAGE1/2`: Adjust prompt strategies.
