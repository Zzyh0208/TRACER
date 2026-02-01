# PhysRCA: Physics-Grounded Evidence Construction for Zero-Shot Traffic Root Cause Analysis

**PhysRCA** 是一个结合了交通仿真（SUMO）、因果推断（Granger Causality）和大语言模型（LLM）代理的根因分析框架。该项目旨在通过构建包含物理约束（路网拓扑、交通流理论）的因果图，解决城市交通网络中的复杂拥堵溯源问题。

## 📁 目录结构

PhysRCA/
├── agent/
│   └── tools.py               # 核心因果分析工具 (CCF, Granger Causality)
├── graph/
│   ├── graph_builder.py       # SUMO路网解析与 NetworkX 图构建
│   └── pruner.py              # 基于梯度的子图检索与拥堵链追踪
├── simulation/
│   ├── step1_build_base_network.py   # 步骤1：构建基础侦察路网
│   ├── step2_find_major_junctions.py # 步骤2：识别需升级的复杂路口
│   ├── step3_build_final_network.py  # 步骤3：生成带强制信号灯的最终路网
│   ├── generate_demand.py            # 生成基于引导式随机游走的交通需求
│   ├── generate_detectors.py         # 生成全路网检测器 (E1 & Induction Loops)
│   ├── optimize_tls.py               # 基于流量的信号灯周期优化
│   └── simulator.py                  # SUMO 仿真控制器与故障注入引擎 (Blockage, Road Damage, TLS Fault)
└── data/                      # 存放路网、日志和配置文件的目录


## 🚀 快速开始

### 1. 环境依赖

确保已安装 [SUMO (Simulation of Urban MObility)](https://eclipse.dev/sumo/) 并配置了 `SUMO_HOME` 环境变量。

安装 Python 依赖：

```bash
pip install numpy pandas scipy statsmodels networkx traci sumolib

```

### 2. 构建仿真环境 (Pipeline)

本项目采用独特的 **"Reconnaissance-Upgrade" (侦察-升级)** 流程来构建高质量路网。

执行提供的 Shell 脚本可一键完成所有准备工作：

```bash
# 在 Windows Git Bash 或 Linux 环境下
chmod +x build_simulation.sh
./build_simulation.sh

```

**手动执行步骤说明：**

1. **构建基础路网** (`step1`): 下载 OSM 数据并生成无干预的基础路网。
2. **路口侦察** (`step2`): 分析基础路网，找出连接数 >= 3 但未配置信号灯的复杂路口。
3. **构建最终路网** (`step3`): 读取 Step 2 的结果，强制生成信号灯并应用高级优化，生成最终 `.net.xml`。
4. **生成需求** (`generate_demand`): 基于路网分级（主干道/次干道）生成符合物理规律的交通流。
5. **信号灯优化** (`optimize_tls`): 根据生成的车流优化信号灯周期。
6. **部署检测器** (`generate_detectors`): 在所有相关车道铺设 E1 检测器和感应线圈。

### 3. 运行根因分析

路网构建完成后，您需要编写一个主入口脚本来调用 `simulation/simulator.py` 运行仿真，并利用 `agent` 和 `graph` 模块进行分析。

**核心模块说明：**

* **RoadGraphManager**: 将 `.net.xml` 转换为 NetworkX 有向图，用于拓扑分析。
* **GradientSubgraphRetriever**: 当检测到异常时，从中心节点向上下游贪婪搜索，构建“拥堵传播链”。
* **CausalVerifier**: 对提取的传播链进行统计检验：
* `analyze_propagation`: 计算互相关 (CCF) 以确定传播滞后时间。
* `verify_granger_causality`: 执行格兰杰因果检验，验证拥堵传播的因果显著性 (P-value)。



## 🛠️ 故障注入 (Fault Injection)

`SumoSimulator` 类提供了三种物理故障注入方法，用于生成测试数据：

1. `inject_lane_blockage`: 模拟车道物理遮挡（捕鼠夹模式，强制捕获车辆）。
2. `inject_traffic_light_all_red`: 模拟信号灯故障（全红死锁）。
3. `inject_road_damage`: 模拟道路损毁（强制降低限速）。