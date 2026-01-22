# core/agent_engine.py
import os
import json
import re
from google import genai
from google.genai import types # 💡 引入类型定义
from typing import Dict, Any, List, Union

class AgentEngine:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("未检测到 GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_id = "gemini-2.0-flash" 

    def get_action_from_text(self, user_input: str, workflow_summary: str) -> Union[Dict, List]:
        system_prompt = f"""
你是一个专业的视频导演助理。你必须根据用户需求生成工作流修改指令。

[当前工作流状态摘要]
{workflow_summary}

[指令逻辑规范 - 极其重要]
1. 修改全局风格: {{"op": "set_global_style", "value": "英文风格描述词"}}
   - 🎨 风格强控：必须使用强力动词来确保 AI 大胆变换风格，例如：
     * "Total transformation into Cyberpunk Neon style"
     * "Hyper-stylized in Studio Ghibli anime aesthetic"
     * "Complete visual overhaul with Film Noir cinematography"
   - 禁止使用保守词汇如 "slightly", "subtle", "minor"

2. 全局主体替换: {{"op": "global_subject_swap", "old_subject": "英文原词", "new_subject": "英文新词"}}
   - 方向逻辑："把 A 换成 B"意味着 A 是旧的(old)，B 是新的(new)。
   - 匹配要求：你必须观察 [摘要] 中的 Shot Descriptions，找出其中真正存在的英文单词作为 "old_subject"。
   - 翻译要求：如果用户说"男人"，而摘要里是 "man"，请使用 "man"；如果用户说"小孩"，请翻译为 "child"。

3. 增强分镜描述: {{"op": "enhance_shot_description", "shot_id": "shot_XX", "spatial_info": "空间位置描述", "style_boost": "风格强化描述"}}
   - 📐 空间感知：必须分析原图构图，添加精确的空间位置描述：
     * "subject positioned on the left side of the frame"
     * "character facing right, looking towards camera"
     * "object in the foreground, background blurred"
     * "centered composition with symmetrical framing"
   - 🎬 风格强化：添加强力变换指令：
     * "Total transformation required"
     * "Hyper-stylized rendering"
     * "Complete aesthetic overhaul"

[输出要求]
- 必须识别用户的所有意图。
- 必须返回一个包含指令对象的 JSON 列表 []，即使只有一条指令也要放在列表里。
- 严禁输出任何解释性文字，只输出纯 JSON 字符串。
- 当用户要求更改风格时，必须使用强力动词，禁止保守表达。
"""
        try:
            # 💡 强制 JSON 模式，确保输出结构稳定
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[system_prompt, f"用户指令: {user_input}"],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                )
            )
            
            # 自动解析 JSON 字符串
            res_json = json.loads(response.text)
            
            # 调试日志：在终端打印 Agent 的决策逻辑
            print(f"🤖 Agent 决策指令集: {res_json}")
            
            return res_json
            
        except Exception as e:
            print(f"❌ Agent 决策过程出现异常: {str(e)}")
            if 'response' in locals() and hasattr(response, 'candidates'):
                print(f"🔍 调试信息 - 停止原因: {response.candidates[0].finish_reason}")
            return {"op": "error", "reason": str(e)}