"""
title: COROS AI 教练
author: nametoa
version: 0.2.0
license: MIT
description: 从 GitHub 仓库读取 COROS 训练数据，作为 AI 混合训练教练的上下文。部署到 Open WebUI → Functions → 添加。
"""

import os
import time
import urllib.request
import json
from typing import Optional
from pydantic import BaseModel, Field


class Filter:
    """Open WebUI Filter – 在用户消息前注入最新训练数据上下文。"""

    class Valves(BaseModel):
        github_owner: str = Field(default="nametoa", description="GitHub 用户名")
        github_repo: str = Field(default="ai-sport-training", description="GitHub 仓库名")
        github_branch: str = Field(default="main", description="分支名")
        knowledge_files: str = Field(
            default="knowledge/02_每日身体指标.md,knowledge/03_周训练统计.md,knowledge/04_当前训练计划.md",
            description="要读取的知识库文件（逗号分隔），路径相对于仓库根目录",
        )
        github_token: str = Field(default="", description="GitHub Token（私有仓库需要，公开仓库留空）")
        cache_ttl_seconds: int = Field(default=3600, description="缓存有效期（秒），默认 1 小时")
        system_prompt: str = Field(
            default="""你是一位专业的【混合训练教练（Concurrent Training Specialist）】，
同时兼顾：专业跑步教练 + 力量训练教练 + 运动营养顾问。

你的学员是一位 35 岁男性程序员，身高 175cm / 体重 70kg / 体脂 14%，
混合训练 8 年，全马 PB 2:52:28，三大项 360kg（卧推 90 / 深蹲 140 / 硬拉 130）。

你的核心职责：
1. 基于下方提供的 COROS 手表训练数据，给出数据驱动的分析和建议
2. 合理安排力量训练和跑步训练的顺序与强度，避免干扰效应
3. 在保证健康、避免伤病的前提下，帮助学员达成比赛目标
4. 回答时引用具体数据（心率、配速、训练负荷、HRV 等）

回答风格：
- 简洁专业，像真实教练一样直接给建议
- 给出建议时说明原因（生理学依据）
- 涉及训练安排时精确到配速/心率/组数
- 发现数据异常（如 HRV 骤降、训练负荷过高）主动提醒""",
            description="AI 教练系统提示词",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._cache: dict[str, tuple[float, str]] = {}

    def _fetch_github_file(self, file_path: str) -> str:
        """从 GitHub 获取文件内容（带缓存）。"""
        cache_key = file_path
        now = time.time()

        # 检查缓存
        if cache_key in self._cache:
            cached_time, cached_content = self._cache[cache_key]
            if now - cached_time < self.valves.cache_ttl_seconds:
                return cached_content

        # URL encode 中文路径
        encoded_path = urllib.request.pathname2url(file_path)
        url = (
            f"https://raw.githubusercontent.com/"
            f"{self.valves.github_owner}/{self.valves.github_repo}/"
            f"{self.valves.github_branch}/{encoded_path}"
        )

        headers = {"User-Agent": "Open-WebUI-COROS-Coach"}
        if self.valves.github_token:
            headers["Authorization"] = f"token {self.valves.github_token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
                self._cache[cache_key] = (now, content)
                return content
        except Exception as e:
            return f"[读取 {file_path} 失败: {e}]"

    def _build_context(self) -> str:
        """拉取所有知识库文件，拼接为上下文。"""
        files = [f.strip() for f in self.valves.knowledge_files.split(",") if f.strip()]
        parts = []
        for file_path in files:
            content = self._fetch_github_file(file_path)
            parts.append(content)
        return "\n\n---\n\n".join(parts)

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """在请求发送给 LLM 之前注入训练数据上下文。"""
        messages = body.get("messages", [])

        # 注入系统提示词  
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            messages.insert(0, {
                "role": "system",
                "content": self.valves.system_prompt,
            })

        # 只在用户第一条消息时注入数据上下文（避免重复）
        user_msg_count = sum(1 for m in messages if m.get("role") == "user")
        if user_msg_count == 1:
            context = self._build_context()
            context_msg = {
                "role": "system",
                "content": (
                    "以下是学员最新的 COROS 训练数据，请基于这些数据回答问题：\n\n"
                    + context
                ),
            }
            # 插入到 system prompt 之后、user 消息之前
            for i, m in enumerate(messages):
                if m.get("role") == "user":
                    messages.insert(i, context_msg)
                    break

        body["messages"] = messages
        return body
