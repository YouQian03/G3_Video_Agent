import os
from pathlib import Path

from google import genai
from google.genai import types

PROJECT_DIR = Path(__file__).parent
FRAMES_DIR = PROJECT_DIR / "frames"
OUT_DIR = PROJECT_DIR / "stylized_frames"
OUT_DIR.mkdir(exist_ok=True)

MODEL = "gemini-3-pro-image-preview"  # 支持多图参考和角色一致性

PROMPT = """
You are given a storyboard reference frame from a viral short video.

Goal: "De-replication stylization" (same structure, new details).
- Preserve: composition, camera angle, subject placement, overall color palette, lighting mood, and emotional tone.
- Must change: all fine details must be newly designed (faces, clothing details, textures, materials, patterns, background objects, any text/logos).
- Avoid pixel-level similarity. Do NOT copy any identifiable characters, logos, or exact text.
- Keep it cinematic and coherent.

Output:
- 16:9 image
- high clarity, rich details
"""

def save_first_image_from_response(response, out_path: Path) -> bool:
    """
    Nano Banana responses can include text parts and image parts.
    We scan parts and save the first image we find.
    """
    for part in response.parts:
        if part.inline_data is not None:
            img = part.as_image()   # requires pillow
            img.save(out_path)
            return True
    return False

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("没有检测到 GEMINI_API_KEY 环境变量（请先 export GEMINI_API_KEY=你的key）")

    if not FRAMES_DIR.exists():
        raise FileNotFoundError(f"找不到 frames 文件夹：{FRAMES_DIR}")

    frame_paths = sorted(FRAMES_DIR.glob("shot_*.png"))
    if not frame_paths:
        raise FileNotFoundError(f"frames 里没有 shot_*.png：{FRAMES_DIR}")

    client = genai.Client(api_key=api_key)

    print(f"将处理 {len(frame_paths)} 张分镜图，输出到：{OUT_DIR}")

    for img_path in frame_paths:
        out_path = OUT_DIR / img_path.name

        # 传入图片（官方推荐：types.Part.from_bytes）
        image_part = types.Part.from_bytes(
            data=img_path.read_bytes(),
            mime_type="image/png",
        )

        print(f"🖼️  Stylize {img_path.name} ...")

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                image_part,
                PROMPT
            ],
            # 可选：如果你用 gemini-3-pro-image-preview 想指定输出参数，可以打开下面 config
            # config=types.GenerateContentConfig(
            #     response_modalities=["TEXT", "IMAGE"],
            #     image_config=types.ImageConfig(aspect_ratio="16:9", image_size="2K"),
            # )
        )

        ok = save_first_image_from_response(response, out_path)
        if ok:
            print(f"✅ saved -> {out_path}")
        else:
            # 有时模型只回文字（表示没出图或被拒绝/降级），把文字打印出来便于你做可行性判断
            print("⚠️ 没拿到图片输出，模型返回文本如下：")
            print(response.text)

    print("✅ 全部完成")

if __name__ == "__main__":
    main()

