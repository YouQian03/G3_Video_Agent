import os
import time
from google import genai
from google.genai import types

# 确保环境变量已加载
api_key = os.environ.get("GEMINI_API_KEY")
# Sanitize API key to remove non-ASCII characters (fixes encoding errors in HTTP headers)
if api_key:
    api_key = api_key.strip()
    api_key = ''.join(c for c in api_key if c.isascii() and c.isprintable())
client = genai.Client(api_key=api_key)

def run_veo_generation(shot_id, prompt, image_path, output_dir="output_videos"):
    """
    针对 2026 年 Gemini 3 / Veo 生态优化的视频生成函数
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 以二进制读取风格化后的参考图
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
    except FileNotFoundError:
        print(f"❌ 找不到图片文件: {image_path}")
        return None

    print(f"🚀 启动 Veo 3.1 任务 | 分镜: {shot_id}")
    
    try:
        # 2. 调用专门的 generate_videos 接口
        # 修复点：必须使用 generate_videos 而非 generate_content
        operation = client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            config=types.GenerateVideosConfig(
                # 修复点：参考图必须放在这个 image 字段里
                image=types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png"
                ),
                aspect_ratio="16:9"
            )
        )

        # 3. 异步轮询 (Veo 视频生成不是即时的)
        print(f"⏳ 视频正在云端渲染 (Operation ID: {operation.name})")
        while not operation.done:
            print(".", end="", flush=True)
            time.sleep(10)  # 每 10 秒查询一次进度
            operation = client.operations.get(operation.name)

        # 4. 检查结果并保存
        if operation.result and operation.result.generated_videos:
            generated_video = operation.result.generated_videos[0]
            output_path = os.path.join(output_dir, f"{shot_id}.mp4")
            
            # 使用 SDK 原生 save 方法
            generated_video.video.save(output_path)
            print(f"\n✅ 视频生成成功: {output_path}")
            return output_path
        else:
            print(f"\n❌ 生成失败，原因: {operation.error}")
            return None

    except Exception as e:
        print(f"\n❌ 调用 Veo API 出现严重异常: {str(e)}")
        return None

if __name__ == "__main__":
    # 测试代码 (你可以直接运行 python video_generator.py 验证)
    test_prompt = "A cinematic drone shot of a neon cyberpunk city in the rain."
    test_image = "stylized_frames/shot_01.png"
    run_veo_generation("shot_01", test_prompt, test_image)