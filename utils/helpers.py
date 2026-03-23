import os
import uuid
from dotenv import load_dotenv

load_dotenv()

BASE_DIR             = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR          = os.path.dirname(BASE_DIR)
UPLOAD_FOLDER_PHOTOS = os.path.join(PROJECT_DIR, "static", "uploads", "photos")
UPLOAD_FOLDER_LOGOS  = os.path.join(PROJECT_DIR, "static", "uploads", "logos")

os.makedirs(UPLOAD_FOLDER_PHOTOS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_LOGOS,  exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file, folder="photos"):
    if not file or not file.filename:
        return None, None
    if not allowed_file(file.filename):
        return None, None

    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    api_key    = os.environ.get("CLOUDINARY_API_KEY", "")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET", "")

    if cloud_name and api_key and api_secret:
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            file.seek(0)
            result   = cloudinary.uploader.upload(file, folder=folder)
            url      = result.get("secure_url", "")
            filename = result.get("public_id", "").split("/")[-1]
            ext      = result.get("format", "jpg")
            filename = filename + "." + ext
            print(f"Cloudinary OK: {url}")
            return filename, url
        except Exception as e:
            print(f"Cloudinary failed: {e}")

    try:
        ext      = file.filename.rsplit(".", 1)[-1].lower()
        filename = uuid.uuid4().hex + "." + ext
        if folder == "logos":
            path = os.path.join(UPLOAD_FOLDER_LOGOS, filename)
        else:
            path = os.path.join(UPLOAD_FOLDER_PHOTOS, filename)
        file.seek(0)
        file.save(path)
        print(f"Local OK: {path}")
        return filename, None
    except Exception as e:
        print(f"Local save failed: {e}")
        return None, None


def save_logo(file):
    return save_photo(file, folder="logos")


def calculate_grade(score):
    if score >= 80: return "A"
    elif score >= 70: return "B"
    elif score >= 60: return "C"
    elif score >= 50: return "D"
    elif score >= 40: return "E"
    else: return "F"


def format_currency(amount):
    return f"N{amount:,.2f}"

