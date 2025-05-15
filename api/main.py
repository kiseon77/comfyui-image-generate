from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import time
import logging
import uuid

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"], supports_credentials=True)

COMFY_API_URL = "http://127.0.0.1:8188"
WORKFLOW_DIR = "workflows"
OUTPUT_DIR = "/Users/kiseon/Documents/ComfyUI/output"

logging.basicConfig(level=logging.DEBUG)

@app.route("/workflows", methods=["GET"])
def list_workflows():
    try:
        files = os.listdir(WORKFLOW_DIR)
        json_files = [f for f in files if f.endswith(".json")]
        return jsonify({"workflows": json_files})
    except Exception as e:
        return jsonify({"error": "워크플로우 목록을 불러올 수 없습니다.", "detail": str(e)}), 500


def set_unique_filename(workflow, unique_id, index=None, item_id=None, subfolder=None):
    for node in workflow.values():
        if node.get("class_type") == "SaveImage":
            if item_id is not None:
                filename = f"background_id={item_id}_{index:02d}_{unique_id}"
            else:
                filename = f"background_{index:02d}_{unique_id}" if index is not None else f"background_{unique_id}"

            if "inputs" in node:
                if "filename_prefix" in node["inputs"]:
                    node["inputs"]["filename_prefix"] = filename
                # ✅ 여기서 subfolder도 설정
                if subfolder:
                    node["inputs"]["subfolder"] = subfolder
    return workflow




@app.route("/generate", methods=["POST", "OPTIONS"])
def generate():
    if request.method == "OPTIONS":
        return '', 204

    data = request.json
    workflow_name = data.get("workflow", "default.json")
    subfolder = data.get("subfolder")
    prompt_data = data.get("prompt")

    try:
        # 1. 단일 문자열 프롬프트
        if isinstance(prompt_data, str):
            return generate_single(prompt_data, workflow_name, subfolder)

        elif isinstance(prompt_data, dict) and "events" in prompt_data:
          return generate_backgrounds(prompt_data["events"], workflow_name, subfolder)


        else:
            return jsonify({"error": "지원하지 않는 형식입니다. 'prompt' 또는 'events' 키를 사용하세요."}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "서버 내부 오류", "detail": str(e)}), 500



def generate_single(prompt, workflow_name, subfolder):
    workflow = set_unique_filename(workflow, str(uuid.uuid4())[:8], subfolder=subfolder)
    if "error" in workflow:
        return jsonify(workflow), 500

    for node in workflow.values():
        if node.get("class_type") in ["KSampler", "KSamplerAdvanced", "Seed"]:
            if "inputs" in node and "seed" in node["inputs"]:
                node["inputs"]["seed"] = int(time.time())

    workflow = set_unique_filename(workflow, str(uuid.uuid4())[:8])

    res = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
    res.raise_for_status()
    prompt_id = res.json().get("prompt_id")

    return wait_for_image(prompt_id, subfolder)


def generate_backgrounds(background_items, workflow_name, subfolder):
    results = []
    batch_id = str(uuid.uuid4())[:8]

    for idx, item in enumerate(background_items):
        if not isinstance(item, dict):
            results.append("invalid")
            continue

        prompt = item.get("background") or item.get("background_image", "")
        prompt = prompt.strip()
        item_id = item.get("id", None)

        if not prompt:
            results.append("empty")
            continue

        workflow = set_unique_filename(workflow, batch_id, idx, item_id, subfolder=subfolder)
        if "error" in workflow:
            results.append("error")
            continue

        # Seed 설정
        for node in workflow.values():
            if node.get("class_type") in ["KSampler", "KSamplerAdvanced", "Seed"]:
                if "inputs" in node and "seed" in node["inputs"]:
                    node["inputs"]["seed"] = int(time.time()) + (idx + 1) * 10000

        # 고유 파일명 설정
        workflow = set_unique_filename(workflow, batch_id, idx, item_id)

        # ComfyUI에 프롬프트 전송
        res = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
        res.raise_for_status()
        prompt_id = res.json().get("prompt_id")

        # 이미지 대기 및 결과 URL 저장
        result = wait_for_image(prompt_id, subfolder, idx)
        results.append(result)

        time.sleep(2)  # 서버 부담 방지

    return jsonify({"image_urls": results})





def wait_for_image(prompt_id, subfolder, idx=None):
    for _ in range(100):
        time.sleep(0.5)
        try:
            history = requests.get(f"{COMFY_API_URL}/history/{prompt_id}").json()
            if prompt_id in history:
                for output in history[prompt_id].get("outputs", {}).values():
                    if "images" in output and output["images"]:
                        image = output["images"][0]
                        filename = image["filename"]
                        folder = subfolder if subfolder else image.get("subfolder", "")
                        path = f"{folder}/{filename}" if folder else filename
                        return f"http://127.0.0.1:5000/output/{path}?cb={int(time.time())}"
        except Exception as e:
            continue
    return "timeout"


@app.route("/output/<path:filename>")
def serve_image(filename):
    try:
        return send_from_directory(OUTPUT_DIR, filename)
    except Exception as e:
        return jsonify({"error": "이미지를 서빙할 수 없습니다.", "detail": str(e)}), 404


@app.route("/output/latest")
def serve_latest_image():
    files = [f for f in os.listdir(OUTPUT_DIR) if os.path.isfile(os.path.join(OUTPUT_DIR, f))]
    if not files:
        return jsonify({"error": "이미지가 없습니다."}), 404
    latest = max(files, key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)))
    return send_from_directory(OUTPUT_DIR, latest)


if __name__ == "__main__":
    app.run(port=5000)
