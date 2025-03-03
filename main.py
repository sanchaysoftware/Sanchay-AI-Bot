from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import openai
import google.generativeai as genai
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from urllib.parse import quote_plus
import json
import random

# ✅ Initialize FastAPI app
app = FastAPI()

# ✅ API Keys (Replace with your own)
API_KEYS = {
    "openai": "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",  # OpenAI API Key
    "google_gemini": "AIzaSyBDyG2ljy31U7s3QWUTo07um0caai23UvA",  # Google Gemini API Key
    "hugging_face": "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"
}

# ✅ Configure AI Clients
genai.configure(api_key=API_KEYS["google_gemini"])
client = openai.OpenAI(api_key=API_KEYS["openai"])

# ✅ Database Configuration
DATABASES = {
    "test_client": {
        "server": "192.168.1.119",
        "database": "P63",
        "username": "ST068",
        "password": "ST068@123"
    },
}

# ✅ Function to get database connection
def get_database_connection(client_name):
    if client_name not in DATABASES:
        raise ValueError("Invalid client database")

    db_config = DATABASES[client_name]
    driver = "ODBC Driver 18 for SQL Server"

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={db_config['server']},1433;"
        f"DATABASE={db_config['database']};"
        f"UID={db_config['username']};"
        f"PWD={db_config['password']};"
        f"Encrypt=no;TrustServerCertificate=yes"
    )

    return create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")

# ✅ Function to fetch data from the database
def fetch_data_from_db(client_name, user_input):
    try:
        engine = get_database_connection(client_name)
        query = "SELECT * FROM dbo.chatbot_history"
        df = pd.read_sql(query, engine)

        if df.empty:
            return []

        # ✅ Filter database responses that match user input
        filtered_responses = df[df["user_query"].str.contains(user_input, case=False, na=False)]

        if not filtered_responses.empty:
            df = filtered_responses  # ✅ Prioritize relevant responses

        df = df.sample(frac=1).reset_index(drop=True)  # ✅ Shuffle before selecting
        random_responses = df.sample(n=min(3, len(df))).to_dict(orient="records")  # ✅ Allow multiple responses
        return random_responses
    except SQLAlchemyError as e:
        return {"error": f"Database Error: {str(e)}"}
    
# ✅ Function to get OpenAI response
def get_openai_response(user_input):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": user_input}],
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI Error: {str(e)}"

# ✅ Function to get Google Gemini AI response
def get_google_gemini_response(user_input):
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(user_input)  # ✅ Only send user_input, NOT full JSON
        return response.text if hasattr(response, 'text') else "No response from Gemini."
    except Exception as e:
        return f"Google Gemini Error: {str(e)}"

# ✅ Function to get Hugging Face response
def get_huggingface_response(user_input):
    try:
        model = "facebook/blenderbot-400M-distill"
        api_url = f"https://api-inference.huggingface.co/models/{model}"

        headers = {
            "Authorization": f"Bearer {API_KEYS['hugging_face']}",
            "Content-Type": "application/json"
        }
        payload = {"inputs": user_input}

        response = requests.post(api_url, headers=headers, json=payload)

        if response.status_code == 200 and response.json():
            return response.json()[0].get("generated_text", "No response from Hugging Face.")
        else:
            return f"Hugging Face API Error: {response.status_code} - {response.text}"
    except Exception as e:
        return "Hugging Face is currently unavailable. Please try again later."

# ✅ Chat Request Model
class ChatRequest(BaseModel):
    client_id: str
    security_key: str
    user_input: str 

# ✅ Chat API Endpoint
@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        db_data = fetch_data_from_db(request.client_id, request.user_input)

        openai_response = get_openai_response(request.user_input)
        google_gemini_response = get_google_gemini_response(request.user_input)
        huggingface_response = get_huggingface_response(request.user_input)

        return {
            "random_database_response": db_data,  # ✅ Ensure database response is included
            "google_gemini_response": google_gemini_response,
            "huggingface_response": huggingface_response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Serve Chatbot UI (HTML Page)
@app.get("/", response_class=HTMLResponse)
async def serve_html():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Chatbot UI</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; background-color: #f4f4f4; }
            #chat-container { width: 50%; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0px 0px 10px 0px gray; height: 500px; overflow-y: auto; }
            #chat-box { display: flex; flex-direction: column; }
            .user-message, .bot-message { padding: 10px; margin: 5px; border-radius: 10px; max-width: 80%; word-wrap: break-word; }
            .user-message { background-color:rgb(255, 0, 0); color: white; align-self: flex-end; }
            .bot-message { background-color:rgb(255, 115, 0); align-self: flex-start; }
            input, button { width: 50%; padding: 10px; margin-top: 10px; border: none; border-radius: 5px; }
            button { background-color:rgb(248, 163, 5); color: white; cursor: pointer; }
            button:hover { background-color:rgb(218, 15, 15); }
        </style>
    </head>
    <body>
        <h2>Chatbot</h2>
        <div id="chat-container">
            <div id="chat-box"></div>
        </div>
        <input type="text" id="user-input" placeholder="Type a message..." />
        <button onclick="sendMessage()">Send</button>
        <script>
            async function sendMessage() {
                const userInput = document.getElementById("user-input").value;
                if (!userInput.trim()) return;

                const chatBox = document.getElementById("chat-box");

                // ✅ Display User Message
                let userMessage = document.createElement("div");
                userMessage.classList.add("user-message");
                userMessage.innerText = userInput;
                chatBox.appendChild(userMessage);

                document.getElementById("user-input").value = "";

                try {
                    console.log("Sending request to /chat...");
                    const response = await fetch("/chat", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            client_id: "test_client",
                            security_key: "YOUR_SECRET_KEY",
                            user_input: userInput
                        })
                    });

                    console.log("Waiting for response...");
                    const data = await response.json();
                    console.log("API Response:", data);  // ✅ Debugging API response

                    let botMessage = document.createElement("div");
                    botMessage.classList.add("bot-message");

                    let aiResponse = "";

                    // ✅ Ensure Database Response is Displayed
                    if (Array.isArray(data.random_database_response) && data.random_database_response.length > 0) {
                        aiResponse += "**Database Response:**\\n";
                        data.random_database_response.forEach(entry => {
                            aiResponse += `🗣 ${entry.user_query} → 🤖 ${entry.response}\\n`;
                        });
                    }

                    // ✅ Show AI Responses
                    if (data.google_gemini_response && !data.google_gemini_response.includes("Error")) {
                        aiResponse += `\\nGoogle Gemini: ${data.google_gemini_response}`;
                    }
                    if (data.huggingface_response && !data.huggingface_response.includes("Error")) {
                        aiResponse += `\\nHugging Face: ${data.huggingface_response}`;
                    }

                    botMessage.innerText = aiResponse || "No AI response received.";
                    chatBox.appendChild(botMessage);
                    chatBox.scrollTop = chatBox.scrollHeight; // ✅ Auto-scroll chat box
                } catch (error) {
                    console.error("Error:", error);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
