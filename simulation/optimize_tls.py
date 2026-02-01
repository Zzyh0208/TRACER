import os
import subprocess
import sys

# --- 配置区域 ---
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
data_path = f"../../data/{NETWORK_NAME}"
net_file = f"{data_path}/{NETWORK_NAME}.net.xml"
route_file = f"{data_path}/{NETWORK_NAME}.rou.xml"

tls_adapter_script_path = os.path.join(sumo_home, 'tools', 'tlsCycleAdaptation.py')


def run_command(command):
    """(最终版) 辅助函数"""
    print(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, errors='ignore')
        print("Success.")
        if result.stdout:
            print(f"Output:\n{result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}")
        print(f"Error Output:\n{e.stderr}")
        sys.exit(1)


def main():
    """主流程函数 (为您本地环境定制)"""
    print(f"--- Step 1: Optimizing traffic lights based on route file data ---")

    # 这个版本不需要检查 detector_output_file

    # <<< 关键修改点：只使用您版本支持的参数 >>>
    final_tls_adapter_cmd = [
        sys.executable,
        tls_adapter_script_path,
        '-n', net_file,
        '-r', route_file,
        '-b', '300',
        '-g', '5',
        '--max-cycle', '120'
    ]

    run_command(final_tls_adapter_cmd)

    print("\n--- Traffic light optimization completed! ---")


if __name__ == "__main__":
    main()