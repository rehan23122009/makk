from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pypdf import PdfReader
import hashlib
import io
import os
import secrets
import sqlite3
from datetime import date

app = FastAPI()

DB_PATH = "makk.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER NOT NULL,
            usage_date TEXT NOT NULL,
            question_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, usage_date)
        )
    """)

    connection.commit()
    connection.close()


def hash_password(password):
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    ).hex()

    return f"{salt}:{password_hash}"


def verify_password(password, stored_password):
    try:
        salt, password_hash = stored_password.split(":")
        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        ).hex()

        return secrets.compare_digest(new_hash, password_hash)
    except Exception:
        return False


def get_current_user(request):
    token = request.cookies.get("makk_session")

    if not token:
        return None

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT users.id, users.email
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token = ?
    """, (token,))

    user = cursor.fetchone()
    connection.close()

    return user


def get_question_count(user_id):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT question_count
        FROM usage
        WHERE user_id = ? AND usage_date = ?
    """, (user_id, date.today().isoformat()))

    result = cursor.fetchone()
    connection.close()

    return result["question_count"] if result else 0


def increase_question_count(user_id):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO usage (user_id, usage_date, question_count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, usage_date)
        DO UPDATE SET question_count = question_count + 1
    """, (user_id, date.today().isoformat()))

    connection.commit()
    connection.close()


def search_text(text, question):
    words = [
        word for word in question.lower().split()
        if len(word) > 2
    ]

    if not words:
        return []

    matches = []

    for line in text.split("\n"):
        line_lower = line.lower()

        if any(word in line_lower for word in words):
            matches.append(line.strip())

    return matches


def make_answer(matches):
    if not matches:
        return "I could not find a matching answer in your documents."

    return "<br><br>".join(matches[:10])


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
      <head>
        <title>MAKK Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>MAKK</h1>
        <p>Your company AI knowledge assistant</p>

        <form action="/login" method="post">
          <p>Email</p>
          <input name="email" type="email" required style="width:100%; padding:12px; margin-bottom:12px;">
          <p>Password</p>
          <input name="password" type="password" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Login</button>
        </form>

        <p style="margin-top:20px;">Demo account:</p>
        <p>demo@makk.ai</p>
        <p>demo1234</p>

        <p style="margin-top:20px;"><a href="/signup" style="color:#4f8cff;">Create account</a></p>

        <p style="margin-top:20px;">
          <a href="/privacy" style="color:#4f8cff;">Privacy</a>
          |
          <a href="/terms" style="color:#4f8cff;">Terms</a>
          |
          <a href="/security" style="color:#4f8cff;">Security</a>
        </p>
      </body>
    </html>
    """


@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, email, password_hash
        FROM users
        WHERE email = ?
    """, (email,))

    user = cursor.fetchone()
    connection.close()

    if not user or not verify_password(password, user["password_hash"]):
        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h2>Login failed</h2>
            <p>Wrong email or password.</p>
            <a href="/" style="color:#4f8cff;">Try again</a>
          </body>
        </html>
        """)

    token = secrets.token_hex(32)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO sessions (token, user_id)
        VALUES (?, ?)
    """, (token, user["id"]))

    connection.commit()
    connection.close()

    response = RedirectResponse(url="/workspace", status_code=303)
    response.set_cookie(
        key="makk_session",
        value=token,
        httponly=True,
        samesite="lax"
    )

    return response


@app.get("/signup", response_class=HTMLResponse)
def signup_page():
    return """
    <html>
      <head>
        <title>MAKK Signup</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Create MAKK account</h1>

        <form action="/signup" method="post">
          <p>Email</p>
          <input name="email" type="email" required style="width:100%; padding:12px; margin-bottom:12px;">
          <p>Password</p>
          <input name="password" type="password" minlength="8" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Create account</button>
        </form>

        <a href="/" style="color:#4f8cff;">Back to login</a>
      </body>
    </html>
    """


@app.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):
    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id
        FROM users
        WHERE email = ?
    """, (email,))

    existing_user = cursor.fetchone()

    if existing_user:
        connection.close()

        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h2>Account already exists</h2>
            <a href="/signup" style="color:#4f8cff;">Try another email</a>
          </body>
        </html>
        """)

    cursor.execute("""
        INSERT INTO users (email, password_hash)
        VALUES (?, ?)
    """, (email, hash_password(password)))

    connection.commit()
    connection.close()

    return HTMLResponse("""
    <html>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h2>Account created</h2>
        <p>You can now login.</p>
        <a href="/" style="color:#4f8cff;">Login</a>
      </body>
    </html>
    """)


@app.get("/workspace", response_class=HTMLResponse)
def workspace(request: Request):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, text, created_at
        FROM documents
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user["id"],))

    docs = cursor.fetchall()

    cursor.execute("""
        SELECT question, answer, sources, created_at
        FROM questions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (user["id"],))

    history = cursor.fetchall()
    connection.close()

    doc_list = ""

    for doc in docs:
        doc_list += f"""
        <p>{doc['name']} — {len(doc['text'].split())} words
        <a href="/document/{doc['id']}" style="color:#4f8cff;">Open</a>
        |
        <a href="/delete/{doc['id']}" style="color:#ff6b6b;">Delete</a>
        </p>
        """

    history_html = ""

    if history:
        history_items = ""

        for item in history:
            history_items += f"""
            <li>
                <b>{item['question']}</b><br>
                {item['answer'][:200]}...
            </li>
            """

        history_html = f"""
        <h2>Recent questions</h2>
        <ul>{history_items}</ul>
        <a href="/clear-history"
           style="display:inline-block; padding:8px 16px; background:#ff6b6b; color:white; border-radius:8px; text-decoration:none;">
            Clear history
        </a>
        """

    used = len(docs)
    remaining = max(0, 3 - used)
    questions_used = get_question_count(user["id"])

    return f"""
    <html>
      <head>
        <title>MAKK Workspace</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>MAKK Enterprise Workspace</h1>
        <p>Welcome, {user['email']}</p>

        <h2>Your plan</h2>
        <p>Documents: {used} / 3</p>
        <p>Questions used today: {questions_used} / 10</p>

        <h2>Your documents</h2>
        {doc_list if doc_list else "<p>No documents uploaded yet.</p>"}

        <h2>Upload documents</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
          <input name="files" type="file" accept=".pdf,.txt" multiple required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Upload</button>
        </form>

        <h2>Ask MAKK</h2>
        <form action="/ask" method="post">
          <input name="question" type="text" placeholder="Ask about all documents" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Ask MAKK</button>
        </form>

        {history_html}

        <p style="margin-top:20px;">
          <a href="/pricing" style="color:#4f8cff;">View pricing</a>
          |
          <a href="/privacy" style="color:#4f8cff;">Privacy</a>
          |
          <a href="/terms" style="color:#4f8cff;">Terms</a>
          |
          <a href="/security" style="color:#4f8cff;">Security</a>
        </p>
      </body>
    </html>
    """


@app.post("/upload", response_class=HTMLResponse)
def upload(request: Request, files: list[UploadFile] = File(...)):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM documents
        WHERE user_id = ?
    """, (user["id"],))

    current_count = cursor.fetchone()["total"]

    if current_count >= 3:
        connection.close()

        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h1>Free plan limit reached</h1>
            <p>You can upload up to 3 documents on the Free plan.</p>
            <p>Upgrade to upload unlimited documents.</p>
            <a href="/pricing" style="color:#4f8cff;">View pricing</a>
          </body>
        </html>
        """)

    allowed = 3 - current_count
    added = 0

    for file in files:
        if added >= allowed:
            break

        filename = file.filename
        content = file.file.read()

        if filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            text = content.decode("utf-8", errors="ignore")

        cursor.execute("""
            INSERT INTO documents (user_id, name, text)
            VALUES (?, ?, ?)
        """, (user["id"], filename, text))

        added += 1

    connection.commit()
    connection.close()

    return f"""
    <html>
      <head>
        <title>MAKK Upload</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>{added} document(s) uploaded</h1>
        <p>MAKK can now answer questions from all your documents.</p>
        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.post("/ask", response_class=HTMLResponse)
def ask(request: Request, question: str = Form(...)):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    if get_question_count(user["id"]) >= 10:
        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h1>Daily limit reached</h1>
            <p>You have used 10 questions today.</p>
            <p>Your limit will reset tomorrow.</p>
            <a href="/pricing" style="color:#4f8cff;">View pricing</a>
          </body>
        </html>
        """)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, text
        FROM documents
        WHERE user_id = ?
    """, (user["id"],))

    docs = cursor.fetchall()
    connection.close()

    if not docs:
        answer = "Please upload documents first."
        sources = ""
    else:
        all_matches = []

        for doc in docs:
            matches = search_text(doc["text"], question)

            for match in matches:
                all_matches.append(f"<b>{doc['name']}</b><br>{match}")

        answer = make_answer(all_matches)
        sources = "<br>".join(sorted(set(doc["name"] for doc in docs)))

    increase_question_count(user["id"])

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO questions (user_id, question, answer, sources)
        VALUES (?, ?, ?, ?)
    """, (user["id"], question, answer, sources))

    connection.commit()
    connection.close()

    return f"""
    <html>
      <head>
        <title>MAKK Answer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>MAKK Answer</h1>
        <p><b>Your question:</b></p>
        <p>{question}</p>

        <p><b>MAKK says:</b></p>
        <p>{answer}</p>

        <p><b>Sources:</b></p>
        <p>{sources}</p>

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.get("/pricing", response_class=HTMLResponse)
def pricing():
    return """
    <html>
      <head>
        <title>MAKK Pricing</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>MAKK Pricing</h1>

        <h2>Free</h2>
        <p>$0 / month</p>
        <p>3 documents</p>
        <p>10 questions per day</p>

        <h2>Team</h2>
        <p>$9 / user / month</p>
        <p>Unlimited documents</p>
        <p>500 questions per user / month</p>

        <h2>Business</h2>
        <p>$19 / user / month</p>
        <p>Advanced AI</p>
        <p>Permissions and admin controls</p>

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return """
    <html>
      <head>
        <title>MAKK Privacy Policy</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Privacy Policy</h1>

        <p>MAKK helps users upload documents and ask questions about them.</p>

        <h2>Information we collect</h2>
        <p>We may collect your email address, password hash, uploaded document text, questions, and question history.</p>

        <h2>How we use information</h2>
        <p>We use this information to provide MAKK services, answer questions, and improve the product.</p>

        <h2>Document data</h2>
        <p>Documents you upload are used to answer your questions. Do not upload confidential or sensitive information unless you understand how it will be stored and used.</p>

        <h2>Data storage</h2>
        <p>MAKK currently stores data in a SQLite database on the application server.</p>

        <h2>Data deletion</h2>
        <p>You can delete uploaded documents from your workspace. You may also contact us to request account deletion.</p>

        <h2>Contact</h2>
        <p>For privacy questions, contact: support@makk.ai</p>

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.get("/terms", response_class=HTMLResponse)
def terms():
    return """
    <html>
      <head>
        <title>MAKK Terms of Service</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Terms of Service</h1>

        <p>By using MAKK, you agree to these terms.</p>

        <h2>Use of service</h2>
        <p>You may use MAKK only for lawful purposes. Do not upload content you do not have permission to use.</p>

        <h2>Account responsibility</h2>
        <p>You are responsible for keeping your account password safe and for all activity under your account.</p>

        <h2>Document ownership</h2>
        <p>You retain ownership of documents you upload. You give MAKK permission to process those documents to provide answers and summaries.</p>

        <h2>Accuracy</h2>
        <p>MAKK may provide incomplete or incorrect information. Always verify important information from the original document.</p>

        <h2>Service availability</h2>
        <p>MAKK may change, pause, or stop the service at any time.</p>

        <h2>Contact</h2>
        <p>For questions, contact: support@makk.ai</p>

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.get("/security", response_class=HTMLResponse)
def security():
    return """
    <html>
      <head>
        <title>MAKK Security</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Security</h1>

        <p>MAKK is designed to help teams work with their documents securely.</p>

        <h2>Current security practices</h2>
        <p>MAKK uses login accounts, password hashing, and session-based authentication to separate user workspaces.</p>

        <h2>Data handling</h2>
        <p>MAKK currently stores uploaded document text, user accounts, and question history in a SQLite database on the application server.</p>

        <h2>Important notice</h2>
        <p>This is an early demo product. Do not upload highly confidential, financial, medical, legal, or other sensitive documents unless you understand the current limitations.</p>

        <h2>Security improvements</h2>
        <p>We plan to improve encryption, access controls, audit logging, backups, and enterprise security controls.</p>

        <h2>Contact</h2>
        <p>For security questions, contact: security@makk.ai</p>

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.get("/delete/{doc_id}")
def delete_document(request: Request, doc_id: int):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name
        FROM documents
        WHERE id = ? AND user_id = ?
    """, (doc_id, user["id"]))

    document = cursor.fetchone()
    connection.close()

    if not document:
        return RedirectResponse(url="/workspace", status_code=303)

    return f"""
    <html>
      <head>
        <title>Delete document</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Delete document?</h1>
        <p>Are you sure you want to delete:</p>
        <p><b>{document['name']}</b></p>

        <a href="/confirm-delete/{document['id']}"
           style="display:inline-block; padding:10px 18px; background:#ff6b6b; color:white; border-radius:8px; text-decoration:none;">
            Yes, delete
        </a>

        <a href="/workspace"
           style="display:inline-block; padding:10px 18px; background:#4f8cff; color:white; border-radius:8px; text-decoration:none;">
            Cancel
        </a>
      </body>
    </html>
    """


@app.get("/confirm-delete/{doc_id}")
def confirm_delete(request: Request, doc_id: int):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM documents
        WHERE id = ? AND user_id = ?
    """, (doc_id, user["id"]))

    connection.commit()
    connection.close()

    return RedirectResponse(url="/workspace", status_code=303)


@app.get("/document/{doc_id}", response_class=HTMLResponse)
def document_preview(request: Request, doc_id: int):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, text
        FROM documents
        WHERE id = ? AND user_id = ?
    """, (doc_id, user["id"]))

    doc = cursor.fetchone()
    connection.close()

    if not doc:
        return RedirectResponse(url="/workspace", status_code=303)

    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]
    preview = "<br>".join(lines[:15])

    return f"""
    <html>
      <head>
        <title>MAKK Document</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Document preview</h1>
        <p><b>File:</b> {doc['name']}</p>
        <p><b>Words:</b> {len(doc['text'].split())}</p>

        <h2>First 15 lines</h2>
        <p>{preview}</p>

        <h2>Ask about this document</h2>
        <form method="post" action="/document/{doc['id']}/ask">
            <input type="text" name="question" placeholder="Ask about this document" required
                   style="width:100%; padding:10px; margin:8px 0;">
            <button type="submit"
                    style="padding:10px 18px; background:#4f8cff; color:white; border:none; border-radius:8px;">
                Ask
            </button>
        </form>

        <a href="/document/{doc['id']}/summary"
           style="display:inline-block; padding:10px 18px; background:#22c55e; color:white; border-radius:8px; text-decoration:none;">
            Summarize
        </a>

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.post("/document/{doc_id}/ask", response_class=HTMLResponse)
def ask_document(request: Request, doc_id: int, question: str = Form(...)):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    if get_question_count(user["id"]) >= 10:
        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h1>Daily limit reached</h1>
            <p>You have used 10 questions today.</p>
            <p>Your limit will reset tomorrow.</p>
            <a href="/pricing" style="color:#4f8cff;">View pricing</a>
          </body>
        </html>
        """)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, text
        FROM documents
        WHERE id = ? AND user_id = ?
    """, (doc_id, user["id"]))

    doc = cursor.fetchone()
    connection.close()

    if not doc:
        return RedirectResponse(url="/workspace", status_code=303)

    matches = search_text(doc["text"], question)
    answer = make_answer(matches)

    increase_question_count(user["id"])

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO questions (user_id, question, answer, sources)
        VALUES (?, ?, ?, ?)
    """, (user["id"], question, answer, doc["name"]))

    connection.commit()
    connection.close()

    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]
    preview = "<br>".join(lines[:15])

    answer_html = f"""
    <div style="background:#16233d; padding:15px; border-radius:10px; margin-top:15px;">
        <b>Answer:</b>
        <p>{answer}</p>
    </div>
    """

    return f"""
    <html>
      <head>
        <title>MAKK Document</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Document preview</h1>
        <p><b>File:</b> {doc['name']}</p>
        <p><b>Words:</b> {len(doc['text'].split())}</p>

        <h2>First 15 lines</h2>
        <p>{preview}</p>

        <h2>Ask about this document</h2>
        <form method="post" action="/document/{doc['id']}/ask">
            <input type="text" name="question" placeholder="Ask about this document" required
                   style="width:100%; padding:10px; margin:8px 0;">
            <button type="submit"
                    style="padding:10px 18px; background:#4f8cff; color:white; border:none; border-radius:8px;">
                Ask
            </button>
        </form>

        {answer_html}

        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """


@app.get("/document/{doc_id}/summary", response_class=HTMLResponse)
def document_summary(request: Request, doc_id: int):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, text
        FROM documents
        WHERE id = ? AND user_id = ?
    """, (doc_id, user["id"]))

    doc = cursor.fetchone()
    connection.close()

    if not doc:
        return RedirectResponse(url="/workspace", status_code=303)

    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]

    keywords = [
        "প্রকল্প",
        "সাক্ষাৎকার",
        "প্রতিবেদক",
        "তারিখ",
        "শিক্ষার্থী",
        "সৌরভ",
        "project",
        "interview",
        "date",
        "student"
    ]

    important_lines = []

    for line in lines:
        if any(keyword in line.lower() for keyword in keywords):
            important_lines.append(line)

    if not important_lines:
        important_lines = lines[:10]

    summary = "<br>".join(important_lines[:10])

    return f"""
    <html>
      <head>
        <title>MAKK Summary</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Document summary</h1>
        <p><b>File:</b> {doc['name']}</p>

        <div style="background:#16233d; padding:15px; border-radius:10px; margin-top:15px;">
            <b>Summary:</b>
            <p>{summary}</p>
        </div>

        <a href="/document/{doc['id']}/summary/download"
           style="display:inline-block; padding:10px 18px; background:#4f8cff; color:white; border-radius:8px; text-decoration:none; margin-bottom:15px;">
            Download summary
        </a>

        <a href="/document/{doc['id']}" style="color:#4f8cff;">Back to document</a>
      </body>
    </html>
    """


@app.get("/document/{doc_id}/summary/download")
def download_summary(request: Request, doc_id: int):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, text
        FROM documents
        WHERE id = ? AND user_id = ?
    """, (doc_id, user["id"]))

    doc = cursor.fetchone()
    connection.close()

    if not doc:
        return RedirectResponse(url="/workspace", status_code=303)

    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]

    keywords = [
        "প্রকল্প",
        "সাক্ষাৎকার",
        "প্রতিবেদক",
        "তারিখ",
        "শিক্ষার্থী",
        "সৌরভ",
        "project",
        "interview",
        "date",
        "student"
    ]

    important_lines = []

    for line in lines:
        if any(keyword in line.lower() for keyword in keywords):
            important_lines.append(line)

    if not important_lines:
        important_lines = lines[:10]

    summary_text = "\n".join(important_lines[:10])

    return Response(
        content=summary_text,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=makk-summary.txt"
        }
    )


@app.get("/clear-history")
def clear_history(request: Request):
    user = get_current_user(request)

    if not user:
        return RedirectResponse(url="/", status_code=303)

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM questions
        WHERE user_id = ?
    """, (user["id"],))

    connection.commit()
    connection.close()

    return RedirectResponse(url="/workspace", status_code=303)


@app.get("/logout")
def logout(request: Request):
    token = request.cookies.get("makk_session")

    if token:
        connection = get_db()
        cursor = connection.cursor()

        cursor.execute("""
            DELETE FROM sessions
            WHERE token = ?
        """, (token,))

        connection.commit()
        connection.close()

    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("makk_session")

    return response
