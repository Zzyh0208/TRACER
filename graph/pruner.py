# 文件路径: E:\py_project\Urban_Cognition_Framework\src\graph\pruner.py

import pandas as pd
import networkx as nx
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GradientSubgraphRetriever:
    def __init__(self, graph_manager):
        self.graph = graph_manager.graph
        self.df_log = None

        self.edge_id_to_nodes = {}
        for u, v, data in self.graph.edges(data=True):
            if 'id' in data:
                self.edge_id_to_nodes[data['id']] = (u, v)

    def load_case_data(self, csv_path):
        try:
            self.df_log = pd.read_csv(csv_path)
            self.df_log.set_index(['time', 'edge_id'], inplace=True)
        except Exception as e:
            logging.error(f"Pruner load CSV failed: {e}")

    def get_edge_data(self, edge_id, timestamp):
        try:
            if (timestamp, edge_id) in self.df_log.index:
                row = self.df_log.loc[(timestamp, edge_id)]
                # 获取全维度数据：速度、车辆数、占有率
                speed = float(row['speed'])
                vehs = float(row['vehicle_count'])
                # 兼容 occupancy 可能不存在的情况
                occ = float(row.get('occupancy', 0.0))
                return speed, vehs, occ
            return None, None, None
        except KeyError:
            return None, None, None

    def trace_congestion_chain(self, center_edge_id, timestamp, max_depth=10):
        """
        [V9.1] 提取从上游到下游的完整交通流路径 (已增加循环检测)
        逻辑：贪心搜索，优先追踪“车多”或“拥堵”的分支，并避免重复访问。
        """
        if center_edge_id not in self.edge_id_to_nodes:
            return []

        # [新增] 初始化一个集合，用于存储路径中所有已访问过的 edge_id
        visited_edges = {center_edge_id}

        # 获取 Center 数据
        c_spd, c_vehs, c_occ = self.get_edge_data(center_edge_id, timestamp)

        # --- 1. 向下游搜索 (寻找拥堵去向/瓶颈) ---
        downstream_path = []
        curr = center_edge_id
        for _ in range(max_depth):
            if curr not in self.edge_id_to_nodes: break
            u, v = self.edge_id_to_nodes[curr]
            successors = list(self.graph.successors(v))

            if not successors: break

            best_next = None
            max_score = -999

            for succ in successors:
                data = self.graph.get_edge_data(v, succ)
                eid = data['id']
                
                # [新增] 如果下游分支已经访问过，则跳过，避免循环
                if eid in visited_edges:
                    continue
                
                spd, vehs, occ = self.get_edge_data(eid, timestamp)
                if spd is None: continue

                score = vehs
                if spd < 5.0: score += 1000

                if score > max_score:
                    max_score = score
                    best_next = {"edge_id": eid, "speed": spd, "vehs": vehs, "occ": occ}

            if best_next:
                best_next['role'] = 'Downstream'
                downstream_path.append(best_next)
                curr = best_next['edge_id']
                
                # [新增] 将新找到的 edge_id 加入已访问集合
                visited_edges.add(curr)

                if best_next['speed'] > 10 and best_next['vehs'] == 0:
                    break
            else:
                break

        # --- 2. 向上游搜索 (寻找拥堵来源) ---
        upstream_path = []
        curr = center_edge_id
        for _ in range(max_depth):
            if curr not in self.edge_id_to_nodes: break
            u, v = self.edge_id_to_nodes[curr]
            predecessors = list(self.graph.predecessors(u))

            if not predecessors: break

            best_prev = None
            max_score = -999

            for pre in predecessors:
                data = self.graph.get_edge_data(pre, u)
                eid = data['id']

                # [新增] 如果上游分支已经访问过，则跳过
                if eid in visited_edges:
                    continue

                spd, vehs, occ = self.get_edge_data(eid, timestamp)
                if spd is None: continue

                if vehs < 5: continue

                score = vehs
                if spd < 5.0: score += 1000

                if score > max_score:
                    max_score = score
                    best_prev = {"edge_id": eid, "speed": spd, "vehs": vehs, "occ": occ}

            if best_prev:
                best_prev['role'] = 'Upstream'
                upstream_path.append(best_prev)
                curr = best_prev['edge_id']
                
                # [新增] 将新找到的 edge_id 加入已访问集合
                visited_edges.add(curr)
            else:
                break
        
        # --- 3. 组装 ---
        # (这部分无需改动)
        full_chain = []
        for item in reversed(upstream_path): full_chain.append(item)
        full_chain.append({
            "edge_id": center_edge_id, "speed": c_spd, "vehs": c_vehs, "occ": c_occ, "role": "Candidate (Detector Hit)"
        })
        for item in downstream_path: full_chain.append(item)

        return full_chain

    def format_chain_text(self, chain):
        """
        生成给 LLM 的详细报表 (已修复 NoneType 报错)
        """
        text = "### TRAFFIC STREAM DATA (Flow Direction: Top -> Bottom) ###\n"
        text += "Columns: [Role] EdgeID | Speed(m/s) | Vehicles | Occupancy(%)\n"
        text += "-" * 60 + "\n"

        for i, item in enumerate(chain):
            marker = "   "
            if "Candidate" in item['role']: marker = ">> "

            # [修复] 增加空值安全检查
            if item['speed'] is not None:
                spd = f"{item['speed']:.1f}"
            else:
                spd = "N/A"

            if item['vehs'] is not None:
                vehs = f"{item['vehs']:.0f}"
            else:
                vehs = "N/A"

            if item['occ'] is not None:
                occ = f"{item['occ'] * 100:.1f}%"
            else:
                occ = "?"

            text += f"{marker}Step {i + 1}: {item['edge_id']} | Spd:{spd} | Veh:{vehs} | Occ:{occ} | {item['role']}\n"

        return text