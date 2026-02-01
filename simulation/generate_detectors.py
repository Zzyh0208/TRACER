import os
import sys
import sumolib

# --- 配置区域 ---
NETWORK_NAME = "xian_north_final"

# --- 文件定义 ---
data_path = f"../../data/{NETWORK_NAME}"
net_file = f"{data_path}/{NETWORK_NAME}.net.xml"
# 我们将把所有检测器都写入同一个文件，由SUMO统一加载
detectors_file = f"{data_path}/{NETWORK_NAME}.add.xml"
e1_output_file = f"{data_path}/{NETWORK_NAME}.e1.out.xml"


def main():
    """(最终集成版) 在一次遍历中生成所有类型的检测器"""
    print(f"--- Loading network from {net_file} ---")
    net = sumolib.net.readNet(net_file)

    # 打开一个XML文件用于写入所有附加定义
    with open(detectors_file, "w") as f:
        f.write("<additional>\n")

        e1_count = 0
        loop_count = 0

        # --- 一次遍历，完成所有工作 ---
        # 我们只遍历所有道路(edge)一次
        for edge in net.getEdges():
            # 过滤掉非普通道路
            if edge.getFunction() in ['internal', 'connector']:
                continue

            # 检查这条道路的终点是否是信号灯路口
            to_junction = edge.getToNode()
            if to_junction.getType() != "traffic_light":
                continue

            # 如果是，那么这条路上的所有车道都是我们的目标
            for lane in edge.getLanes():
                lane_id = lane.getID()
                lane_length = lane.getLength()

                # 1. 生成用于我们算法分析的 e1Detector
                pos_e1 = lane_length - 100  # 放在距路口100米处
                if pos_e1 > 0:
                    f.write(
                        f'    <e1Detector id="e1_{lane_id}" lane="{lane_id}" pos="{pos_e1}" freq="60" file="{e1_output_file}"/>\n')
                    e1_count += 1

                # 2. 生成用于感应式信号灯的 InductionLoop
                pos_loop = lane_length - 5  # 放在距路口5米处
                if pos_loop > 0:
                    det_id = f"det_{lane_id}"
                    f.write(
                        f'    <inductionLoop id="{det_id}" lane="{lane_id}" pos="{pos_loop}" freq="900" file="NUL"/>\n')
                    loop_count += 1

        f.write("</additional>\n")

    print(f"Generated {e1_count} e1Detectors for analysis.")
    print(f"Generated {loop_count} induction loops for actuated traffic lights.")
    print(f"\n--- All detectors saved to single file: {detectors_file} ---")


if __name__ == "__main__":
    main()