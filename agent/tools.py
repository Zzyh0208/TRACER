# 文件路径: E:\py_project\Urban_Cognition_Framework\src\agent\tools.py

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
import statsmodels.api as sm
from statsmodels.tsa.stattools import grangercausalitytests, ccf
import logging


class CausalVerifier:
    def __init__(self, df_log):
        """
        :param df_log: 全局 CSV 数据 (pandas DataFrame, MultiIndex: time, edge_id)
        """
        self.df_log = df_log
        # 确保按时间排序
        self.df_log = self.df_log.sort_index()

    def get_time_series(self, edge_id, metric='speed'):
        """提取某条路的时间序列数据"""
        try:
            # 兼容处理：检查 edge_id 是否存在
            if edge_id not in self.df_log.index.get_level_values('edge_id'):
                return None

            # 提取并重置索引
            df_edge = self.df_log.xs(edge_id, level='edge_id').copy()
            return df_edge[metric].values
        except Exception as e:
            logging.error(f"Error getting series for {edge_id}: {e}")
            return None

    def analyze_propagation(self, source_edge, target_edge, max_lag_seconds=800, sampling_interval=10):
        """
        [核心工具] 互相关分析 (Cross-Correlation)
        用于解决 "传播需要时间" 的问题。自动寻找最佳滞后时间 (Optimal Lag)。

        :param max_lag_seconds: 最大搜索多少秒之前的因果 (针对你提到的600s+，这里设宽一点)
        :param sampling_interval: 数据的采样间隔 (你的数据是10s一次)
        """
        ts_source = self.get_time_series(source_edge)
        ts_target = self.get_time_series(target_edge)

        if ts_source is None or ts_target is None:
            return {"error": "Edge ID not found in logs"}

        # 长度对齐
        min_len = min(len(ts_source), len(ts_target))
        if min_len < 20:  # 数据太少无法分析
            return {"error": "Insufficient data points"}

        ts_source = ts_source[:min_len]
        ts_target = ts_target[:min_len]

        # 检查方差 (如果一条路一直死锁速度为0，方差为0，无法计算相关性)
        if np.std(ts_source) < 0.01 or np.std(ts_target) < 0.01:
            return {
                "result": "No_Variation",
                "max_corr": 0.0,
                "lag_seconds": 0,
                "desc": "One of the edges has constant speed (likely deadlocked or empty)."
            }

        # 计算互相关函数 (CCF)
        # 我们关注 Source(t-k) -> Target(t)，即 Source 领先 Target
        # ccf 返回的是 normalized correlation
        max_lag_steps = int(max_lag_seconds / sampling_interval)

        # 提取 Source 领先的部分
        # statsmodels 的 ccf 默认 forward lag，我们需要小心处理方向
        # 简单做法：手动滑动窗口或用 numpy.correlate
        # 这里使用 numpy 的 full cross-correlation 更直观

        # 标准化
        ts_source_norm = (ts_source - np.mean(ts_source)) / (np.std(ts_source) + 1e-6)
        ts_target_norm = (ts_target - np.mean(ts_target)) / (np.std(ts_target) + 1e-6)

        xcov = np.correlate(ts_target_norm, ts_source_norm, mode='full')
        lags = np.arange(-min_len + 1, min_len)

        # 我们只关心 Lag >= 0 的部分 (Source 发生在前，Target 发生在后)
        mask = (lags >= 0) & (lags <= max_lag_steps)
        valid_lags = lags[mask]
        valid_xcov = xcov[mask] / min_len  # Normalize

        if len(valid_xcov) == 0:
            return {"error": "Lag computation error"}

        # 找到相关性最大的那个时刻
        best_idx = np.argmax(np.abs(valid_xcov))
        max_corr = valid_xcov[best_idx]
        best_lag_steps = valid_lags[best_idx]
        best_lag_seconds = best_lag_steps * sampling_interval

        return {
            "result": "Success",
            "source": source_edge,
            "target": target_edge,
            "max_correlation": round(float(max_corr), 4),
            "optimal_lag_seconds": int(best_lag_seconds),
            "desc": f"Max correlation {round(max_corr, 2)} found at lag {best_lag_seconds}s."
        }

    def verify_granger_causality(self, source_edge, target_edge, max_lag=5):
        """
        [高级工具] 格兰杰因果检验 (Granger Causality)
        这是顶会论文最喜欢的统计检验。
        注意：Granger要求数据平稳，如果数据非平稳可能会有误差，但在Agent中作为参考足够。
        """
        ts_source = self.get_time_series(source_edge)
        ts_target = self.get_time_series(target_edge)

        if ts_source is None or ts_target is None or len(ts_source) < 20:
            return {"p_value": 1.0, "result": "Insufficient Data"}

        # 构造 DataFrame
        data = pd.DataFrame({'target': ts_target, 'source': ts_source})

        # 差分以去除趋势 (使其平稳)
        # 交通速度通常有周期性，一阶差分通常足够
        data_diff = data.diff().dropna()

        # 如果差分后方差太小（完全静止），跳过
        if data_diff.std().min() < 0.01:
            return {"p_value": 0.0, "result": "Static Data (Strong Correlation)"}

        try:
            # 运行检验
            # maxlag: 这里的 lag 是 step 数。对于 10s 采样，maxlag=5 意味着看过去 50s
            # 对于长传播，前面用 analyze_propagation 确定了大致范围，这里做局部因果检验
            gc_res = grangercausalitytests(data_diff, maxlag=[max_lag], verbose=False)

            # 提取 F-test 的 p-value
            p_value = gc_res[max_lag][0]['ssr_ftest'][1]

            return {
                "test": "Granger Causality",
                "lag_steps": max_lag,
                "p_value": round(p_value, 5),
                "is_significant": p_value < 0.05
            }
        except Exception as e:
            return {"p_value": 1.0, "error": str(e)}
        
