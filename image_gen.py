#!/Users/admin/bin/python3.14
"""GPT-Image-2 图像生成 — 本地桌面窗口"""

import json
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
from io import BytesIO
from urllib.request import Request, urlopen
from urllib.error import URLError

API_KEY = "sk-uoB3UmTvwtwqiNVAeqvH27Cy7NFSxnOUvM7Pfa4LK9yXLDmL"
API_BASE = "https://toapis.com/v1"

SIZES = ["1:1", "3:2", "2:3", "4:3", "3:4", "5:4", "4:5", "16:9", "9:16", "2:1", "1:2", "21:9", "9:21"]
RESOLUTIONS = ["1K", "2K", "4K"]


HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json", "User-Agent": "image_gen/1.0"}


def api_post(path, body):
    data = json.dumps(body).encode()
    req = Request(f"{API_BASE}{path}", data=data, headers=HEADERS)
    resp = urlopen(req, timeout=30)
    return json.loads(resp.read())


def upload_image(filepath):
    """上传本地图片，返回可用的 URL"""
    boundary = "----ToAPIsBoundary2026"
    with open(filepath, "rb") as f:
        file_data = f.read()

    filename = os.path.basename(filepath)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: image/{'png' if filename.lower().endswith('.png') else 'jpeg'}\r\n"
        f"\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    headers = {
        "Authorization": HEADERS["Authorization"],
        "User-Agent": HEADERS["User-Agent"],
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = Request(f"{API_BASE}/uploads/images", data=body, headers=headers)
    resp = urlopen(req, timeout=30)
    data = json.loads(resp.read())
    return data["data"]["url"]


def api_get(path):
    req = Request(f"{API_BASE}{path}", headers=HEADERS)
    resp = urlopen(req, timeout=10)
    return json.loads(resp.read())


def create_task(prompt, size, resolution, references=None):
    body = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "size": size,
        "resolution": resolution,
        "n": 1,
        "response_format": "url",
    }
    if references:
        body["reference_images"] = references

    data = api_post("/images/generations", body)
    return data["id"]


def poll_task(task_id):
    """轮询任务，yield (status, progress)；完成时 yield (url, 100)"""
    start = time.time()
    while time.time() - start < 600:
        data = api_get(f"/images/generations/{task_id}")
        status = data["status"]
        progress = data.get("progress", 0)

        if status == "completed":
            result = data.get("result", {})
            images = result.get("data", [])
            url = images[0]["url"] if images else data.get("url")
            yield url, 100
            return
        if status == "failed":
            error = data.get("error", {})
            raise RuntimeError(f"生成失败: {error.get('message', json.dumps(error))}")
        if status not in ("queued", "in_progress"):
            raise RuntimeError(f"未知状态: {status}")

        yield status, progress
        time.sleep(3)

    raise TimeoutError("任务超时（600 秒）")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GPT-Image-2 图像生成")
        self.root.geometry("780x720")
        self.root.configure(bg="#f0f0f0")

        style = ttk.Style()
        style.theme_use("clam")

        # --- 输入区 ---
        input_frame = ttk.LabelFrame(self.root, text="提示词", padding=12)
        input_frame.pack(fill=tk.X, padx=14, pady=(14, 8))

        self.prompt_text = tk.Text(input_frame, height=4, font=("PingFang SC", 14), wrap=tk.WORD,
                                    relief=tk.FLAT, borderwidth=0, padx=8, pady=8)
        self.prompt_text.pack(fill=tk.X)

        # --- 参数区 ---
        param_frame = ttk.Frame(self.root)
        param_frame.pack(fill=tk.X, padx=14, pady=6)

        ttk.Label(param_frame, text="比例", font=("PingFang SC", 12)).pack(side=tk.LEFT)
        self.size_var = tk.StringVar(value="1:1")
        size_cb = ttk.Combobox(param_frame, textvariable=self.size_var, values=SIZES, width=7,
                               state="readonly", font=("PingFang SC", 12))
        size_cb.pack(side=tk.LEFT, padx=(6, 20))

        ttk.Label(param_frame, text="分辨率", font=("PingFang SC", 12)).pack(side=tk.LEFT)
        self.res_var = tk.StringVar(value="1K")
        res_cb = ttk.Combobox(param_frame, textvariable=self.res_var, values=RESOLUTIONS, width=5,
                              state="readonly", font=("PingFang SC", 12))
        res_cb.pack(side=tk.LEFT, padx=6)

        self.gen_btn = ttk.Button(param_frame, text="生成图片", command=self.on_generate)
        self.gen_btn.pack(side=tk.RIGHT)

        # --- 状态 ---
        self.status_var = tk.StringVar(value="就绪")
        status_label = tk.Label(self.root, textvariable=self.status_var, font=("PingFang SC", 11), bg="#f0f0f0")
        status_label.pack(padx=14, pady=4)

        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, padx=14, pady=4)

        # --- 图片显示区 ---
        img_frame = ttk.LabelFrame(self.root, text="生成结果", padding=8)
        img_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(8, 14))

        canvas_frame = tk.Frame(img_frame, bg="#e8e8e8")
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#e8e8e8", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._photo = None
        self._task_thread = None

    def on_generate(self):
        prompt = self.prompt_text.get("1.0", " ").strip()
        if not prompt:
            self.status_var.set("请输入提示词")
            return

        self.gen_btn.config(state=tk.DISABLED)
        self.status_var.set("正在创建任务...")
        self.progress.config(mode="indeterminate")
        self.progress.start()
        self.canvas.delete("all")

        self._task_thread = threading.Thread(target=self._run, args=(prompt,), daemon=True)
        self._task_thread.start()

    def _run(self, prompt):
        size = self.size_var.get()
        resolution = self.res_var.get()
        try:
            task_id = create_task(prompt, size, resolution)
            self._update(lambda: self.status_var.set(f"任务已提交，等待生成..."))
            self._update(lambda: self.progress.config(mode="determinate"))
            self._update(lambda: self.progress.config(value=0))

            for result, progress in poll_task(task_id):
                if isinstance(result, str) and result.startswith("http"):
                    # 完成 — result 是图片 URL
                    url = result
                    self._update(lambda: self.progress.config(value=100))
                    self._update(lambda: self.status_var.set("下载图片中..."))

                    req = Request(url, headers={"User-Agent": "image_gen/1.0"})
                    img_data = urlopen(req, timeout=30).read()
                    self._update(lambda: self._show_image(img_data))

                    info = f"完成! {size} / {resolution}"
                    self._update(lambda: self.status_var.set(info))
                    return
                else:
                    # 进度更新
                    self._update(lambda p=progress: self.progress.config(value=p))
                    self._update(lambda s=result: self.status_var.set(f"状态: {s} ({progress}%)"))
        except Exception as e:
            self._update(lambda: self.status_var.set(f"错误: {e}"))
        finally:
            self._update(lambda: self.gen_btn.config(state=tk.NORMAL))
            self._update(lambda: self.progress.stop())

    def _show_image(self, img_data):
        self._photo = tk.PhotoImage(data=img_data)

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 100:
            cw = 760
        if ch < 100:
            ch = 500

        pw = self._photo.width()
        ph = self._photo.height()

        # tkinter PhotoImage 只支持整数倍缩放，用 subsample 缩小
        factor = max(1, (pw + cw - 1) // cw, (ph + ch - 1) // ch)
        if factor > 1:
            self._photo = self._photo.subsample(factor, factor)

        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo, anchor=tk.CENTER)

    def _update(self, fn):
        self.root.after(0, fn)

    def run(self):
        self.root.mainloop()


def cli_mode():
    import subprocess

    size = "1:1"
    resolution = "1K"
    output = None
    references = []
    prompt_parts = []
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--size" and i + 1 < len(args):
            size = args[i + 1]; i += 2
        elif args[i] == "--resolution" and i + 1 < len(args):
            resolution = args[i + 1]; i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output = args[i + 1]; i += 2
        elif args[i] == "--reference" and i + 1 < len(args):
            references.append(args[i + 1]); i += 2
        elif args[i] == "--help" or args[i] == "-h":
            print("用法: image_gen.py [选项] <提示词>")
            print("      image_gen.py                   启动 GUI 窗口")
            print("选项:")
            print("  --size <比例>           1:1, 16:9, 9:16 ... (默认 1:1)")
            print("  --resolution <档位>     1K, 2K, 4K (默认 1K)")
            print("  --reference <图片路径>  参考图(可多次指定，用于图生图)")
            print("  --output <路径>         保存路径 (默认自动命名并打开)")
            print("示例:")
            print('  image_gen.py "一只可爱的橘猫"')
            print('  image_gen.py --size 16:9 --resolution 2K "未来城市夜景"')
            print('  image_gen.py --reference photo.png "唐朝公主风格"')
            return
        else:
            prompt_parts.append(args[i]); i += 1

    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        print("请输入提示词，或运行不带参数启动 GUI 窗口")
        print('示例: image_gen.py "一只可爱的橘猫坐在窗台上"')
        return

    # 上传参考图
    ref_urls = []
    for ref_path in references:
        if not os.path.exists(ref_path):
            print(f"参考图不存在: {ref_path}")
            return
        print(f"上传参考图: {os.path.basename(ref_path)}...", end="", flush=True)
        url = upload_image(ref_path)
        ref_urls.append(url)
        print(" OK")

    print(f"提示词: {prompt}")
    print(f"参数:   {size} / {resolution}")
    if ref_urls:
        print(f"参考图: {len(ref_urls)} 张")
    print(f"正在创建任务...", end="", flush=True)

    try:
        task_id = create_task(prompt, size, resolution, references=ref_urls or None)
        print(f" OK ({task_id[:24]}...)")

        last_msg = ""
        for result, progress in poll_task(task_id):
            if isinstance(result, str) and result.startswith("http"):
                url = result
                print(f"\r下载图片中...", end="", flush=True)
                req = Request(url, headers={"User-Agent": "image_gen/1.0"})
                img_data = urlopen(req, timeout=30).read()

                if not output:
                    safe_name = prompt[:30].replace("/", "_").replace(" ", "_")
                    output = f"generated_{safe_name}.png"

                with open(output, "wb") as f:
                    f.write(img_data)
                print(f"\r完成! 已保存到: {os.path.abspath(output)}   ")
                subprocess.run(["open", output])
                return
            else:
                msg = f"状态: {result} ({progress}%)"
                if msg != last_msg:
                    print(f"\r{msg}", end="", flush=True)
                    last_msg = msg

        print("\n超时")

    except Exception as e:
        print(f"\n错误: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_mode()
    else:
        App().run()
