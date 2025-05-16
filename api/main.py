from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import time
import logging
import uuid
import json


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}}, supports_credentials=True)

COMFY_API_URL = "http://192.168.1.236:8188/"
WORKFLOW_DIR = "workflows"
OUTPUT_DIR = "/Users/kiseon/Documents/ComfyUI/output"

logging.basicConfig(level=logging.DEBUG)


def load_workflow(workflow_name):
    try:
        with open(os.path.join(WORKFLOW_DIR, workflow_name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"워크플로우를 로드할 수 없습니다: {str(e)}"}



def set_unique_filename(workflow, unique_id, index=None, item_id=None, subfolder=None):
    for node in workflow.values():
        if not isinstance(node, dict):
            continue

        if node.get("class_type") == "SaveImage":
            # 기본 파일 이름 생성
            if item_id is not None and index is not None:
                filename = f"background_id={item_id}_{index:02d}_{unique_id}"
            elif index is not None:
                filename = f"background_{index:02d}_{unique_id}"
            else:
                filename = f"background_{unique_id}"

            # subfolder를 포함한 파일 경로 생성
            if subfolder:
                filename_prefix = f"{subfolder}/{filename}"
            else:
                filename_prefix = filename

            if "inputs" in node:
                node["inputs"]["filename_prefix"] = filename_prefix
                # subfolder key는 삭제 (filename_prefix에 포함됐기 때문)
                node["inputs"].pop("subfolder", None)

    return workflow


def generate_single(prompt, workflow_name, subfolder):
    workflow = load_workflow(workflow_name)

    if "error" in workflow:
        return jsonify(workflow), 500

    # 프롬프트를 워크플로우 내에 반영
    for node in workflow.values():
        if (
            isinstance(node, dict)
            and node.get("class_type") == "CLIPTextEncode"
            and node.get("_meta", {}).get("title") == "Positive Prompt"
        ):
            if "inputs" in node and "text" in node["inputs"]:
                node["inputs"]["text"] = prompt


    workflow = set_unique_filename(workflow, str(uuid.uuid4())[:8], subfolder=subfolder)

    for node in workflow.values():
        if node.get("class_type") in ["KSampler", "KSamplerAdvanced", "Seed"]:
            if "inputs" in node and "seed" in node["inputs"]:
                node["inputs"]["seed"] = int(time.time())

    res = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
    res.raise_for_status()
    prompt_id = res.json().get("prompt_id")

    return wait_for_image(prompt_id, subfolder)



def generate_backgrounds(background_items, workflow_name, subfolder):
    results = []
    batch_id = str(uuid.uuid4())[:8]
    original_workflow = load_workflow(workflow_name)

    # ❗1. 워크플로우가 에러인지 먼저 확인
    if not isinstance(original_workflow, dict) or "error" in original_workflow:
        return jsonify(original_workflow), 500

    for idx, item in enumerate(background_items):
        # ❗2. 아이템이 dict가 아니면 continue
        if not isinstance(item, dict):
            results.append("invalid")
            continue

        # deepcopy
        workflow = json.loads(json.dumps(original_workflow))
        item_id = item.get("id", None)
        prompt = item.get("background") or item.get("background_image", "")
        prompt = prompt.strip()

        # ❗3. 프롬프트가 없으면 스킵
        if not prompt:
            results.append("empty")
            continue
        for node in workflow.values():
            if (
                isinstance(node, dict)
                and node.get("class_type") == "CLIPTextEncode"
                and node.get("_meta", {}).get("title") == "Positive Prompt"
            ):
                if "inputs" in node and "text" in node["inputs"]:
                    node["inputs"]["text"] = prompt


        # ❗4. 워크플로우에 고유 파일명 설정
        workflow = set_unique_filename(workflow, batch_id, idx, item_id, subfolder=subfolder)

        # ❗5. workflow가 dict가 아닐 경우 대비
        if not isinstance(workflow, dict):
            results.append("error")
            continue

        # Seed 설정
        for node in workflow.values():
            if isinstance(node, dict) and node.get("class_type") in ["KSampler", "KSamplerAdvanced", "Seed"]:
                if "inputs" in node and "seed" in node["inputs"]:
                    node["inputs"]["seed"] = int(time.time()) + (idx + 1) * 10000

        try:
            # 프롬프트 전송
            res = requests.post(f"{COMFY_API_URL}/prompt", json={"prompt": workflow})
            res.raise_for_status()
            prompt_id = res.json().get("prompt_id")

            # 이미지 대기
            result = wait_for_image(prompt_id, subfolder, idx)
            results.append(result)

        except Exception as e:
            results.append(f"error: {str(e)}")

        time.sleep(2)

    return jsonify({"image_urls": results})






def wait_for_image(prompt_id, subfolder, idx=None):
    while True:
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




@app.route("/workflows", methods=["GET"])
def list_workflows():
    try:
        files = os.listdir(WORKFLOW_DIR)
        json_files = [f for f in files if f.endswith(".json")]
        return jsonify({"workflows": json_files})
    except Exception as e:
        return jsonify({"error": "워크플로우 목록을 불러올 수 없습니다.", "detail": str(e)}), 500





@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    workflow_name = data.get("workflow")
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
    app.run(port=5000, debug=True)
