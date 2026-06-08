import cloudinary
import cloudinary.uploader
import json
import os
import requests
from io import BytesIO
from PIL import Image
from plexapi.server import PlexServer
# ======================
# CONFIG
# ======================
PLEX_URL = os.getenv("PLEX_URL")
PLEX_DOWNLOAD_URL = os.getenv("PLEX_DOWNLOAD_URL")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
CACHE_FILE = "/cache/plex_cache.json"
POSTER_DIR = "/cache/posters"
POSTER_PUBLIC_URL = os.getenv(
    "POSTER_PUBLIC_URL",
    ""
)

# ======================
# POSTER PROVIDER
# ======================

POSTER_PROVIDER = os.getenv(
    "POSTER_PROVIDER",
    "local"
).lower()

# ======================
# CLOUDINARY
# ======================

CLOUDINARY_CLOUD_NAME = os.getenv(
    "CLOUDINARY_CLOUD_NAME",
    ""
)

CLOUDINARY_API_KEY = os.getenv(
    "CLOUDINARY_API_KEY",
    ""
)

CLOUDINARY_API_SECRET = os.getenv(
    "CLOUDINARY_API_SECRET",
    ""
)

CLOUDINARY_FOLDER = os.getenv(
    "CLOUDINARY_FOLDER",
    "plex-posters"
)
# ======================
# POSTER QUALITY
# ======================
POSTER_WIDTH = int(
    os.getenv("POSTER_WIDTH", "600")
)

POSTER_HEIGHT = int(
    os.getenv("POSTER_HEIGHT", "900")
)

POSTER_QUALITY = int(
    os.getenv("POSTER_QUALITY", "80")
)

# ======================
# LOAD CACHE
# ======================
def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            item["rating_key"]: item
            for item in data
        }
    except Exception as e:
        print(f"[CACHE LOAD ERROR] {e}")
        return {}
# ======================
# SAVE CACHE
# ======================
def save_cache(cache):
    os.makedirs(
        os.path.dirname(CACHE_FILE),
        exist_ok=True
    )
    with open(
        CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            list(cache.values()),
            f,
            indent=2,
            ensure_ascii=False
        )
# ======================
# BUILD WATCH URL
# ======================
def build_watch_url(item, media_type):
    slug = getattr(item, "slug", None)
    if slug:
        if media_type == "movie":
            return f"https://watch.plex.tv/movie/{slug}"
        elif media_type == "show":
            return f"https://watch.plex.tv/show/{slug}"
    return None
# ======================
# BUILD POSTER URL
# ======================
def upload_to_cloudinary(
    image_bytes,
    rating_key
):

    try:

        result = cloudinary.uploader.upload(
            image_bytes,
            folder=CLOUDINARY_FOLDER,
            public_id=str(rating_key),
            overwrite=True,
            invalidate=True,
            resource_type="image",
            format="webp"
        )

        return result["secure_url"]

    except Exception as e:

        print(
            f"[CLOUDINARY ERROR] "
            f"{rating_key}: {e}"
        )

        return None

def build_poster_url(item):
    if not getattr(item, "thumb", None):
        return None

    if POSTER_PROVIDER == "local":

        os.makedirs(
            POSTER_DIR,
            exist_ok=True
        )

    key = str(item.ratingKey)

    # ======================
    # STABIELE BESTANDSNAAM
    # ======================

    filename = f"{key}.webp"

    if POSTER_PROVIDER == "local":

        local_file = os.path.join(
            POSTER_DIR,
            filename
        )

        public_url = (
            f"{POSTER_PUBLIC_URL}/{filename}"
        )

        if os.path.exists(local_file):
            return public_url

    # ======================
    # DOWNLOAD POSTER
    # ======================
    try:
        thumb = item.thumb
        if thumb.startswith("http://") or thumb.startswith("https://"):
            try:
                thumb = "/" + thumb.split("/", 3)[3]
            except:
                pass
        poster_url = (
            f"{PLEX_DOWNLOAD_URL}{thumb}"
            f"?X-Plex-Token={PLEX_TOKEN}"
        )
        response = requests.get(
            poster_url,
            timeout=30
        )
        response.raise_for_status()
        img = Image.open(
            BytesIO(response.content)
        ).convert("RGB")
        img.thumbnail(
            (
                POSTER_WIDTH,
                POSTER_HEIGHT
            ),
            Image.LANCZOS
        )
        # ======================
        # CLOUDINARY
        # ======================

        if POSTER_PROVIDER == "cloudinary":

            buffer = BytesIO()

            img.save(
                buffer,
                "WEBP",
                quality=POSTER_QUALITY,
                method=6
            )

            buffer.seek(0)

            cloud_url = upload_to_cloudinary(
                buffer,
                key
            )

            if cloud_url:

                print(
                    f"[POSTER] Uploaded: "
                    f"{key} -> {cloud_url}"
                )

                return cloud_url

            return None

        # ======================
        # LOCAL SAVE
        # ======================

        img.save(
            local_file,
            "WEBP",
            quality=POSTER_QUALITY,
            method=6
        )

        print(
            f"[POSTER] Cached: {filename}"
        )

        return public_url
    except Exception as e:
        print(
            f"[POSTER ERROR] "
            f"{key}: {e}"
        )
        return None
# ======================
# GET LABELS
# ======================
def get_labels(item):
    try:
        return [
            label.tag.lower()
            for label in item.labels
        ]
    except:
        return []
# ======================
# PROCESS ITEM
# ======================
def process_item(
    cache,
    item,
    media_type
):
    key = str(item.ratingKey)
    url = build_watch_url(
        item,
        media_type
    )
    poster = build_poster_url(item)
    labels = get_labels(item)
    cache[key] = {
        "rating_key": key,
        "title": item.title,
        "type": media_type,
        # belangrijk voor library grouping
        "library_name": item.librarySectionTitle,
        "section": item.librarySectionTitle,
        "url": url,
        "poster": poster,
        "labels": labels
    }
    print(
        f"[CACHE] "
        f"{media_type.upper()} | "
        f"{item.title}"
    )
# ======================
# CONFIG VALIDATION
# ======================

def validate_config():

    print(
        f"[POSTER PROVIDER] "
        f"{POSTER_PROVIDER}"
    )

    required = [
        ("PLEX_URL", PLEX_URL),
        ("PLEX_DOWNLOAD_URL", PLEX_DOWNLOAD_URL),
        ("PLEX_TOKEN", PLEX_TOKEN)
    ]

    if POSTER_PROVIDER == "local":

        required += [
            ("POSTER_PUBLIC_URL", POSTER_PUBLIC_URL)
        ]

    if POSTER_PROVIDER == "cloudinary":

        required += [
            ("CLOUDINARY_CLOUD_NAME", CLOUDINARY_CLOUD_NAME),
            ("CLOUDINARY_API_KEY", CLOUDINARY_API_KEY),
            ("CLOUDINARY_API_SECRET", CLOUDINARY_API_SECRET)
        ]

    missing = [
        name
        for name, value in required
        if not value
    ]

    if missing:

        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )

# ======================
# CLOUDINARY SETUP
# ======================

def configure_cloudinary():

    if POSTER_PROVIDER != "cloudinary":
        return

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )

    print(
        f"[CLOUDINARY] "
        f"Folder: {CLOUDINARY_FOLDER}"
    )

# ======================
# MAIN
# ======================
def main():
    plex = PlexServer(
        PLEX_URL,
        PLEX_TOKEN
    )
    cache = load_cache()
    print(
        f"Loaded cache: "
        f"{len(cache)} items"
    )
    # ======================
    # MOVIES
    # ======================
    movie_sections = [
        s for s in plex.library.sections()
        if s.type == "movie"
    ]
    for section in movie_sections:
        print(
            f"[SECTION] Movies: "
            f"{section.title}"
        )
        movies = section.all()
        for movie in movies:
            process_item(
                cache,
                movie,
                "movie"
            )
    # ======================
    # SHOWS
    # ======================
    show_sections = [
        s for s in plex.library.sections()
        if s.type == "show"
    ]
    for section in show_sections:
        print(
            f"[SECTION] Shows: "
            f"{section.title}"
        )
        shows = section.all()
        for show in shows:
            process_item(
                cache,
                show,
                "show"
            )
    # ======================
    # CLEANUP CACHE
    # ======================
    cleaned = {
        k: v for k, v in cache.items()
        if v.get("url")
    }
    save_cache(cleaned)
    print(
        f"Done. "
        f"Total cache: "
        f"{len(cleaned)} items"
    )
# ======================
# START
# ======================
if __name__ == "__main__":

    validate_config()
    configure_cloudinary()
    main()

