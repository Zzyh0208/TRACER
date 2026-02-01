#!/bin/bash

# ==========================================
# PhysRCA Simulation Environment Builder
# ==========================================

# 设置项目根目录 (假设脚本在项目根目录下运行)
PROJECT_ROOT=$(pwd)
SIM_DIR="$PROJECT_ROOT/simulation"

echo "========================================"
echo "Starting PhysRCA Environment Build"
echo "Project Root: $PROJECT_ROOT"
echo "========================================"

# 检查 Python 是否安装
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH."
    exit 1
fi

# 检查 SUMO_HOME
if [ -z "$SUMO_HOME" ]; then
    echo "Error: SUMO_HOME environment variable is not set."
    exit 1
fi

# 进入 simulation 目录，因为脚本中的相对路径 (../../data) 依赖于执行位置
cd "$SIM_DIR" || { echo "Error: Could not output to simulation directory"; exit 1; }

# 定义一个辅助函数来运行脚本并检查错误
run_step() {
    echo ""
    echo "----------------------------------------"
    echo ">>> Running: $1"
    echo "----------------------------------------"
    python "$1"
    
    if [ $? -ne 0 ]; then
        echo "❌ Error: $1 failed execution."
        exit 1
    else
        echo "✅ Success: $1 completed."
    fi
}

# --- 1. 构建基础路网 ---
run_step "step1_build_base_network.py"

# --- 2. 侦察复杂路口 ---
run_step "step2_find_major_junctions.py"

# --- 3. 构建最终路网 (强制信号灯) ---
run_step "step3_build_final_network.py"

# --- 4. 生成交通需求 ---
run_step "generate_demand.py"

# --- 5. 优化信号灯配时 ---
# 注意：这需要依赖生成的 route 文件
run_step "optimize_tls.py"

# --- 6. 生成检测器 ---
run_step "generate_detectors.py"

echo ""
echo "========================================"
echo "🎉 All simulation environment files built successfully!"
echo "Files are located in: $PROJECT_ROOT/data/xian_north_final/"
echo "========================================"

# 返回原始目录
cd "$PROJECT_ROOT"