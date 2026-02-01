import pandas as pd
import requests
import numpy as np
import time
import json
import re
from statsmodels.tsa.stattools import grangercausalitytests
from src.graph.pruner import GradientSubgraphRetriever
from config_and_prompts import OPENROUTER_API_KEY, OPENROUTER_URL, DIAGNOSIS_TIME, SYSTEM_PROMPT_STAGE1

def call_llm(model_name, system_prompt, user_prompt, temperature=0.2):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Urban-Cognition",
        "X-Title": "Traffic-RCA-Research",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": 4000 
    }
    if any(x in model_name for x in ["gpt-5.2", "gemini-3", "glm-4.7", "deepseek"]): 
        payload["reasoning"] = {"enabled": True}

    start_t = time.time()
    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=120)
        duration = time.time() - start_t
        if response.status_code == 200:
            res_json = response.json()
            if "choices" in res_json and len(res_json["choices"]) > 0:
                content = res_json["choices"][0]["message"]["content"]
                if content:
                    if content.startswith("```json"): 
                        content = content.replace("```json", "").replace("```", "")
                    return content, duration, res_json.get("usage", {}).get("total_tokens", 0)
            return None, duration, 0
        else:
            return None, duration, 0
    except Exception:
        return None, 0, 0

def run_weighted_detector(fault_csv, normal_csv, center_time, window_half, top_k):
    try:
        df_f = pd.read_csv(fault_csv)
        df_n = pd.read_csv(normal_csv)
        t_s, t_e = center_time - window_half, center_time + window_half
        df_f = df_f[(df_f['time'] >= t_s) & (df_f['time'] <= t_e)].groupby('edge_id').mean()
        df_n = df_n[(df_n['time'] >= t_s) & (df_n['time'] <= t_e)].groupby('edge_id').mean()
        df = df_f.join(df_n, lsuffix='_f', rsuffix='_n', how='inner')
        df = df[(df['speed_n'] > 1.0) & (df['vehicle_count_f'] >= 2)]
        df['speed_drop'] = (df['speed_n'] - df['speed_f']) / (df['speed_n'] + 1e-5)
        df['occ_rise'] = df['occupancy_f'] - df['occupancy_n']
        df['score'] = (df['speed_drop'].clip(0, 1) + df['occ_rise'].clip(0, 1)) * (np.log1p(df['vehicle_count_f']) ** 0.8)
        return df.sort_values('score', ascending=False).head(top_k)
    except:
        return pd.DataFrame()

def calculate_pair_granger(downstream_series, upstream_series, max_lag=3):
    df = pd.DataFrame({'Y': upstream_series, 'X': downstream_series}).dropna()
    if df['X'].nunique() <= 1 or df['Y'].nunique() <= 1:
        return {'p_value': 1.0, 'f_score': 0.0}
    if len(df) < max_lag + 2:
        return {'p_value': 1.0, 'f_score': 0.0}
    try:
        gc_res = grangercausalitytests(df[['Y', 'X']], maxlag=[max_lag], verbose=False)
        res_stats = gc_res[max_lag][0]['ssr_ftest']
        return {'p_value': round(res_stats[1], 4), 'f_score': round(res_stats[0], 2)}
    except:
        return {'p_value': 1.0, 'f_score': 0.0}

def get_ground_truth_edges(label, graph_manager):
    if label.get('edge_id'): return [label['edge_id']]
    if label.get('tls_id'):
        tls_id = label['tls_id']
        incoming = []
        try:
            if graph_manager.graph.has_node(tls_id):
                for u, v, d in graph_manager.graph.in_edges(tls_id, data=True):
                    if 'id' in d: incoming.append(d['id'])
            else:
                for u, v, d in graph_manager.graph.edges(data=True):
                    if v == tls_id and 'id' in d: incoming.append(d['id'])
        except:
            pass
        return incoming
    return []

def check_hit_with_tolerance(pred_id, true_roots, graph_manager):
    if pred_id in true_roots: 
        return True, "Exact"
    if pred_id not in graph_manager.edge_id_to_nodes: 
        return False, "Miss"
    u_p, v_p = graph_manager.edge_id_to_nodes[pred_id]
    for tr in true_roots:
        if tr not in graph_manager.edge_id_to_nodes: 
            continue
        u_t, v_t = graph_manager.edge_id_to_nodes[tr]
        if v_p == u_t or u_p == v_t or u_p == u_t or v_p == v_t: 
            return True, "1-Hop"
    return False, "Miss"

def extract_json_from_response(response_str):
    if not response_str: return []
    try:
        clean_str = response_str
        if "</think>" in clean_str:
            clean_str = clean_str.split("</think>")[-1].strip()
        match = re.search(r'\{.*\}', clean_str, re.DOTALL)
        if match:
            clean_str = match.group(0)
        res_json = json.loads(clean_str)
        if "predictions" in res_json:
            return res_json["predictions"]
        if "fused_results" in res_json:
            return res_json["fused_results"]
        if isinstance(res_json, list):
            return res_json
        return [res_json]
    except:
        pass
    return []

def worker_process_candidate(args):
    candidate_edge_id, fault_csv, model_name, graph_manager_local = args
    pruner = GradientSubgraphRetriever(graph_manager_local)
    pruner.load_case_data(fault_csv)
    chain_data = pruner.trace_congestion_chain(candidate_edge_id, DIAGNOSIS_TIME, max_depth=15)
    
    granger_evidence = []
    full_log = pruner.df_log
    t_s, t_e = DIAGNOSIS_TIME - 300, DIAGNOSIS_TIME + 100
    time_mask = (full_log['time'] >= t_s) & (full_log['time'] <= t_e)
    chain_ids = [n['edge_id'] for n in chain_data]
    
    for i in range(len(chain_ids) - 1):
        down_node = chain_ids[i]
        up_node = chain_ids[i+1]
        ts_down = full_log[(full_log['edge_id'] == down_node) & time_mask].set_index('time')['speed']
        ts_up = full_log[(full_log['edge_id'] == up_node) & time_mask].set_index('time')['speed']
        common_idx = ts_down.index.intersection(ts_up.index)
        if len(common_idx) > 10:
            res = calculate_pair_granger(ts_down.loc[common_idx], ts_up.loc[common_idx])
            granger_evidence.append(f"Link {down_node} -> {up_node}: Granger F={res['f_score']}, p={res['p_value']}")
            
    granger_text = "\n".join(granger_evidence) if granger_evidence else "No Granger data available."
    context_text = pruner.format_chain_text(chain_data)
    user_prompt = f"--- Chain Data ---\n{context_text}\n\n--- Granger Causality Evidence ---\n{granger_text}\n\nAnalyze this chain."
    
    response, dur, toks = call_llm(model_name, SYSTEM_PROMPT_STAGE1, user_prompt)
    predictions = extract_json_from_response(response)
    
    return {
        "candidate_start": candidate_edge_id,
        "chain_ids": chain_ids,
        "predictions": predictions,
        "raw_response": response,
        "duration": dur
    }