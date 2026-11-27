
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pypdf import PdfReader
import io

app = FastAPI()

DEMO_EMAIL = "demo@makk.ai"
DEMO_PASSWORD = "demo1234"

documents = {}
question_count = {}

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
        <p>AI Document Assistant</p>

        <form action="/login" method="post">
          <p>Email</p>
          <input name="email" type="email" required style="width:100%; padding:12px; margin-bottom:12px;">
          <p>Password</p>
          <input name="password" type="password" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Login</button>
        </form>
                <p style="margin-top:20px;"><a href="/pricing" style="color:#4f8cff;">View pricing</a></p>

        <p style="margin-top:20px;">Demo account:</p>
        <p>demo@makk.ai</p>
        <p>demo1234</p>
      </body>
    </html>
    """

@app.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    if email == DEMO_EMAIL and password == DEMO_PASSWORD:
        response = RedirectResponse(url="/dashboard", status_code=303)
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

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return f"""
    <html>
      <head>
        <title>MAKK Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>MAKK Dashboard</h1>
        <p>Welcome, {user}</p>

        <h2>Upload document</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
          <input name="file" type="file" accept=".pdf,.txt" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Upload</button>
        </form>

        <h2>Ask MAKK</h2>
        <form action="/ask" method="post">
          <input name="question" type="text" placeholder="Ask a question" required style="width:100%; padding:12px; margin-bottom:12px;">
          <button type="submit" style="width:100%; padding:12px; background:#4f8cff; color:white; border:none; border-radius:8px;">Ask MAKK</button>
        </form>
      </body>
    </html>
    """

@app.post("/upload", response_class=HTMLResponse)
def upload(request: Request, file: UploadFile = File(...)):
    user = request.cookies.get("makk_user")
    if not user:
        return RedirectResponse(url="/", status_code=303)

    filename = file.filename
    content = file.file.read()

    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = content.decode("utf-8", errors="ignore")

    documents[user] = text

    return f"""
    <html>
      <head>
        <title>MAKK Upload</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background:#0b1220; color:white; padding:20px;">
        <h1>Document uploaded</h1>
        <p><b>File:</b> {filename}</p>
        <p><b>Words found:</b> {len(text.split())}</p>
        <p>MAKK can now answer questions from this document.</p>
        <a href="/dashboard" style="color:#4f8cff;">Back to dashboard</a>
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
            <p>Upgrade to Pro for more questions.</p>
            <a href="/pricing" style="color:#4f8cff;">View pricing</a>
          </body>
        </html>
        """)

    question_count[user] = count + 1

    text = documents.get(user, "")

    if not text:
        answer = "Please upload a document first."
    else:
        words = question.lower().split()
        matches = [line for line in text.split("\n") if any(word in line.lower() for word in words)]
        if matches:
            answer = "<br>".join(matches[:5])
        else:
            answer = "I could not find a matching line in your document."

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
        <a href="/dashboard" style="color:#4f8cff;">Back to dashboard</a>
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
        <p>1 document</p>
        <p>10 questions per day</p>

        <h2>Pro</h2>
        <p>$19 / month</p>
        <p>20 documents</p>
        <p>200 questions per day</p>

        <h2>Business</h2>
        <p>$99 / month</p>
        <p>Unlimited documents</p>
        <p>Unlimited questions</p>

        <a href="/dashboard" style="color:#4f8cff;">Back to dashboard</a>
      </body>
    </html>
    """
    
