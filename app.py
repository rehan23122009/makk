from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
      <head>
        <title>MAKK</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
      </head>
      <body style="font-family: Arial; padding: 20px; background: #0b1220; color: white;">
        <h1>MAKK</h1>
        <p>AI Document Assistant</p>
        <p>MAKK is starting. Next we will add login and document upload.</p>
      </body>
    </html>
    """
