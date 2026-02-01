# 文件路径: E:\py_project\Urban_Cognition_Framework\src\graph\graph_builder.py

import os
import pickle
import networkx as nx
import sumolib
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class RoadGraphManager:
    def __init__(self, net_file_path):
        """
        初始化路网管理器
        :param net_file_path: .net.xml 文件的绝对路径
        """
        self.net_file_path = net_file_path
        self.graph = None  # NetworkX DiGraph
        self.net = None  # sumolib Net object
        # [新增] 核心索引：EdgeID -> (SourceNode, TargetNode)
        self.edge_id_to_nodes = {}

    def build_graph(self):
        """
        解析 SUMO 网络并构建 NetworkX 图
        """
        logging.info(f"正在加载 SUMO路网: {self.net_file_path} ... (可能需要几秒钟)")

        self.net = sumolib.net.readNet(self.net_file_path, withOutgoing=True)

        logging.info("SUMO路网加载完成，正在构建 NetworkX 图...")

        self.graph = nx.DiGraph()
        # 重置索引
        self.edge_id_to_nodes = {}

        edges = self.net.getEdges()
        logging.info(f"路网包含 {len(edges)} 条边 (Edges)")

        for edge in edges:
            edge_id = edge.getID()

            if edge_id.startswith(":"):
                continue

            from_node = edge.getFromNode().getID()
            to_node = edge.getToNode().getID()
            length = edge.getLength()
            speed_limit = edge.getSpeed()
            lane_count = edge.getLaneNumber()

            # 添加边到 NetworkX 图
            self.graph.add_edge(from_node, to_node,
                                id=edge_id,
                                length=length,
                                speed=speed_limit,
                                lanes=lane_count)

            # [新增] 构建快速索引
            self.edge_id_to_nodes[edge_id] = (from_node, to_node)

        logging.info(f"NetworkX 图构建完成。节点数: {self.graph.number_of_nodes()}, 边数: {self.graph.number_of_edges()}")

    def save_graph(self, output_path):
        """
        将构建好的图保存为 pickle 文件
        """
        if self.graph is None:
            raise ValueError("图尚未构建，请先调用 build_graph()")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # 注意：这里我们只保存 graph 对象，edge_id_to_nodes 在加载时重建，以减小文件体积并保持兼容
        with open(output_path, 'wb') as f:
            pickle.dump(self.graph, f)
        logging.info(f"路网图已保存至: {output_path}")

    def load_graph(self, input_path):
        """
        从 pickle 文件加载图
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"图文件不存在: {input_path}")

        with open(input_path, 'rb') as f:
            self.graph = pickle.load(f)

        # [新增] 加载 Graph 后，必须重建索引，否则 edge_id_to_nodes 会是空的
        logging.info("正在重建 Edge ID 索引...")
        self.edge_id_to_nodes = {}
        for u, v, data in self.graph.edges(data=True):
            if 'id' in data:
                self.edge_id_to_nodes[data['id']] = (u, v)

        logging.info(f"已加载路网图，包含 {self.graph.number_of_edges()} 条边")

    def get_context_subgraph(self, edge_id, k_hop=2):
        """
        (核心功能) 给定一个 Edge ID，返回其上下游 k-hop 的子图信息
        """
        # [优化] 使用字典直接查找，速度从 O(N) 提升到 O(1)
        if edge_id not in self.edge_id_to_nodes:
            return f"Edge {edge_id} not found in graph."

        target_u, target_v = self.edge_id_to_nodes[edge_id]

        # 为了兼容性，重新获取 data
        target_data = self.graph.get_edge_data(target_u, target_v)
        # 处理 MultiDiGraph 兼容性
        if isinstance(target_data, dict) and 'id' not in target_data:
            if 0 in target_data: target_data = target_data[0]

        # 搜索上游 (Predecessors)
        upstream_edges = []
        try:
            predecessors = list(self.graph.predecessors(target_u))
            for pre_node in predecessors:
                edge_data = self.graph.get_edge_data(pre_node, target_u)
                if isinstance(edge_data, dict) and 'id' not in edge_data:
                    if 0 in edge_data: edge_data = edge_data[0]

                if 'id' in edge_data:
                    upstream_edges.append(f"{edge_data['id']} (Speed: {edge_data.get('speed', 0)}m/s)")
        except:
            pass

        # 搜索下游 (Successors)
        downstream_edges = []
        try:
            successors = list(self.graph.successors(target_v))
            for succ_node in successors:
                edge_data = self.graph.get_edge_data(target_v, succ_node)
                if isinstance(edge_data, dict) and 'id' not in edge_data:
                    if 0 in edge_data: edge_data = edge_data[0]

                if 'id' in edge_data:
                    downstream_edges.append(f"{edge_data['id']} (Lanes: {edge_data.get('lanes', 1)})")
        except:
            pass

        context_str = (
            f"Focus Edge: {edge_id}\n"
            f" - Properties: Length={target_data.get('length', 0)}m, Lanes={target_data.get('lanes', 1)}\n"
            f" - Immediate Upstream: {', '.join(upstream_edges) if upstream_edges else 'None'}\n"
            f" - Immediate Downstream: {', '.join(downstream_edges) if downstream_edges else 'None'}"
        )
        return context_str


if __name__ == "__main__":
    # 测试代码
    NET_FILE = r"E:\py_project\Urban_Cognition_Framework\data\xian_north_final\xian_north_final.net.xml"
    # 这里定义你想保存的位置，要和 main_step8_batch.py 里读取的位置一致
    SAVE_PATH = r"E:\py_project\Urban_Cognition_Framework\data\graph\xian_road_graph.pkl"

    if os.path.exists(NET_FILE):
        manager = RoadGraphManager(NET_FILE)

        # 1. 构建
        manager.build_graph()

        # 2. 验证
        print(f"Index size: {len(manager.edge_id_to_nodes)}")
        test_edge = list(manager.edge_id_to_nodes.keys())[0]
        print(manager.get_context_subgraph(test_edge))

        # 3. 【新增】保存！
        manager.save_graph(SAVE_PATH)
        print(f"Graph successfully saved to: {SAVE_PATH}")