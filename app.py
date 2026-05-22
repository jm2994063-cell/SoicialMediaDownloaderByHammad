from flask import Flask, request, render_template, jsonify, send_file
import os
import tempfile
import requests
import re
from datetime import datetime
import yt_dlp
import instaloader
from werkzeug.utils import secure_filename
import zipfile
import shutil

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "supersecretkey")

# Downloads folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class UniversalDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0'
        })

    def detect_platform(self, url):
        url = url.lower()

        if 'youtube.com' in url or 'youtu.be' in url:
            return 'youtube'

        elif 'instagram.com' in url:
            return 'instagram'

        elif 'facebook.com' in url or 'fb.watch' in url:
            return 'facebook'

        elif 'twitter.com' in url or 'x.com' in url:
            return 'twitter'

        elif 'tiktok.com' in url:
            return 'tiktok'

        elif 'reddit.com' in url:
            return 'reddit'

        return 'unknown'

    def yt_options(self, path, template):
        return {
            'outtmpl': os.path.join(path, template),
            'format': 'bestvideo+bestaudio/best',
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': False,
            'merge_output_format': 'mp4'
        }

    def download_youtube_content(self, url, path):
        try:
            ydl_opts = self.yt_options(
                path,
                '%(uploader)s - %(title)s.%(ext)s'
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if not info:
                    return {
                        'status': 'error',
                        'message': 'Failed to fetch YouTube content'
                    }

                return {
                    'status': 'success',
                    'message': 'YouTube content downloaded successfully!',
                    'title': info.get('title', 'Unknown'),
                    'platform': 'YouTube'
                }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'YouTube error: {str(e)}'
            }

    def download_instagram_content(self, url, path):
        try:
            loader = instaloader.Instaloader(
                dirname_pattern=path,
                filename_pattern='{profile}_{shortcode}',
                download_videos=True,
                download_video_thumbnails=False,
                download_comments=False,
                save_metadata=False
            )

            shortcode = self.extract_instagram_shortcode(url)

            if not shortcode:
                return {
                    'status': 'error',
                    'message': 'Invalid Instagram URL'
                }

            post = instaloader.Post.from_shortcode(
                loader.context,
                shortcode
            )

            loader.download_post(post, target=path)

            return {
                'status': 'success',
                'message': 'Instagram content downloaded successfully!',
                'title': post.owner_username,
                'platform': 'Instagram'
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Instagram error: {str(e)}'
            }

    def download_generic(self, url, path):
        try:
            ydl_opts = self.yt_options(
                path,
                '%(extractor)s_%(title)s.%(ext)s'
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if not info:
                    return {
                        'status': 'error',
                        'message': 'Failed to download content'
                    }

                return {
                    'status': 'success',
                    'message': 'Content downloaded successfully!',
                    'title': info.get('title', 'Unknown')
                }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    def extract_instagram_shortcode(self, url):
        patterns = [
            r'/p/([^/?]+)',
            r'/reel/([^/?]+)',
            r'/tv/([^/?]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)

            if match:
                return match.group(1)

        return None

    def download_content(self, url):
        platform = self.detect_platform(url)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        folder = os.path.join(
            DOWNLOAD_DIR,
            f"{platform}_{timestamp}"
        )

        os.makedirs(folder, exist_ok=True)

        if platform == 'youtube':
            return self.download_youtube_content(url, folder)

        elif platform == 'instagram':
            return self.download_instagram_content(url, folder)

        else:
            return self.download_generic(url, folder)


downloader = UniversalDownloader()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()

        url = data.get('url', '').strip()

        if not url:
            return jsonify({
                'status': 'error',
                'message': 'URL is required'
            })

        result = downloader.download_content(url)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


@app.route('/downloads')
def downloads():
    try:
        items = []

        for item in os.listdir(DOWNLOAD_DIR):
            item_path = os.path.join(DOWNLOAD_DIR, item)

            if os.path.isdir(item_path):
                items.append({
                    'name': item,
                    'type': 'folder',
                    'file_count': len(os.listdir(item_path))
                })

            elif os.path.isfile(item_path):
                items.append({
                    'name': item,
                    'type': 'file',
                    'size': os.path.getsize(item_path)
                })

        return jsonify({'items': items})

    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/download-file/<filename>')
def download_file(filename):
    try:
        safe_filename = secure_filename(filename)

        file_path = os.path.join(
            DOWNLOAD_DIR,
            safe_filename
        )

        if not os.path.exists(file_path):
            return jsonify({
                'error': 'File not found'
            }), 404

        return send_file(
            file_path,
            as_attachment=True
        )

    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/download-folder/<foldername>')
def download_folder(foldername):
    try:
        safe_foldername = secure_filename(foldername)

        folder_path = os.path.join(
            DOWNLOAD_DIR,
            safe_foldername
        )

        if not os.path.exists(folder_path):
            return jsonify({
                'error': 'Folder not found'
            }), 404

        temp_zip = tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.zip'
        )

        temp_zip.close()

        with zipfile.ZipFile(
            temp_zip.name,
            'w',
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
            download_name=f'{safe_foldername}.zip'
        )

    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/bulk-download', methods=['POST'])
def bulk_download():
    try:
        data = request.get_json()

        urls = data.get('urls', [])

        if not urls:
            return jsonify({
                'status': 'error',
                'message': 'No URLs provided'
            })

        results = []

        for url in urls:
            result = downloader.download_content(url.strip())
            results.append(result)

        return jsonify({
            'status': 'success',
            'message': 'Bulk download completed',
            'results': results
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


@app.route('/clear-downloads', methods=['POST'])
def clear_downloads():
    try:
        shutil.rmtree(DOWNLOAD_DIR)

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        return jsonify({
            'status': 'success',
            'message': 'Downloads cleared'
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host='0.0.0.0',
        port=port,
        debug=True
    )