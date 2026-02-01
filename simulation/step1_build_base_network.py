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
net_file = f"{output_path}/{NETWORK_NAME}.net.xml"
osm_get_script_path = os.path.join(sumo_home, 'tools', 'osmGet.py')


def run_command(command):
    """(最终版) 辅助函数"""
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
    """主流程函数 (基础侦察版)"""

    # --- Step 1: 下载OSM数据 ---
    print("--- Step 1: Downloading OSM data ---")
    osm_get_cmd = [
        sys.executable,
        osm_get_script_path,
        '-b', BOUNDS,
        '-p', osm_file_prefix
    ]
    if not os.path.exists(osm_file):
        run_command(osm_get_cmd)
    else:
        print(f"OSM data file already exists, skipping download.")
    print(f"OSM data should be at: {osm_file}")

    # --- Step 2: 生成一个基础的、未经强制干预的路网 ---
    print("\n--- Step 2: Generating a baseline optimized network ---")

    # 这个版本不包含任何 --tls.set 的逻辑
    netconvert_cmd = [
        'netconvert',
        '--osm-files', osm_file,
        '-o', net_file,

        # --- 核心优化参数 ---
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
    run_command(netconvert_cmd)

    print("\n--- Baseline network build completed! ---")
    print(f"This network is for reconnaissance purposes. File saved to: {net_file}")


if __name__ == "__main__":
    main()