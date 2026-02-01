import os
import sys
import sumolib

# --- 配置区域 ---
NETWORK_NAME = "xian_north_final"
# 我们只关心主干道和次干道相交形成的路口
MIN_CONNECTIONS_FOR_TLS = 3 # 设为4，意味着所有十字路口及更复杂的路口都会被选中
MAJOR_ROAD_TYPES = [
    'highway.motorway',
    'highway.trunk',
    'highway.primary',
    'highway.secondary'
]

# --- 定义文件路径 ---
data_path = f"../../data/{NETWORK_NAME}"
net_file = f"{data_path}/{NETWORK_NAME}.net.xml"
output_junction_ids_file = f"{data_path}/major_junction_ids.txt"


def main():
    """
    (终极版) 分析路网，找出所有足够复杂（例如十字路口）的、但当前不是信号灯的路口。
    """
    print(f"--- Loading network from {net_file} to find all complex junctions to upgrade ---")
    net = sumolib.net.readNet(net_file)
    junctions_to_upgrade = set()

    for junction in net.getNodes():
        # 我们只关心那些当前不是信号灯的路口
        if junction.getType() != 'traffic_light':

            # <<< 核心优化：根据连接数判断，而不是道路类型！>>>
            # 获取进入和离开该路口的所有道路连接数
            num_connections = len(junction.getIncoming()) + len(junction.getOutgoing())

            # 如果连接数达到我们的阈值，就判定为需要升级
            if num_connections >= MIN_CONNECTIONS_FOR_TLS:
                junctions_to_upgrade.add(junction.getID())

    print(
        f"Found {len(junctions_to_upgrade)} complex junctions to be forced into traffic lights (based on >= {MIN_CONNECTIONS_FOR_TLS} connections).")

    with open(output_junction_ids_file, "w") as f:
        for jid in sorted(list(junctions_to_upgrade)):
            f.write(f"{jid}\n")

    print(f"Junction IDs to upgrade saved to: {output_junction_ids_file}")


if __name__ == "__main__":
    main()