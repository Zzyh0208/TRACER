# # src/simulation/generate_demand_random_walk.py (最终成品 - 完全自洽)
#
# import os
# import sys
# import random
# import sumolib
# import subprocess
# import xml.etree.ElementTree as ET
# from xml.dom import minidom
# import math  # 导入Python内置的数学库
#
# # --- 配置区域 ---
# NETWORK_NAME = "xian_north_final"
# # 随机数种子，确保每次生成的车流都可复现
# SEED = 42
# # 仿真总时长（秒），例如 3600秒 = 1小时
# SIMULATION_END_TIME = 3600
# # 总车辆数，这是调控路网繁忙程度的最主要参数
# TOTAL_VEHICLE_COUNT = 22000
# # 每条随机路径的期望长度（步数），可以调整以增加或减少车辆的平均行程
# AVERAGE_PATH_LENGTH = 20
# # 柔和的宽路倾向 (值在0.1到1.0之间)
# LANE_COUNT_WEIGHT_FACTOR = 0.8
# # 强大的直行倾向 (值越大，越倾向于直行)
# STRAIGHT_PREFERENCE_BOOST = 7
#
# # --- 检查SUMO环境变量 ---
# sumo_home = ""
# if 'SUMO_HOME' in os.environ:
#     sumo_home = os.environ['SUMO_HOME']
#     tools = os.path.join(sumo_home, 'tools')
#     sys.path.append(tools)
# else:
#     sys.exit("please declare environment variable 'SUMO_HOME'")
#
# # --- 定义文件路径 ---
# data_path = f"../../data/{NETWORK_NAME}"
# net_file = f"{data_path}/{NETWORK_NAME}.net.xml"
# final_route_file = f"{data_path}/{NETWORK_NAME}.rou.xml"
#
#
# def run_command(command):
#     print(f"Executing: {' '.join(command)}")
#     try:
#         result = subprocess.run(command, check=True, capture_output=True, text=True, errors='ignore')
#         print("Success.")
#         if result.stdout:
#             print(f"Output:\n{result.stdout[:1500]}...")
#     except subprocess.CalledProcessError as e:
#         print(f"Error executing command: {' '.join(command)}")
#         print(f"Error Output:\n{e.stderr}")
#         sys.exit(1)
#
#
# def get_angle_from_points(p1, p2):
#     """
#     (自实现) 使用atan2计算由两点(p1 -> p2)定义的向量与x轴正方向的角度（0-360度）。
#     p1 和 p2 应该是 (x, y) 格式的元组。
#     """
#     if not isinstance(p1, (tuple, list)) or len(p1) < 2 or not isinstance(p2, (tuple, list)) or len(p2) < 2:
#         return 0.0  # 返回一个默认角度，如果输入点无效
#     dx = p2[0] - p1[0]
#     dy = p2[1] - p1[1]
#     # math.atan2返回弧度，我们将其转换为角度
#     angle_rad = math.atan2(dy, dx)
#     angle_deg = math.degrees(angle_rad)
#     # 将角度范围从 -180~180 转换为 0~360
#     return (angle_deg + 360) % 360
#
#
# def get_angle_diff(angle1, angle2):
#     """计算两个角度之间的最小差值 (0-360度)"""
#     diff = abs(angle1 - angle2) % 360
#     return min(diff, 360 - diff)
#
#
# def main():
#     """主流程函数 (最终修正版，内置数学库)"""
#
#     # --- Step 1: 加载路网并准备数据 ---
#     print(f"--- Step 1: Loading network from {net_file} ---")
#     if not os.path.exists(net_file):
#         print(f"Error: Network file '{net_file}' not found. Please run build_network.py first.")
#         sys.exit(1)
#
#     net = sumolib.net.readNet(net_file)
#
#     allowed_vclass = "passenger"
#     edges = [e for e in net.getEdges() if e.allows(allowed_vclass) and e.getFunction() not in ['internal', 'connector']]
#     if not edges:
#         print("Error: No valid edges found in the network.")
#         sys.exit(1)
#     print(f"Found {len(edges)} valid edges for random walks.")
#
#     # --- Step 2: 生成所有车辆的定义 ---
#     print(f"\n--- Step 2: Generating {TOTAL_VEHICLE_COUNT} vehicles with intelligent random walk routes ---")
#
#     random.seed(SEED)
#
#     vtypes_distribution = {
#         "car_aggressive": 0.15, "car_normal": 0.40, "car_conservative": 0.15,
#         "truck_light": 0.05, "truck_heavy": 0.15, "bus": 0.08, "motorcycle": 0.02
#     }
#     type_ids = list(vtypes_distribution.keys())
#     probabilities = list(vtypes_distribution.values())
#     depart_times = sorted([random.uniform(0, SIMULATION_END_TIME) for _ in range(TOTAL_VEHICLE_COUNT)])
#
#     routes_root = ET.Element("routes")
#
#     for i in range(TOTAL_VEHICLE_COUNT):
#         if (i + 1) % 1000 == 0:
#             print(f"    Generated routes for {i + 1}/{TOTAL_VEHICLE_COUNT} vehicles...")
#
#         path = []
#         current_edge = random.choice(edges)
#         path.append(current_edge.getID())
#
#         path_length = 1
#         target_length = int(random.gauss(AVERAGE_PATH_LENGTH, AVERAGE_PATH_LENGTH / 4))
#         target_length = max(5, target_length)
#
#         while path_length < target_length:
#             outgoing_edges_all = list(current_edge.getOutgoing().keys())
#             valid_next_edges = [e for e in outgoing_edges_all if
#                                 e.allows(allowed_vclass) and e.getFunction() not in ['internal', 'connector']]
#
#             if not valid_next_edges:
#                 break
#
#             weights = []
#             shape = current_edge.getShape()
#             if len(shape) < 2:
#                 # 如果当前道路形状点不足，无法计算来向角度，则退化为柔和加权
#                 for edge in valid_next_edges:
#                     weights.append(len(edge.getLanes()) ** LANE_COUNT_WEIGHT_FACTOR)
#             else:
#                 # 正常计算带直行倾向的权重
#                 incoming_angle = get_angle_from_points(shape[-2], shape[-1])
#                 for edge in valid_next_edges:
#                     base_weight = len(edge.getLanes()) ** LANE_COUNT_WEIGHT_FACTOR
#
#                     edge_shape = edge.getShape()
#                     if len(edge_shape) < 2:
#                         weights.append(base_weight)
#                         continue
#
#                     outgoing_angle = get_angle_from_points(edge_shape[0], edge_shape[1])
#                     angle_difference = get_angle_diff(incoming_angle, outgoing_angle)
#
#                     if angle_difference < 30.0:
#                         final_weight = base_weight * STRAIGHT_PREFERENCE_BOOST
#                     elif angle_difference > 160.0:
#                         final_weight = 0.01
#                     else:
#                         final_weight = base_weight
#
#                     weights.append(final_weight)
#
#             if not weights or sum(weights) == 0:
#                 if not valid_next_edges: break
#                 weights = [1.0 for _ in valid_next_edges]
#
#             next_edge = random.choices(valid_next_edges, weights=weights, k=1)[0]
#
#             path.append(next_edge.getID())
#             current_edge = next_edge
#             path_length += 1
#
#         if len(path) > 1:
#             chosen_type = random.choices(type_ids, probabilities, k=1)[0]
#
#             vehicle = ET.SubElement(routes_root, "vehicle", {
#                 "id": str(i),
#                 "type": chosen_type,
#                 "depart": f"{depart_times[i]:.2f}"
#             })
#             ET.SubElement(vehicle, "route", {"edges": " ".join(path)})
#
#     # --- Step 3: 写入最终的 .rou.xml 文件 ---
#     print(f"\n--- Step 3: Writing final route file ---")
#     xml_str = ET.tostring(routes_root, 'utf-8')
#     try:
#         pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="    ")
#         with open(final_route_file, "w", encoding='utf-8') as f:
#             f.write(pretty_xml_str)
#     except Exception as e:
#         print(f"Warning: XML formatting failed, writing raw XML. Error: {e}")
#         with open(final_route_file, "w", encoding='utf-8') as f:
#             f.write(xml_str.decode('utf-8'))
#
#     print(f"\n--- Final intelligent random walk traffic generation completed! ---")
#     print(f"Final route file saved to: {final_route_file}")
#
#
# if __name__ == "__main__":
#     main()
# src/simulation/generate_demand_final.py (分层起点 + 终点引导 最终版)

import os
import sys
import random
import sumolib
import subprocess
import xml.etree.ElementTree as ET
from xml.dom import minidom
import math

# --- 配置区域 ---
NETWORK_NAME = "xian_north_final"
SEED = 42
SIMULATION_END_TIME = 3600
TOTAL_VEHICLE_COUNT = 40000
# 随机游走的最大步数，防止因意外情况导致无限循环
MAX_PATH_LENGTH = 30

# <<< 最终调优参数 >>>
# 1. 柔和的宽路倾向 (值在0.1到1.0之间，建议0.5)
LANE_COUNT_WEIGHT_FACTOR = 0.5
# 2. 强大的直行倾向 (值越大，越倾向于直行)
STRAIGHT_PREFERENCE_BOOST = 5
# 3. 强大的终点引导倾向 (值越大，车辆越“有目的性”)
DESTINATION_GUIDANCE_BOOST = 1

# 4. 核心配置：分层起点采样比例
START_EDGE_DISTRIBUTION = {
    'level1_arterial': 0.7,  # 70%的车出生在主干道
    'level2_collector': 0.2,  # 20%的车出生在次干道
    'level3_local': 0.1  # 10%的车出生在支路
}

# --- 检查SUMO环境变量 ---
sumo_home = ""
if 'SUMO_HOME' in os.environ:
    sumo_home = os.environ['SUMO_HOME']
    tools = os.path.join(sumo_home, 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

# --- 定义文件路径 ---
data_path = f"../../data/{NETWORK_NAME}"
net_file = f"{data_path}/{NETWORK_NAME}.net.xml"
final_route_file = f"{data_path}/{NETWORK_NAME}.rou.xml"


def get_angle_from_points(p1, p2):
    """(自实现) 使用atan2计算由两点(p1 -> p2)定义的向量与x轴正方向的角度（0-360度）。"""
    if not isinstance(p1, (tuple, list)) or len(p1) < 2 or not isinstance(p2, (tuple, list)) or len(p2) < 2:
        return 0.0
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)
    return (angle_deg + 360) % 360


def get_angle_diff(angle1, angle2):
    """计算两个角度之间的最小差值 (0-360度)"""
    diff = abs(angle1 - angle2) % 360
    return min(diff, 360 - diff)


def get_distance(p1, p2):
    """(自实现) 计算两点之间的欧几里得距离"""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def classify_edges(net):
    """根据车道数和限速，将路网中的所有有效道路分为三级"""
    print("Classifying network edges into three levels...")
    levels = {'level1_arterial': [], 'level2_collector': [], 'level3_local': []}
    allowed_vclass = "passenger"

    for edge in net.getEdges():
        if not edge.allows(allowed_vclass) or edge.getFunction() in ['internal', 'connector']:
            continue

        num_lanes = len(edge.getLanes())
        speed = edge.getSpeed()

        # 分级标准 (可以根据需要微调)
        if num_lanes >= 3 or (num_lanes >= 2 and speed > 16.67):  # ~60km/h
            levels['level1_arterial'].append(edge)
        elif num_lanes >= 2:
            levels['level2_collector'].append(edge)
        else:
            levels['level3_local'].append(edge)

    print(f"Classification complete: "
          f"Level 1 (Arterials): {len(levels['level1_arterial'])} edges, "
          f"Level 2 (Collectors): {len(levels['level2_collector'])} edges, "
          f"Level 3 (Locals): {len(levels['level3_local'])} edges")
    return levels


def main():
    """主流程函数 (分层起点 + 终点引导)"""

    # --- Step 1: 加载路网并进行分级 ---
    print(f"--- Step 1: Loading and classifying network from {net_file} ---")
    if not os.path.exists(net_file):
        print(f"Error: Network file '{net_file}' not found. Please run the final build_network.py first.")
        sys.exit(1)

    net = sumolib.net.readNet(net_file)
    edge_levels = classify_edges(net)
    all_valid_edges = edge_levels['level1_arterial'] + edge_levels['level2_collector'] + edge_levels['level3_local']

    if not all_valid_edges:
        print("Error: No valid edges found in the network after classification.")
        sys.exit(1)

    # --- Step 2: 生成所有车辆的定义 ---
    print(f"\n--- Step 2: Generating {TOTAL_VEHICLE_COUNT} vehicles with guided random walk routes ---")
    random.seed(SEED)

    vtypes_distribution = {
        "car_aggressive": 0.15, "car_normal": 0.40, "car_conservative": 0.15,
        "truck_light": 0.05, "truck_heavy": 0.15, "bus": 0.08, "motorcycle": 0.02
    }
    type_ids = list(vtypes_distribution.keys())
    probabilities = list(vtypes_distribution.values())
    depart_times = sorted([random.uniform(0, SIMULATION_END_TIME) for _ in range(TOTAL_VEHICLE_COUNT)])

    routes_root = ET.Element("routes")

    # 根据比例，预先为所有车辆选择好它们的“出生地”等级
    start_level_choices = random.choices(
        list(START_EDGE_DISTRIBUTION.keys()),
        weights=list(START_EDGE_DISTRIBUTION.values()),
        k=TOTAL_VEHICLE_COUNT
    )

    for i in range(TOTAL_VEHICLE_COUNT):
        if (i + 1) % 1000 == 0:
            print(f"    Generated routes for {i + 1}/{TOTAL_VEHICLE_COUNT} vehicles...")

        path = []

        # 1. 根据预设比例，在对应等级的道路中选择起点
        start_level = start_level_choices[i]
        if not edge_levels[start_level]: continue
        current_edge = random.choice(edge_levels[start_level])

        # 2. 随机选择一个终点道路，并获取其坐标
        destination_edge = random.choice(all_valid_edges)
        dest_pos = destination_edge.getShape()[-1]

        path.append(current_edge.getID())
        path_length = 1

        while path_length < MAX_PATH_LENGTH:
            if current_edge == destination_edge: break  # 已到达终点

            outgoing = list(current_edge.getOutgoing().keys())
            valid_next_edges = [e for e in outgoing if e in all_valid_edges]  # 确保出口也是有效道路
            if not valid_next_edges: break

            # --- 核心权重计算 ---
            weights = []
            shape = current_edge.getShape()
            if len(shape) < 2: continue
            incoming_angle = get_angle_from_points(shape[-2], shape[-1])
            current_pos = shape[-1]

            for edge in valid_next_edges:
                # a. 基础权重：柔和的宽路倾向
                base_weight = len(edge.getLanes()) ** LANE_COUNT_WEIGHT_FACTOR

                # b. 直行倾向奖励
                edge_shape = edge.getShape()
                if len(edge_shape) < 2: continue
                outgoing_angle = get_angle_from_points(edge_shape[0], edge_shape[1])
                angle_difference = get_angle_diff(incoming_angle, outgoing_angle)

                if angle_difference < 30.0:
                    straight_boost = STRAIGHT_PREFERENCE_BOOST
                elif angle_difference > 160.0:
                    straight_boost = 0.01  # 极力避免掉头
                else:
                    straight_boost = 1.0

                # c. 终点引导奖励
                next_pos = edge.getShape()[-1]
                dist_to_dest_current = get_distance(current_pos, dest_pos)
                dist_to_dest_next = get_distance(next_pos, dest_pos)

                if dist_to_dest_current > 0 and dist_to_dest_next < dist_to_dest_current:
                    distance_gain = (dist_to_dest_current - dist_to_dest_next) / dist_to_dest_current
                    guidance_boost = 1 + distance_gain * DESTINATION_GUIDANCE_BOOST
                else:
                    guidance_boost = 1.0

                # 组合所有权重
                final_weight = base_weight * straight_boost * guidance_boost
                weights.append(final_weight)

            if not weights or sum(weights) == 0: break

            next_edge = random.choices(valid_next_edges, weights=weights, k=1)[0]
            path.append(next_edge.getID())
            current_edge = next_edge
            path_length += 1

        if len(path) > 1:
            chosen_type = random.choices(type_ids, probabilities, k=1)[0]
            vehicle = ET.SubElement(routes_root, "vehicle",
                                    {"id": str(i), "type": chosen_type, "depart": f"{depart_times[i]:.2f}"})
            ET.SubElement(vehicle, "route", {"edges": " ".join(path)})

    # --- Step 3: 写入最终的 .rou.xml 文件 ---
    print(f"\n--- Step 3: Writing final route file ---")
    xml_str = ET.tostring(routes_root, 'utf-8')
    try:
        pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="    ")
        with open(final_route_file, "w", encoding='utf-8') as f:
            f.write(pretty_xml_str)
    except Exception as e:
        print(f"Warning: XML formatting failed, writing raw XML. Error: {e}")
        with open(final_route_file, "w", encoding='utf-8') as f:
            f.write(xml_str.decode('utf-8'))

    print(f"\n--- Ultimate traffic demand generation completed! ---")
    print(f"Final route file saved to: {final_route_file}")


if __name__ == "__main__":
    # 在运行此脚本前，请确保已成功运行最终版的 build_network.py
    main()