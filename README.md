# COROS 训练仪表板

基于 COROS Team API 的训练数据可视化面板，支持 Streamlit Cloud 一键部署。

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/deploy?repository=nametoa/ai-sport-training&branch=master&mainModule=streamlit_app.py)

## 功能

- **仪表板** — VO2max、训练负荷、HRV、静息心率等关键指标总览
- **数据分析** — 每日负荷、配速/心率区间分布、强度趋势等多维图表（支持 2/3/4 列布局）
- **活动列表** — 所有运动记录，支持按类型筛选和排序
- **训练计划** — 混合训练（Concurrent Training）周计划，含每日 Todolist 和 COROS 数据自动打卡

## 一键部署到 Streamlit Cloud

1. Fork 本仓库到你的 GitHub
2. 打开 [share.streamlit.io](https://share.streamlit.io)，点击 **New app**
3. 选择你 Fork 的仓库，分支选 `master`，主文件填 `streamlit_app.py`
4. 点击 **Advanced settings → Secrets**，粘贴以下内容（替换为你的 COROS 凭据）：

```toml
[coros]
access_token = "YOUR_COROS_ACCESS_TOKEN"
user_id = "YOUR_COROS_USER_ID"
cookie_wbkfro = "YOUR_COOKIE_WBKFRO_VALUE"
cookie_region = "2"
base_url = "https://teamcnapi.coros.com"
```

5. 点击 **Deploy** 即可

### 如何获取 COROS 凭据

1. 打开 [t.coros.com](https://t.coros.com) 并登录
2. 按 F12 打开浏览器开发者工具 → Network 标签
3. 刷新页面，找到任意发往 `teamcnapi.coros.com` 的请求
4. 从请求头中复制：
   - `accesstoken` → 填入 `access_token`
   - `yfheader` 中的 `userId` → 填入 `user_id`
   - Cookie 中的 `_c_WBKFRo` → 填入 `cookie_wbkfro`

## 本地运行

```bash
pip install -r requirements.txt

# 方式1: 直接运行（使用脚本内的默认凭据）
python3 -m streamlit run streamlit_app.py

# 方式2: 使用 secrets 配置
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# 编辑 .streamlit/secrets.toml 填入你的凭据
python3 -m streamlit run streamlit_app.py
```

应用启动时会自动同步最新 COROS 数据。

## 项目结构

```
├── streamlit_app.py          # Streamlit 主应用
├── fetch_coros_data.py       # COROS API 数据拉取（增量更新）
├── ai_coach_prompt.md        # AI 教练提示词
├── requirements.txt          # Python 依赖
├── .streamlit/
│   ├── config.toml           # Streamlit 主题配置
│   └── secrets.toml.example  # Secrets 模板
└── data/                     # 运行时数据目录（自动创建）
```
