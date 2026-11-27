from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pypdf import PdfReader
import io

app = FastAPI()

users = {"demo@makk.ai": "demo1234"}
question_count = {}
workspaces = {}
question_history = {}

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
      </body>
    </html>
    """

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    if users.get(email) == password:
        response = RedirectResponse(url="/workspace", status_code=303)
        response.set_cookie(key="makk_user", value=email)
        return response
    return HTMLResponse("""
    <html>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h2>Login failed</h2>
        <p>Wrong email or password.</p>
        <a href="/" style="color:#4f8cff;">Try again</a>
      </body>
    </html>
    """)

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
          <input name="password" type="password" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Create account</button>
        </form>

        <a href="/" style="color:#4f8cff;">Back to login</a>
      </body>
    </html>
    """

@app.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):
    if email in users:
        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h2>Account already exists</h2>
            <a href="/signup" style="color:#4f8cff;">Try another email</a>
          </body>
        </html>
        """)

    users[email] = password
    workspaces[email] = []

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
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if user not in workspaces:
        workspaces[user] = []

    docs = workspaces[user]
    doc_list = ""

    for i, doc in enumerate(docs):
        doc_list += f"""
        <p>{i + 1}. <a href="/document/{i}" style="color:#4f8cff;">{doc['name']}</a> — {len(doc['text'].split())} words
        <a href="/delete/{i}" style="color:#ff6b6b;">Delete</a>
        </p>
        """

    return f"""
    <html>
      <head>
        <title>MAKK Workspace</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>MAKK Enterprise Workspace</h1>
        <p>Welcome, {user}</p>

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

        <p style="margin-top:20px;"><a href="/pricing" style="color:#4f8cff;">View pricing</a></p>
      </body>
    </html>
    """

@app.post("/upload", response_class=HTMLResponse)
def upload(request: Request, files: list[UploadFile] = File(...)):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if user not in workspaces:
        workspaces[user] = []

    added = 0

    for file in files:
        filename = file.filename
        content = file.file.read()

        if filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            text = content.decode("utf-8", errors="ignore")

        workspaces[user].append({
            "name": filename,
            "text": text
        })

        added += 1

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
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    count = question_count.get(user, 0)

    if count >= 10:
        return HTMLResponse("""
        <html>
          <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
            <h1>Daily limit reached</h1>
            <p>You have used 10 questions today.</p>
            <p>Upgrade for more questions.</p>
            <a href="/pricing" style="color:#4f8cff;">View pricing</a>
          </body>
        </html>
        """)

    question_count[user] = count + 1

    docs = workspaces.get(user, [])

    if not docs:
        answer = "Please upload documents first."
        sources = ""
    else:
        words = question.lower().split()
        matches = []

        for doc in docs:
            for line in doc["text"].split("\n"):
                if any(word in line.lower() for word in words):
                    matches.append({
                        "file": doc["name"],
                        "line": line
                    })

        if matches:
            answer = "<br><br>".join(
                f"<b>{m['file']}</b><br>{m['line']}" for m in matches[:5]
            )
            sources = "<br>".join(sorted(set(m["file"] for m in matches[:5])))
        else:
            answer = "I could not find a matching answer in your documents."
            sources = ""
        history = question_history.setdefault(user, [])
        history.append(question)

    if len(history) > 10:
        history.pop(0)

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
@app.get("/delete/{doc_id}")
def delete_document(request: Request, doc_id: int):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    if user in workspaces and 0 <= doc_id < len(workspaces[user]):
        workspaces[user].pop(doc_id)

    return RedirectResponse(url="/workspace", status_code=303)
@app.get("/document/{doc_id}", response_class=HTMLResponse)
def document_preview(request: Request, doc_id: int):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    docs = workspaces.get(user, [])

    if doc_id < 0 or doc_id >= len(docs):
        return RedirectResponse(url="/workspace", status_code=303)

    doc = docs[doc_id]
    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]
    preview = "<br>".join(lines[:15])
    answer_html = ""
        

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
        <form method="post" action="/document/{doc_id}/ask">
            <input type="text" name="question" placeholder="Ask about this document" required
                   style="width:100%; padding:10px; margin:8px 0;">
            <button type="submit"
                    style="padding:10px 18px; background:#4f8cff; color:white; border:none; border-radius:8px;">
                Ask
            </button>
        </form>

        {answer_html}
        <a href="/document/{doc_id}/summary"
           style="display:inline-block; padding:10px 18px; background:#22c55e; color:white; border-radius:8px; text-decoration:none;">
            Summarize
        </a>
        <a href="/workspace" style="color:#4f8cff;">Back to workspace</a>
      </body>
    </html>
    """
@app.post("/document/{doc_id}/ask", response_class=HTMLResponse)
def ask_document(request: Request, doc_id: int, question: str = Form(...)):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    docs = workspaces.get(user, [])

    if doc_id < 0 or doc_id >= len(docs):
        return RedirectResponse(url="/workspace", status_code=303)

    doc = docs[doc_id]
    text = doc["text"]
    lines = text.split("\n")

    words = question.lower().split()
    matches = []

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(word in line_lower for word in words if len(word) > 2):
            matches.append(line.strip())

    if matches:
        answer = "<br>".join(matches[:10])
    else:
        answer = "No matching information found in this document."

    lines = [line.strip() for line in text.split("\n") if line.strip()]
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
        <p><b>Words:</b> {len(text.split())}</p>

        <h2>First 15 lines</h2>
        <p>{preview}</p>

        <h2>Ask about this document</h2>
        <form method="post" action="/document/{doc_id}/ask">
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
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    docs = workspaces.get(user, [])

    if doc_id < 0 or doc_id >= len(docs):
        return RedirectResponse(url="/workspace", status_code=303)

    doc = docs[doc_id]
    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]

    important_lines = []
    keywords = ["প্রকল্প", "সাক্ষাৎকার", "প্রতিবেদক", "তারিখ", "শিক্ষার্থী", "সৌরভ"]

    for line in lines:
        if any(keyword in line for keyword in keywords):
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
        <a href="/document/{doc_id}/summary/download"
           style="display:inline-block; padding:10px 18px; background:#4f8cff; color:white; border-radius:8px; text-decoration:none; margin-bottom:15px;">
            Download summary
        </a>
        <a href="/document/{doc_id}" style="color:#4f8cff;">Back to document</a>
      </body>
    </html>
    """
@app.get("/document/{doc_id}/summary/download")
def download_summary(request: Request, doc_id: int):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    docs = workspaces.get(user, [])

    if doc_id < 0 or doc_id >= len(docs):
        return RedirectResponse(url="/workspace", status_code=303)

    doc = docs[doc_id]
    lines = [line.strip() for line in doc["text"].split("\n") if line.strip()]

    important_lines = []
    keywords = ["প্রকল্প", "সাক্ষাৎকার", "প্রতিবেদক", "তারিখ", "শিক্ষার্থী", "সৌরভ"]

    for line in lines:
        if any(keyword in line for keyword in keywords):
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
