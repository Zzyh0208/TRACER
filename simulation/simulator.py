import os
import sys
import traci
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SumoSimulator:
    def __init__(self, sumocfg_path, use_gui=True):
        self.sumocfg_path = sumocfg_path
        self.use_gui = use_gui
        self.step_count = 0
        self.active_faults = []

        if 'SUMO_HOME' in os.environ:
            tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
            if tools not in sys.path:
                sys.path.append(tools)
        else:
            sys.exit("请声明环境变量 'SUMO_HOME'")

    def start(self):
        sumo_binary = "sumo-gui" if self.use_gui else "sumo"
        cmd = [sumo_binary, "-c", self.sumocfg_path, "--start", "--no-warnings", "--no-step-log"]
        logging.info(f"正在启动 SUMO: {' '.join(cmd)}")
        traci.start(cmd)
        self.step_count = 0

    def step(self):
        try:
            traci.simulationStep()
            self.step_count += 1
            # 持续运行捕鼠夹逻辑
            self._update_incremental_blockage()
            return self.step_count
        except traci.TraCIException:
            logging.error("TraCI 连接在 step() 中断开，仿真可能已崩溃。")
            return -1

    def close(self):
        try:
            traci.close()
        except:
            pass
        logging.info("仿真结束。")

    def get_time(self):
        try:
            return traci.simulation.getTime()
        except:
            return 0

    # ==========================
    # 辅助逻辑
    # ==========================
    def _update_incremental_blockage(self):
        """持续捕获车辆，保证每条道堵3辆"""
        for fault in self.active_faults:
            if fault["type"] == "blockage":
                if self.get_time() >= fault["end_time"]:
                    continue

                for lane_id, trapped_vehs in fault["lane_status"].items():
                    if len(trapped_vehs) < 3:
                        try:
                            # 倒序遍历，优先抓车头
                            current_vehs = traci.lane.getLastStepVehicleIDs(lane_id)
                            for veh in reversed(current_vehs):
                                if veh not in trapped_vehs:
                                    self._freeze_vehicle(veh)
                                    trapped_vehs.append(veh)
                                    logging.info(f"  [捕鼠夹] 在 {lane_id} 捕获车辆 {veh} ({len(trapped_vehs)}/3)")
                                    if len(trapped_vehs) >= 3:
                                        break
                        except:
                            pass

    def _freeze_vehicle(self, veh_id):
        try:
            traci.vehicle.setSpeedMode(veh_id, 0)
            traci.vehicle.setSpeed(veh_id, 0)
            traci.vehicle.setColor(veh_id, (255, 0, 255, 255))  # 洋红色
        except:
            pass

    def _release_vehicle(self, veh_id):
        try:
            traci.vehicle.setSpeedMode(veh_id, 31)
            traci.vehicle.setSpeed(veh_id, -1)
            traci.vehicle.setColor(veh_id, (255, 255, 255, 255))
        except:
            pass

    # ==========================
    # 故障注入 API (修复版 v7.0)
    # ==========================

    def inject_lane_blockage(self, edge_id, duration=300):
        """[异常 1] 持续捕获型连环车祸"""
        logging.info(f"正在初始化 Edge {edge_id} 的捕鼠夹 (目标: 3车/道)...")
        try:
            num_lanes = traci.edge.getLaneNumber(edge_id)
        except:
            logging.error(f"找不到 Edge: {edge_id}")
            return None

        lane_status = {}
        for i in range(num_lanes):
            lane_status[f"{edge_id}_{i}"] = []

        self.active_faults.append({
            "type": "blockage",
            "edge_id": edge_id,
            "lane_status": lane_status,
            "end_time": self.get_time() + duration
        })

        self._update_incremental_blockage()  # 立即执行一次

        return {
            "type": "blockage",
            "edge_id": edge_id,
            "start_time": self.get_time(),
            "duration": duration
        }

    def inject_traffic_light_all_red(self, tls_id, duration=300):
        """[异常 2] 红绿灯全红"""
        try:
            traci.trafficlight.getPhase(tls_id)
            original_program = traci.trafficlight.getProgram(tls_id)
            state_len = len(traci.trafficlight.getRedYellowGreenState(tls_id))

            traci.trafficlight.setRedYellowGreenState(tls_id, "r" * state_len)

            logging.info(f">>> [故障注入成功] TLS All-Red: {tls_id}")
            self.active_faults.append({
                "type": "tls_all_red",
                "tls_id": tls_id,
                "end_time": self.get_time() + duration,
                "original_program": original_program
            })
            return {"type": "tls_all_red", "tls_id": tls_id, "start_time": self.get_time(), "duration": duration}
        except Exception as e:
            logging.error(f"TLS注入失败: {e}")
            return None

    def inject_road_damage(self, edge_id, duration=300, speed_limit=1.0):
        """
        [异常 3] 道路损毁 (API 修复版)
        使用 traci.lane.setMaxSpeed 替代不存在的 traci.edge.setMaxSpeed
        """
        logging.info(f"正在注入道路损毁: Edge {edge_id}, 限速降为 {speed_limit}m/s")

        try:
            # 1. 获取车道数
            num_lanes = traci.edge.getLaneNumber(edge_id)

            # 2. 获取原始限速 (取第0条车道即可，通常一样)
            first_lane = f"{edge_id}_0"
            original_speed = traci.lane.getMaxSpeed(first_lane)

            # 3. 遍历所有车道，设置新限速
            for i in range(num_lanes):
                lane_id = f"{edge_id}_{i}"
                traci.lane.setMaxSpeed(lane_id, speed_limit)

                # 视觉增强：把当前在上面的车变黄
                vehs = traci.lane.getLastStepVehicleIDs(lane_id)
                for v in vehs:
                    try:
                        traci.vehicle.setColor(v, (255, 255, 0, 255))
                    except:
                        pass

            self.active_faults.append({
                "type": "road_damage",
                "edge_id": edge_id,
                "num_lanes": num_lanes,
                "original_speed": original_speed,
                "end_time": self.get_time() + duration
            })

            return {
                "type": "road_damage",
                "edge_id": edge_id,
                "speed_limit": speed_limit,
                "start_time": self.get_time(),
                "duration": duration
            }

        except Exception as e:
            logging.error(f"Road Damage 注入失败: {e}")
            return None

    def check_and_recover_faults(self):
        current_time = self.get_time()

        for fault in self.active_faults[:]:
            if current_time >= fault["end_time"]:
                # 恢复 Blockage
                if fault["type"] == "blockage":
                    for lane_id, veh_list in fault["lane_status"].items():
                        for veh in veh_list:
                            self._release_vehicle(veh)
                    logging.info(f"<<< [故障恢复] 连环事故清理完毕。Edge: {fault['edge_id']}")

                # 恢复 TLS
                elif fault["type"] == "tls_all_red":
                    try:
                        traci.trafficlight.setProgram(fault["tls_id"], fault["original_program"])
                        logging.info(f"<<< [故障恢复] TLS {fault['tls_id']} 恢复。")
                    except:
                        pass

                # 恢复 Road Damage (修复版)
                elif fault["type"] == "road_damage":
                    try:
                        edge_id = fault["edge_id"]
                        orig_speed = fault["original_speed"]
                        # 遍历所有车道恢复限速
                        for i in range(fault["num_lanes"]):
                            lane_id = f"{edge_id}_{i}"
                            traci.lane.setMaxSpeed(lane_id, orig_speed)
                        logging.info(f"<<< [故障恢复] 道路维修结束，限速恢复。Edge: {edge_id}")
                    except:
                        pass

                self.active_faults.remove(fault)