import os
import json
import glob
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from src.graph.graph_builder import RoadGraphManager
from config_and_prompts import *
from utils import (
    call_llm, run_weighted_detector, get_ground_truth_edges, 
    check_hit_with_tolerance, extract_json_from_response, worker_process_candidate
)

graph_manager = None

def perform_fusion_analysis(model_name, stage1_results):
    summary_lines = []
    valid_count = 0
    for i, res in enumerate(stage1_results):
        preds = res.get('predictions', [])
        chain_ids = res.get('chain_ids', [])
        if not preds:
            summary_lines.append(f"Chain_{i} (Edges: {chain_ids[:3]}...): No Cause Found")
        else:
            for p in preds:
                valid_count += 1
                r_id = p.get('predicted_root_id', 'Unknown')
                imp = p.get('impact_vehicle_count', 0)
                conf = p.get('confidence', 0)
                summary_lines.append(f"Chain_{i} (Edges: {chain_ids[:3]}...) -> Found Root: '{r_id}', Impact Score: {imp}, Confidence: {conf}")

    if valid_count == 0:
        return [], "No valid predictions to fuse."

    summary_text = "\n".join(summary_lines)
    user_prompt = f"Here are the reports from the 5 chains:\n\n{summary_text}\n\nPerform the fusion analysis."
    response, dur, toks = call_llm(model_name, SYSTEM_PROMPT_STAGE2, user_prompt)
    fused_results = extract_json_from_response(response)
    return fused_results, response

def solve_single_case_workflow(args):
    case_id, log_file, label_file, baseline_csv, model_name, result_dir = args
    detail_dir = os.path.join(result_dir, "details")
    os.makedirs(detail_dir, exist_ok=True)
    
    with open(label_file, 'r') as f:
        label = json.load(f)
    true_roots = get_ground_truth_edges(label, graph_manager)
    
    candidates_df = run_weighted_detector(log_file, baseline_csv, DIAGNOSIS_TIME, TIME_WINDOW_HALF, TOP_K_DETECTOR)
    if candidates_df.empty:
        return {"CaseID": case_id, "Status": "No Candidates", "Is_Hit": 0}
    
    top_candidates = candidates_df.head(TOP_K_AGENT)
    detector_rank = -1
    for root in true_roots:
        if root in candidates_df.index:
            rank = candidates_df.index.get_loc(root) + 1
            if detector_rank == -1 or rank < detector_rank: detector_rank = rank

    worker_tasks = []
    for edge_id in top_candidates.index:
        worker_tasks.append((edge_id, log_file, model_name, graph_manager))
    
    stage1_results = []
    total_stage1_time = 0
    with ProcessPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_process_candidate, task) for task in worker_tasks]
        for future in as_completed(futures):
            try:
                res = future.result()
                stage1_results.append(res)
                total_stage1_time += res['duration']
            except:
                pass

    fused_results, fusion_raw_resp = perform_fusion_analysis(model_name, stage1_results)
    
    best_pred_id = "None"
    vote_count = 0
    if fused_results:
        best_pred_id = fused_results[0].get('root_cause_id', "None")
        vote_count = fused_results[0].get('vote_count', 0)

    final_hit = 0
    hit_type = "Miss"
    if best_pred_id != "None":
        is_hit, h_type = check_hit_with_tolerance(best_pred_id, true_roots, graph_manager)
        if is_hit:
            final_hit = 1
            hit_type = h_type

    log_data = {
        "case_id": case_id,
        "true_roots": true_roots,
        "detector_candidates": top_candidates.index.tolist(),
        "stage1_results": stage1_results,
        "stage2_fusion_raw": fusion_raw_resp,
        "fused_ranking": fused_results
    }
    with open(os.path.join(detail_dir, f"{case_id}.json"), 'w') as f:
        json.dump(log_data, f, indent=2)

    return {
        "CaseID": case_id,
        "Model": model_name,
        "Fault_Type": label.get('type', 'Unknown'),
        "True_Roots": str(true_roots),
        "Detector_Rank": detector_rank,
        "Pred_Root": best_pred_id,
        "Is_Hit": final_hit,
        "Hit_Type": hit_type,
        "Vote_Count": vote_count,
        "Stage1_Time": round(total_stage1_time, 2),
        "Fusion_Count": len(fused_results)
    }

def main():
    global graph_manager
    graph_manager = RoadGraphManager(NET_FILE)
    if os.path.exists(GRAPH_PKL):
        graph_manager.load_graph(GRAPH_PKL)
    else:
        graph_manager.build_graph()

    all_log_files = glob.glob(os.path.join(RAW_DIR, BATCH_FOLDER, "*_log.csv"))
    all_log_files.sort()
    target_log_files = all_log_files[:45]
    
    for model_name in MODELS_TO_TEST:
        safe_model_name = model_name.replace("/", "_")
        current_result_dir = os.path.join(PROJECT_ROOT, "results", f"parallel_v2_{safe_model_name}")
        os.makedirs(current_result_dir, exist_ok=True)
        summary_path = os.path.join(current_result_dir, "summary.csv")
        results_list = []
        
        for log_file in tqdm(target_log_files, desc=f"Running {safe_model_name}"):
            case_id = os.path.basename(log_file).replace("_log.csv", "")
            label_file = log_file.replace("_log.csv", "_label.json")
            task_args = (case_id, log_file, label_file, BASELINE_CSV, model_name, current_result_dir)
            try:
                res = solve_single_case_workflow(task_args)
                results_list.append(res)
                pd.DataFrame(results_list).to_csv(summary_path, index=False)
            except Exception as e:
                print(f"Error {case_id}: {e}")

if __name__ == "__main__":
    main()