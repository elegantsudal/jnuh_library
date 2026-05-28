import os
import re
from pathlib import Path

import pymysql
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from pymysql.cursors import DictCursor
from pymysql.err import IntegrityError, MySQLError
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")
XP_PER_RECORD = 10

DEFAULT_THEME_CARDS = (
    {
        "name": "과학",
        "description": "호기심과 실험으로 세상을 이해하는 공동탐구 테마",
        "image": "images/themes/science.jpeg",
    },
    {
        "name": "사회",
        "description": "사람과 공동체, 세상의 규칙을 함께 읽는 테마",
        "image": "images/themes/society.avif",
    },
    {
        "name": "역사",
        "description": "과거의 사건과 인물을 통해 오늘을 바라보는 테마",
        "image": "images/themes/history.png",
    },
    {
        "name": "SF",
        "description": "상상력과 기술의 미래를 탐험하는 테마",
        "image": "images/themes/sf.png",
    },
    {
        "name": "청소년 소설",
        "description": "성장과 관계를 깊이 있게 나누는 이야기 테마",
        "image": "images/themes/growth.jpeg",
    },
    {
        "name": "예술",
        "description": "감수성과 표현을 넓혀 주는 창작 탐구 테마",
        "image": "images/themes/art.jpeg",
    },
)

THEME_TITLE_RULES = {
    "\uacfc\ud559": (
        (150, "\ubbf8\ub798\uc758 \uacfc\ud559\uc790"),
        (100, "\uacfc\ud559\uc774 \uc88b\uc544!"),
        (50, "\uacfc\ud559 \uafc8\ub098\ubb34"),
    ),
    "\uc0ac\ud68c": (
        (150, "IT\uc0ac\ud68c"),
        (100, "\uacf5\uc5c5 \uc0ac\ud68c"),
        (50, "\ub18d\uc5c5 \uc0ac\ud68c"),
    ),
    "\uc5ed\uc0ac": (
        (150, "\ud604\ub300"),
        (100, "\uadfc\ub300"),
        (50, "\uace0\ub300"),
    ),
    "SF": (
        (150, "\ucc4c\ub9b0\uc800"),
        (100, "\ub2e4\uc774\uc544"),
        (50, "\uc544\uc774\uc5b8"),
    ),
    "\uccad\uc18c\ub144 \uc18c\uc124": (
        (150, "\uc5b4\ub978"),
        (100, "\uccad\uc18c\ub144"),
        (50, "\uc5b4\ub9b0\uc774"),
    ),
    "\uc608\uc220": (
        (150, "\uc804\uacf5\uc0dd"),
        (100, "\uc785\uc2dc\uc0dd"),
        (50, "\ucde8\ubbf8\uc0dd"),
    ),
}

WORKBOOK_KEYWORDS = (
    "문제집",
    "기출",
    "모의고사",
    "수능",
    "내신",
    "평가문제",
    "학원평가",
    "예상문제",
    "학습지",
    "연습장",
    "워크북",
)

CHILDREN_CATEGORY_KEYWORDS = (
    "어린이",
    "아동",
    "유아",
    "초등",
    "청소년",
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_aladin_api_key():
    return (
        os.getenv("ALADIN_API_KEY")
        or os.getenv("ALADIN_TTB_KEY")
        or os.getenv("TTB_KEY")
    )

def get_db_config(autocommit=True):
    print("DB_HOST:", os.getenv("DB_HOST"))
    config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": autocommit,
    }

    missing = [key for key, value in config.items()
               if key in ("host", "user", "password", "database") and not value]

    if missing:
        raise RuntimeError(
            f"데이터베이스 설정 누락: {', '.join(missing)}"
        )

    return config


def get_db_connection(autocommit=True):
    return pymysql.connect(**get_db_config(autocommit=autocommit))


def fetch_user_by_id(user_id):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, email, created_at
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()


def fetch_user_by_username(username):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, password_hash, email, created_at
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            return cursor.fetchone()


def fetch_user_by_email(email):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, email, created_at
                FROM users
                WHERE email = %s
                """,
                (email,),
            )
            return cursor.fetchone()


def ensure_reading_game_schema():
    theme_rows = [
        (theme["name"], theme["description"])
        for theme in DEFAULT_THEME_CARDS
    ]

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT IGNORE INTO themes (theme_name, description)
                VALUES (%s, %s)
                """,
                theme_rows,
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS book_records (
                    record_id INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id INT(10) UNSIGNED NOT NULL,
                    theme_id INT(10) UNSIGNED NOT NULL,
                    book_title VARCHAR(255) NOT NULL,
                    reflection TEXT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (record_id),
                    KEY idx_book_records_user_created (user_id, created_at),
                    KEY idx_book_records_theme_created (theme_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )


def fetch_theme_by_name(theme_name, connection=None):
    query = """
        SELECT theme_id, theme_name, description
        FROM themes
        WHERE theme_name = %s
    """

    if connection is None:
        with get_db_connection() as owned_connection:
            with owned_connection.cursor() as cursor:
                cursor.execute(query, (theme_name,))
                return cursor.fetchone()

    with connection.cursor() as cursor:
        cursor.execute(query, (theme_name,))
        return cursor.fetchone()


def get_theme_title(theme_name, xp_points):
    for threshold, title in THEME_TITLE_RULES.get(theme_name, ()):
        if xp_points >= threshold:
            return title
    return ""


def fetch_user_theme_dashboard(user_id):
    theme_names = [theme["name"] for theme in DEFAULT_THEME_CARDS]
    placeholders = ", ".join(["%s"] * len(theme_names))

    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    t.theme_id,
                    t.theme_name,
                    t.description,
                    COALESCE(utx.xp_points, 0) AS xp_points
                FROM themes t
                LEFT JOIN user_theme_xp utx
                    ON utx.theme_id = t.theme_id
                    AND utx.user_id = %s
                WHERE t.theme_name IN ({placeholders})
                """,
                (user_id, *theme_names),
            )
            rows = cursor.fetchall()

    row_by_name = {row["theme_name"]: row for row in rows}
    dashboard = []

    for theme in DEFAULT_THEME_CARDS:
        row = row_by_name.get(theme["name"], {})
        xp_points = int(row.get("xp_points") or 0)
        dashboard.append(
            {
                "theme_name": theme["name"],
                "description": row.get("description") or theme["description"],
                "xp_points": xp_points,
                "theme_title": get_theme_title(theme["name"], xp_points),
            }
        )

    return dashboard


def fetch_recent_book_records(user_id, limit=5):
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    br.record_id,
                    br.book_title,
                    br.reflection,
                    br.created_at,
                    t.theme_name
                FROM book_records br
                INNER JOIN themes t
                    ON t.theme_id = br.theme_id
                WHERE br.user_id = %s
                ORDER BY br.created_at DESC, br.record_id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return cursor.fetchall()


def save_book_record(user_id, theme_name, book_title, reflection):
    with get_db_connection(autocommit=False) as connection:
        try:
            theme = fetch_theme_by_name(theme_name, connection=connection)
            if not theme:
                raise ValueError("선택한 테마를 찾을 수 없습니다.")

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO book_records (user_id, theme_id, book_title, reflection)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, theme["theme_id"], book_title, reflection or None),
                )
                cursor.execute(
                    """
                    INSERT INTO user_theme_xp (user_id, theme_id, xp_points)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE xp_points = xp_points + VALUES(xp_points)
                    """,
                    (user_id, theme["theme_id"], XP_PER_RECORD),
                )
                cursor.execute(
                    """
                    SELECT xp_points
                    FROM user_theme_xp
                    WHERE user_id = %s AND theme_id = %s
                    """,
                    (user_id, theme["theme_id"]),
                )
                xp_row = cursor.fetchone()

            connection.commit()
            return {
                "theme_name": theme["theme_name"],
                "xp_points": int((xp_row or {}).get("xp_points") or 0),
            }
        except Exception:
            connection.rollback()
            raise


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    try:
        user = fetch_user_by_id(user_id)
    except (RuntimeError, MySQLError):
        return None

    if not user:
        session.clear()

    return user


def is_workbook(item):
    searchable_text = " ".join(
        str(item.get(field, ""))
        for field in (
            "title",
            "title_info",
            "categoryName",
            "description",
            "publisher",
            "pub_info",
            "kdc_name_1s",
        )
    )
    return any(keyword in searchable_text for keyword in WORKBOOK_KEYWORDS)


def is_children_book(item):
    searchable_text = " ".join(
        str(item.get(field, ""))
        for field in (
            "categoryName",
            "title",
            "title_info",
            "description",
            "type_name",
            "place_info",
            "manage_name",
            "kdc_name_1s",
        )
    )
    return any(keyword in searchable_text for keyword in CHILDREN_CATEGORY_KEYWORDS)


def get_aladin_query_type(query_type):
    return "Title" if query_type == "Title" else "Keyword"


def extract_aladin_items(data):
    if not isinstance(data, dict):
        return []

    items = data.get("item")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]

    return []


def get_aladin_error_message(data):
    if not isinstance(data, dict):
        return None

    error_message = str(data.get("errorMessage") or data.get("message") or "").strip()
    if error_message:
        return error_message

    return None


def request_aladin_api(url, params):
    timeout = (
        float(os.getenv("ALADIN_API_CONNECT_TIMEOUT", "5")),
        float(os.getenv("ALADIN_API_READ_TIMEOUT", "15")),
    )

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ProxyError:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()


def get_aladin_request_error_message(exc):
    if isinstance(exc, requests.exceptions.ProxyError):
        return (
            "알라딘 API 프록시 연결에 실패했습니다. "
            "회사/학교 프록시를 쓰지 않는 환경이면 HTTP_PROXY, HTTPS_PROXY 설정을 확인해주세요."
        )

    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return "알라딘 API 서버 연결이 지연되고 있습니다. 네트워크 상태를 확인한 뒤 다시 시도해주세요."

    if isinstance(exc, requests.exceptions.ReadTimeout):
        return "알라딘 API 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."

    if isinstance(exc, requests.exceptions.SSLError):
        return "알라딘 API SSL 연결에 실패했습니다. 네트워크 보안 프로그램이나 인증서 환경을 확인해주세요."

    if isinstance(exc, requests.exceptions.ConnectionError):
        return "알라딘 API 서버에 연결하지 못했습니다. 네트워크 상태를 확인해주세요."

    return "알라딘 API 요청에 실패했습니다."


def map_aladin_book(item):
    publish_year = str(item.get("pubDate") or "").strip().split("-")[0]
    return {
        "title": item.get("title", "제목 없음"),
        "author": item.get("author", "저자 정보 없음"),
        "publisher": item.get("publisher", ""),
        "publish_year": publish_year,
        "location": item.get("categoryName", ""),
        "type": "도서",
        "isbn": item.get("isbn13") or item.get("isbn") or "",
        "cover": item.get("cover", ""),
        "link": item.get("link", ""),
    }


def get_json_payload():
    return request.get_json(silent=True) or request.form or {}


@app.route("/")
def home():
    current_user = get_current_user()
    theme_stats = []
    recent_records = []
    activity_error = None
    total_xp = 0
    profile_initial = ""

    if current_user:
        profile_initial = (current_user["username"] or "?")[:1].upper()
        try:
            ensure_reading_game_schema()
            theme_stats = fetch_user_theme_dashboard(current_user["user_id"])
            recent_records = fetch_recent_book_records(current_user["user_id"])
            total_xp = sum(stat["xp_points"] for stat in theme_stats)
        except RuntimeError as exc:
            activity_error = str(exc)
        except MySQLError:
            activity_error = "테마 활동 정보를 불러오지 못했습니다. 데이터베이스 연결을 확인해주세요."

    return render_template(
        "index.html",
        current_user=current_user,
        theme_cards=DEFAULT_THEME_CARDS,
        theme_stats=theme_stats,
        recent_records=recent_records,
        activity_error=activity_error,
        xp_per_record=XP_PER_RECORD,
        total_xp=total_xp,
        profile_initial=profile_initial,
    )


@app.post("/signup")
def signup():
    data = get_json_payload()
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not username or not email or not password or not confirm_password:
        return jsonify({"ok": False, "message": "모든 항목을 입력해주세요."}), 400

    if len(username) < 3:
        return jsonify({"ok": False, "message": "아이디는 3자 이상이어야 합니다."}), 400

    if not EMAIL_PATTERN.match(email):
        return jsonify({"ok": False, "message": "올바른 이메일 형식이 아닙니다."}), 400

    if len(password) < 8:
        return jsonify({"ok": False, "message": "비밀번호는 8자 이상으로 설정해주세요."}), 400

    if password != confirm_password:
        return jsonify({"ok": False, "message": "비밀번호 확인이 일치하지 않습니다."}), 400

    try:
        if fetch_user_by_username(username):
            return jsonify({"ok": False, "message": "이미 사용 중인 아이디입니다."}), 409

        if fetch_user_by_email(email):
            return jsonify({"ok": False, "message": "이미 사용 중인 이메일입니다."}), 409

        password_hash = generate_password_hash(password)

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, email, created_at)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (username, password_hash, email),
                )
                user_id = cursor.lastrowid

        session["user_id"] = user_id
        return jsonify(
            {
                "ok": True,
                "message": "회원가입이 완료되었습니다.",
                "user": {"user_id": user_id, "username": username, "email": email},
            }
        )
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
    except IntegrityError:
        return jsonify({"ok": False, "message": "이미 등록된 회원 정보입니다."}), 409
    except MySQLError as e:
        print("MYSQL ERROR:", e)
        return jsonify(
            {
                "ok": False,
                "message": "데이터베이스에 회원 정보를 저장하지 못했습니다.",
            }
        ), 500


@app.post("/login")
def login():
    data = get_json_payload()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"ok": False, "message": "아이디와 비밀번호를 입력해주세요."}), 400

    try:
        user = fetch_user_by_username(username)
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
    except MySQLError:
        return jsonify({"ok": False, "message": "데이터베이스에 연결할 수 없습니다."}), 500

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"ok": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 401

    session["user_id"] = user["user_id"]
    return jsonify(
        {
            "ok": True,
            "message": "로그인되었습니다.",
            "user": {
                "user_id": user["user_id"],
                "username": user["username"],
                "email": user["email"],
            },
        }
    )


@app.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True, "message": "로그아웃되었습니다."})


@app.post("/record-book")
def record_book():
    current_user = get_current_user()
    if not current_user:
        return jsonify({"ok": False, "message": "로그인 후 기록을 남겨주세요."}), 401

    data = get_json_payload()
    theme_name = (data.get("theme_name") or "").strip()
    book_title = (data.get("book_title") or "").strip()
    reflection = (data.get("reflection") or "").strip()

    allowed_theme_names = {theme["name"] for theme in DEFAULT_THEME_CARDS}

    if theme_name not in allowed_theme_names:
        return jsonify({"ok": False, "message": "테마를 먼저 선택해주세요."}), 400

    if not book_title:
        return jsonify({"ok": False, "message": "읽은 책 제목을 입력해주세요."}), 400

    if len(book_title) > 255:
        return jsonify({"ok": False, "message": "책 제목은 255자 이내로 입력해주세요."}), 400

    if len(reflection) > 1000:
        return jsonify({"ok": False, "message": "감상은 1000자 이내로 입력해주세요."}), 400

    try:
        ensure_reading_game_schema()
        saved = save_book_record(
            current_user["user_id"],
            theme_name,
            book_title,
            reflection,
        )
    except RuntimeError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except MySQLError:
        return jsonify({"ok": False, "message": "도서 기록을 저장하지 못했습니다."}), 500

    return jsonify(
        {
            "ok": True,
            "message": f"{saved['theme_name']} 테마에 기록을 남겼습니다. XP {XP_PER_RECORD}점을 획득했어요.",
            "theme_name": saved["theme_name"],
            "xp_points": saved["xp_points"],
        }
    )


@app.route("/search")
def search():
    if not get_current_user():
        return jsonify({"error": "로그인 후 도서 검색을 이용해주세요.", "books": []}), 401

    query = (request.args.get("q") or "").strip()
    query_type = (request.args.get("queryType") or "Title").strip()
    api_key = get_aladin_api_key()

    if query_type not in {"Title", "Keyword"}:
        query_type = "Title"

    if not query:
        return jsonify({"error": "검색어를 입력해주세요.", "books": []}), 400

    if not api_key:
        return (
            jsonify(
                {
                    "error": ".env 파일에 ALADIN_API_KEY를 설정해주세요.",
                    "books": [],
                }
            ),
            500,
        )

    url = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
    params = {
        "ttbkey": api_key,
        "Query": query,
        "QueryType": get_aladin_query_type(query_type),
        "MaxResults": 20,
        "start": 1,
        "SearchTarget": "Book",
        "output": "js",
        "Version": "20131101",
        "Cover": "Big",
    }

    try:
        data = request_aladin_api(url, params)
    except requests.RequestException as exc:
        app.logger.warning("Aladin API request failed: %s", exc)
        return jsonify({"error": get_aladin_request_error_message(exc), "books": []}), 502
    except ValueError:
        return jsonify({"error": "알라딘 API 응답을 해석할 수 없습니다.", "books": []}), 502

    error_message = get_aladin_error_message(data)
    if error_message:
        return jsonify({"error": error_message, "books": []}), 502

    preferred_books = []
    fallback_books = []

    for item in extract_aladin_items(data):
        if is_workbook(item):
            continue

        book = map_aladin_book(item)

        if is_children_book(item):
            preferred_books.append(book)
        else:
            fallback_books.append(book)

    books = (preferred_books + fallback_books)[:10]

    return jsonify({"error": None, "books": books})


if __name__ == "__main__":
    app.run(debug=True)
