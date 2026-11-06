
import os
import uuid
import logging

from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from google import genai
from google.genai import types, errors

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise ValueError("FLASK_SECRET_KEY is missing from .env")

logging.basicConfig(level=logging.INFO)

# ==========================================
# BUSINESS INFORMATION
# ==========================================

BUSINESS_NAME = "Your Mining Company"
BUSINESS_EMAIL = "support@yourcompany.com"
BUSINESS_PHONE = "+234 000 000 0000"

# ==========================================
# GEMINI API CONFIGURATION
# ==========================================

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY is missing from your .env file")

# Primary model and fallback models.
# You can override this list in your .env file.

DEFAULT_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
]

MODEL_NAMES = [
    model.strip()
    for model in os.getenv(
        "GEMINI_MODELS",
        ",".join(DEFAULT_MODELS)
    ).split(",")
    if model.strip()
]

# HTTP/API errors that should trigger fallback.
RETRYABLE_STATUS_CODES = {
    404, 429, 500, 502, 503, 504
}

# ==========================================
# CONVERSATION STORAGE
# ==========================================

# Development storage only.
# Use Redis or a database in production.

CHAT_HISTORY = {}

MAX_HISTORY_MESSAGES = 12

# ==========================================
# GEMINI SYSTEM INSTRUCTIONS
# ==========================================

SYSTEM_INSTRUCTION = f"""
You are the official AI customer support assistant
for {BUSINESS_NAME}.

BUSINESS DETAILS:
Business name: {BUSINESS_NAME}
Email: {BUSINESS_EMAIL}
Phone: {BUSINESS_PHONE}

ABOUT THE BUSINESS:
The business deals with cryptocurrency and natural
resources, including columbite, tantalite, tin,
lithium and other earth metals.

YOUR RESPONSIBILITIES:

1. Assist customers professionally and politely.
2. Answer questions about minerals and their applications.
3. Help customers interested in buying or selling minerals.
4. Explain mineral sourcing, supply and export processes.
5. Assist with general cryptocurrency questions.
6. Help customers with payment and transaction enquiries.
7. Collect relevant details when customers request quotations.
8. Direct customers to human support when necessary.

MINERAL ENQUIRIES:

When customers want to buy minerals, ask for:
- Mineral type
- Required quantity
- Required grade
- Destination

When customers want to sell minerals, ask for:
- Mineral type
- Available quantity
- Location
- Grade or assay report

CRYPTOCURRENCY:

Provide general cryptocurrency assistance.

Never request private keys, passwords, seed phrases
or wallet recovery phrases.

IMPORTANT RULES:

- Be conversational, helpful and professional.
- Give clear answers without unnecessary technical language.
- Do not invent mineral stock availability.
- Do not invent prices, quotations or transaction confirmations.
- Do not claim a payment has been received unless verified.
- Explain that prices depend on mineral grade, quantity
  and market conditions.
- If you do not know an answer, say so honestly.
- Do not pretend to be a human employee.
- Keep responses reasonably concise.
- Use the business contact details when customers
  need human assistance.

FORMATTING RULES:

- Always respond in clean, plain text.
- Never use Markdown formatting.
- Do not use ** for bold text.
- Do not use * for italic text.
- Do not use Markdown headings or code blocks.
- Use simple paragraphs and numbered lists when necessary.
- Responses should look natural in a customer service
  chat interface.

Always represent the business professionally.
"""

# ==========================================
# ASYNCHRONOUS GEMINI MODEL ROUTER
# ==========================================

async def generate_gemini_response(async_client, conversation):

    last_error = None

    for model_name in MODEL_NAMES:

        try:

            app.logger.info(
                f"Attempting Gemini model: {model_name}"
            )

            response = await async_client.models.generate_content(

                model=model_name,

                contents=conversation,

                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.7,
                    max_output_tokens=800
                )
            )

            reply = response.text

            if reply and reply.strip():

                app.logger.info(
                    f"Successfully generated response using {model_name}"
                )

                return reply.strip()

            app.logger.warning(
                f"{model_name} returned an empty response."
            )

        except errors.APIError as error:

            last_error = error

            status_code = getattr(error, "code", None)

            app.logger.warning(
                f"Gemini model {model_name} failed. "
                f"Status: {status_code}. Error: {error}"
            )

            if status_code in RETRYABLE_STATUS_CODES:

                app.logger.info(
                    f"Switching to the next model after {model_name}"
                )

                continue

            # Authentication and other non-retryable errors
            # should not be hidden by trying every model.
            raise

        except Exception as error:

            last_error = error

            app.logger.exception(
                f"Unexpected error with Gemini model {model_name}"
            )

            # Allow the next model to be attempted after
            # a temporary network or transport failure.
            continue

    raise RuntimeError(
        "All configured Gemini models failed."
    ) from last_error


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template(
        "index.html",
        business_name=BUSINESS_NAME
    )


# ==========================================
# ASYNCHRONOUS AI CHAT ENDPOINT
# ==========================================

@app.route("/chat", methods=["POST"])
async def chat():

    data = request.get_json(silent=True) or {}

    message = data.get("message", "")

    if not isinstance(message, str):

        return jsonify({
            "error": "Invalid message."
        }), 400

    message = message.strip()

    if not message:

        return jsonify({
            "error": "Please enter a message."
        }), 400

    if len(message) > 1500:

        return jsonify({
            "error": "Message is too long."
        }), 400

    try:

        # Create a unique conversation ID
        chat_id = session.get("chat_id")

        if not chat_id:

            chat_id = str(uuid.uuid4())

            session["chat_id"] = chat_id

        # Retrieve previous conversation
        history = CHAT_HISTORY.get(chat_id, [])

        # Add the new user message
        conversation = history + [
            {
                "role": "user",
                "parts": [
                    {"text": message}
                ]
            }
        ]

        # Create an async client for this request.
        # Using a context manager ensures it is closed
        # after the request completes.

        async with genai.Client(api_key=API_KEY).aio as async_client:

            reply = await generate_gemini_response(
                async_client,
                conversation
            )

        # Save conversation history only after success
        updated_history = conversation + [
            {
                "role": "model",
                "parts": [
                    {"text": reply}
                ]
            }
        ]

        CHAT_HISTORY[chat_id] = (
            updated_history[-MAX_HISTORY_MESSAGES:]
        )

        return jsonify({
            "reply": reply
        })

    except Exception:

        app.logger.exception(
            "All Gemini model attempts failed or chat request failed."
        )

        return jsonify({
            "reply": (
                "I'm sorry, our AI assistant is temporarily "
                "unavailable. Please try again shortly or "
                "contact our support team."
            )
        }), 503


# ==========================================
# CLEAR CHAT HISTORY
# ==========================================

@app.route("/clear-chat", methods=["POST"])
def clear_chat():

    chat_id = session.get("chat_id")

    if chat_id:

        CHAT_HISTORY.pop(chat_id, None)

    session.pop("chat_id", None)

    return jsonify({
        "message": "Conversation cleared."
    })


# ==========================================
# SERVER HEALTH CHECK
# ==========================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "ai": "Gemini asynchronous routing enabled",
        "models": MODEL_NAMES
    })


# ==========================================
# START FLASK SERVER
# ==========================================

if __name__ == "__main__":

    print("Starting AI Mining Chatbot...")
    print("Gemini asynchronous routing enabled.")

    print("Available models:")

    for model in MODEL_NAMES:
        print(f" - {model}")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
