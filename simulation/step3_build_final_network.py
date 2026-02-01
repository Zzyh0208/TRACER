# src/simulation/step3_build_final_network.py

import os
import subprocess
import sys

# --- 配置区域 ---
BOUNDS = "108.91296,34.31041,108.99227,34.35605"
NETWORK_NAME = "xian_north_final"

# --- 检查SUMO环境变量 ---
sumo_home = ""
if 'SUMO_HOME' in os.environ:
    sumo_home = os.environ['SUMO_HOME']
    tools = os.path.join(sumo_home, 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

# --- 定义文件路径 ---
output_path = f"../../data/{NETWORK_NAME}"
if not os.path.exists(output_path):
    os.makedirs(output_path)

osm_file_prefix = f"{output_path}/{NETWORK_NAME}"
osm_file = f"{osm_file_prefix}_bbox.osm.xml"
# 这个脚本将覆盖由 step1 生成的路网文件
net_file = f"{output_path}/{NETWORK_NAME}.net.xml"
osm_get_script_path = os.path.join(sumo_home, 'tools', 'osmGet.py')
# 这个脚本依赖于 step2 生成的侦察结果文件
major_junction_ids_file = f"{output_path}/major_junction_ids.txt"


def run_command(command):
    """(最终版) 辅助函数：运行命令行指令，并提供鲁棒的错误处理和输出。"""
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, errors='ignore')
        print("Success.")
        if result.stdout:
            print(f"Output:\n{result.stdout[:1500]}...")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}")
        print(f"Error Output:\n{e.stderr}")
        sys.exit(1)


def main():
    """
    主流程函数：
    1. (可选) 重新下载OSM数据以确保最新。
    2. 读取侦察到的关键路口ID列表。
    3. 调用netconvert，使用--tls.set参数强制生成信号灯，并应用所有优化。
    """

    # --- Step 1: 确保OSM数据存在 ---
    print("--- Step 1: Ensuring OSM data is available ---")
    if not os.path.exists(osm_file):
        print(f"OSM file not found at {osm_file}. Running osmGet.py to download.")
        osm_get_cmd = [sys.executable, osm_get_script_path, '-b', BOUNDS, '-p', osm_file_prefix]
        run_command(osm_get_cmd)
    else:
        print(f"OSM data file already exists.")
    print(f"Using OSM data at: {osm_file}")

    # --- Step 2: 构造最终的、带有强制信号灯的netconvert命令 ---
    print("\n--- Step 2: Constructing and running the final netconvert command with forced TLS ---")

    # 定义基础的、共享的优化参数
    base_optimization_params = [
        '--keep-edges.by-type', 'highway.motorway,highway.trunk,highway.primary,highway.secondary,highway.tertiary',
        '--remove-edges.by-type', 'highway.track,highway.path,highway.footway,highway.cycleway,highway.pedestrian',
        '--remove-edges.isolated',
        '--geometry.remove',
        '--junctions.join',
        '--junctions.join-dist', '50',
        '--tls.guess-signals',
        '--tls.join',
        '--tls.default-type', 'actuated',
        '--verbose'
    ]

    # 构造命令列表
    netconvert_cmd = ['netconvert', '--osm-files', osm_file, '-o', net_file]

    # 将基础优化参数添加到命令中
    netconvert_cmd.extend(base_optimization_params)

    # --- 核心逻辑：读取侦察文件并强制生成信号灯 ---
    if os.path.exists(major_junction_ids_file):
        with open(major_junction_ids_file, 'r') as f:
            # 读取所有ID，去掉换行符，并用逗号连接成一个字符串
            junction_ids_str = ",".join([line.strip() for line in f if line.strip()])

        if junction_ids_str:
            print(f"Found {len(junction_ids_str.split(','))} major junctions to be forced into traffic lights.")
            # 使用 extend 一次性添加 --tls.set 参数和它的值
            netconvert_cmd.extend(['--tls.set', junction_ids_str])
        else:
            print("Warning: major_junction_ids.txt is empty. No junctions will be forced.")
    else:
        print("Warning: major_junction_ids.txt not found. Running without forcing any TLS.")
        print("Please run step2_find_major_junctions.py first for best results.")

    # --- 执行最终的命令 ---
    run_command(netconvert_cmd)

    print("\n--- Final network build process with forced TLS completed! ---")
    print(f"The final, intelligent, and fully covered network is saved to: {net_file}")


if __name__ == "__main__":
    main()