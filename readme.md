# PhysRCA: Physics-Grounded Evidence Construction for Zero-Shot Traffic Root Cause Analysis

**PhysRCA** 是一个融合了交通仿真（SUMO）、统计因果推断（Granger Causality）和大语言模型（LLM）代理的交通拥堵根因分析框架。

本项目通过 **"检测 -> 并行诊断 -> 融合推理"** 的流程，利用物理知识（路网拓扑）和统计证据（格兰杰因果检验）辅助 LLM 准确定位交通拥堵的源头。

## 🧠 核心算法逻辑 (Agent & LLM)

PhysRCA 的诊断过程是一个 **"并行假设验证 + 全局融合"** 的过程，代码逻辑主要在 `main.py` 和 `utils.py` 中实现。

### 1. 异常检测与候选生成 (Detector)

* **输入**: 交通流日志 (CSV)。
* **逻辑**: 使用加权检测器算法，结合速度下降率、占有率上升量和车辆数，计算异常分数。
* **输出**: Top-5 异常路段 (Candidates)，作为并行的诊断起点。

### 2. Stage 1: 并行链式诊断 (Parallel Workers)

对 Top-5 中的每一个候选路段，启动一个独立的 Worker 进程（由 `utils.py/worker_process_candidate` 实现）：

1. **链条追踪 (Pruner)**: 使用 `GradientSubgraphRetriever` 从候选点向上游和下游贪婪搜索，构建“拥堵传播链”。
2. **统计验证 (Statistical Check)**:
* 对链条中相邻的节点对（如 ）执行 **Granger Causality Test**。
* 计算 F-score 和 P-value，判断下游拥堵是否是导致上游拥堵的统计学原因。


3. **LLM 单链推理**:
* 将 **链条数据** + **Granger 统计证据** 填入 `SYSTEM_PROMPT_STAGE1`。
* LLM 输出该链条内的潜在根因及置信度。



### 3. Stage 2: 全局融合推理 (Fusion)

所有 Worker 完成后，进入融合阶段（由 `main.py/perform_fusion_analysis` 实现）：

* **输入**: 5 条链条的诊断结果摘要。
* **融合逻辑**:
* **同链去重**: 如果单条链内重复报告，取最高置信度。
* **异链叠加**: 如果不同链条指向同一个根因 (Edge ID)，则**累加**其 Impact Score（车辆影响数）。这是因为多条独立证据链指向同一源头增强了证据力度。


* **输出**: 最终的根因排名列表。

## 🚦 仿真环境构建 (Simulation)

在运行分析前，需要构建高质量的仿真场景。`simulation/` 目录下的脚本构成了一个闭环工作流：

1. **路网构建 (Steps 1-3)**:
* `step1`: 下载 OSM 数据生成基础路网。
* `step2`: 自动识别连接数  的复杂路口。
* `step3`: 强制将这些路口升级为信号灯控制，生成 `xian_north_final.net.xml`。


2. **需求生成**: `generate_demand.py` 基于路网等级（主干道/次干道）生成带有直行倾向和终点引导的随机车流。
3. **设施铺设**: `generate_detectors.py` 自动铺设 E1 检测器和感应线圈。
4. **故障模拟**: `simulator.py` 支持注入车道封锁 (Blockage)、信号灯全红 (All-Red) 和道路损毁 (Road Damage) 故障。

## 🚀 快速开始

### 1. 环境准备

确保安装 SUMO 和 Python 依赖：

```bash
# 设置 SUMO_HOME 环境变量 (根据你的安装路径)
export SUMO_HOME="/path/to/sumo"

# 安装 Python 库
pip install numpy pandas scipy statsmodels networkx traci sumolib requests tqdm

```

### 2. 构建仿真场景

按顺序执行脚本生成数据（或编写 shell 脚本批量执行）：

```bash
cd src/simulation
python step1_build_base_network.py
python step2_find_major_junctions.py
python step3_build_final_network.py
python generate_demand.py
python generate_detectors.py
# 此时 data/ 目录下会生成完整的路网文件

```

### 3. 运行根因分析 (RCA)

配置你的 API Key：
打开 `src/config_and_prompts.py`，填入 `OPENROUTER_API_KEY`。

执行主程序：

```bash
cd src
python main.py

```

程序将自动：

1. 加载路网图 (`graph_builder`).
2. 读取 `data/dataset_raw` 下的 CSV 日志。
3. 并行启动 5 个 Worker 分析 Top-5 异常点。
4. 调用 LLM 进行 Stage 2 融合。
5. 输出结果到 `results/` 目录。

## ⚙️ 配置说明

在 `src/config_and_prompts.py` 中可调整关键参数：

* `MODELS_TO_TEST`: 待评测的大模型列表。
* `DIAGNOSIS_TIME`: 诊断切片时间点。
* `TOP_K_AGENT`: 并行分析的候选节点数量（默认 5）。
* `SYSTEM_PROMPT_STAGE1/2`: 调整提示词策略。