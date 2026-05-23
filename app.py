from flask import Flask, request, render_template, jsonify, send_file
import os
import tempfile
import re
from datetime import datetime
import yt_dlp
import zipfile
import shutil
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Railway-safe folder
DOWNLOAD_DIR = "/tmp/downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class UniversalDownloader:

    def detect_platform(self, url):
        url = url.lower()

        if "youtube.com" in url or "youtu.be" in url:
            return "YouTube"

        elif "instagram.com" in url:
            return "Instagram"

        elif "facebook.com" in url or "fb.watch" in url:
            return "Facebook"

        elif "tiktok.com" in url:
            return "TikTok"

        elif "twitter.com" in url or "x.com" in url:
            return "Twitter/X"

        elif "reddit.com" in url:
            return "Reddit"

        return "Unknown"

    def download_content(self, url):

        platform = self.detect_platform(url)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        folder_name = f"{platform}_{timestamp}"

        download_path = os.path.join(DOWNLOAD_DIR, folder_name)

        os.makedirs(download_path, exist_ok=True)

        ydl_opts = {
            "outtmpl": os.path.join(
                download_path,
                "%(title)s.%(ext)s"
            ),

            "format": "best",
            "quiet": True,
            "noplaylist": False,
            "merge_output_format": "mp4",
            "ignoreerrors": True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(url, download=True)

                if not info:
                    return {
                        "status": "error",
                        "message": "Download failed"
                    }

                title = info.get("title", "Unknown")

                return {
                    "status": "success",
                    "platform": platform,
                    "title": title,
                    "folder": folder_name,
                    "message": f"{platform} content downloaded successfully!"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }


downloader = UniversalDownloader()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/detect", methods=["POST"])
def detect():

    try:
        data = request.get_json()

        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "status": "error",
                "message": "URL missing"
            })

        platform = downloader.detect_platform(url)

        return jsonify({
            "status": "success",
            "platform": platform
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@app.route("/download", methods=["POST"])
def download():

    try:
        data = request.get_json()

        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "status": "error",
                "message": "URL required"
            })

        result = downloader.download_content(url)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })


@app.route("/downloads")
def downloads():

    try:
        items = []

        for item in os.listdir(DOWNLOAD_DIR):

            item_path = os.path.join(DOWNLOAD_DIR, item)

            if os.path.isdir(item_path):

                items.append({
                    "name": item,
                    "files": len(os.listdir(item_path))
                })

        return jsonify(items)

    except Exception as e:
        return jsonify({
            "error": str(e)
        })


@app.route("/download-folder/<foldername>")
def download_folder(foldername):

    try:
        safe_foldername = secure_filename(foldername)

        folder_path = os.path.join(
            DOWNLOAD_DIR,
            safe_foldername
        )

        if not os.path.exists(folder_path):
            return jsonify({
                "error": "Folder not found"
            })

        temp_zip = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".zip"
        )

        temp_zip.close()

        with zipfile.ZipFile(
            temp_zip.name,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zipf:

            for root, dirs, files in os.walk(folder_path):

                for file in files:

                    file_path = os.path.join(root, file)

                    arcname = os.path.relpath(
                        file_path,
                        folder_path
                    )

                    zipf.write(file_path, arcname)

        return send_file(
            temp_zip.name,
            as_attachment=True,
            download_name=f"{safe_foldername}.zip"
        )

    except Exception as e:
        return jsonify({
            "error": str(e)
        })


@app.route("/clear-downloads", methods=["POST"])
def clear_downloads():

    try:

        shutil.rmtree(DOWNLOAD_DIR)

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        return jsonify({
            "status": "success"
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        })


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )