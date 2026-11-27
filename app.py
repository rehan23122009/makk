from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

DEMO_EMAIL = "demo@makk.ai"
DEMO_PASSWORD = "demo1234"

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
      <head>
        <title>MAKK Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; background: #0b1220; color: white; padding: 20px;">
        <h1>MAKK</h1>
        <p>AI Document Assistant</p>

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
        <p>Next: document upload and AI answers.</p>
      </body>
    </html>
    """
