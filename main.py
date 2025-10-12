from flask import Flask, render_template, Response, request, jsonify, session
from openai import OpenAI
from ragflow_sdk import RAGFlow
import json
import threading
import requests
import mysql.connector
from mysql.connector import Error
import uuid
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import os


app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure RAGFlow + Ollama
MODEL = os.getenv("MODEL")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")
BASE_URL = "http://localhost:9380"

MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 5455,
    'database': 'rag_flow',
    'user': 'root',
    'password': 'infini_rag_flow'
}

client = OpenAI(api_key=API_KEY, base_url=f"{BASE_URL}/api/v1/chats_openai/{CHAT_ID}")
rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
assistant = rag.list_chats(id=CHAT_ID)[0]


def get_mysql_connection():
    """Create and return a MySQL connection"""
    try:
        connection = mysql.connector.connect(**MYSQL_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def save_to_mysql(session_id: str, question: str, answer: str):
    """Save Q&A into MySQL conversation table"""
    try:
        connection = get_mysql_connection()
        if not connection:
            print("❌ No MySQL connection, skipping save")
            return

        cursor = connection.cursor()

        # Fetch existing conversation
        cursor.execute("SELECT message FROM conversation WHERE dialog_id = %s", (session_id,))
        row = cursor.fetchone()
        messages = []
        if row and row[0]:
            try:
                messages = json.loads(row[0])
            except Exception as je:
                print(f"JSON parse error in MySQL messages: {je}")

        # Append new messages
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})

        now_ms = int(time.time() * 1000)
        now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if row:
            # Update existing
            cursor.execute(
                """
                UPDATE conversation
                SET message=%s, update_time=%s, update_date=%s
                WHERE dialog_id=%s
                """,
                (json.dumps(messages), now_ms, now_dt, session_id)
            )
        else:
            # Insert new row
            cursor.execute(
                """
                INSERT INTO conversation 
                (id, create_time, create_date, update_time, update_date, dialog_id, name, message, reference, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid.uuid4().hex,   # id
                    now_ms, now_dt,     # create_time, create_date
                    now_ms, now_dt,     # update_time, update_date
                    session_id,         # dialog_id
                    question[:255],     # name (truncate to 255)
                    json.dumps(messages), # message
                    "[]",               # reference (empty list for now)
                    "default_user"      # user_id (replace with real user later)
                )
            )

        connection.commit()
        cursor.close()
        connection.close()
        print(f"💾 Saved conversation to MySQL for session {session_id}")

    except Exception as e:
        print(f"MySQL save error: {e}")

def get_or_create_default_session():
    """Get the most recent session or create a new one"""
    try:
        sessions = assistant.list_sessions(page=1, page_size=1)
        if sessions and len(sessions) > 0:
            return sessions[0].id
        else:
            new_session = assistant.create_session(name="Chat Session")
            return new_session.id
    except Exception as e:
        print(f"Error in get_or_create_default_session: {e}")
        return None


def save_conversation_to_ragflow(session_id: str, question: str, answer: str):
    """Save the complete Q&A to RAGFlow using REST API"""
    try:
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        url = f"{BASE_URL}/api/v1/chats/{CHAT_ID}/completions"
        payload = {
            "question": question,
            "session_id": session_id,
            "stream": False
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"✓ Conversation saved to session {session_id}")
        else:
            print(f"✗ Error saving to RAGFlow: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error saving to RAGFlow: {e}")


def generate_response(question: str, session_id: str,
                      system_prompt: str = "You are a helpful fitness and health assistant."):
    """Generator that yields assistant text chunks"""
    full_response = ""
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            stream=True,
            extra_body={
                "reference": True,
                "session_id": session_id
            }
        )
        for chunk in completion:
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                content = delta.content
                full_response += content
                yield f"data: {json.dumps({'content': content})}\n\n"

        if full_response:
            # Save to MySQL
            thread = threading.Thread(
                target=save_to_mysql,
                args=(session_id, question, full_response)
            )
            thread.daemon = True
            thread.start()

            # (Optional) Save to RAGFlow too
            thread2 = threading.Thread(
                target=save_conversation_to_ragflow,
                args=(session_id, question, full_response)
            )
            thread2.daemon = True
            thread2.start()

        yield f"data: {json.dumps({'done': True})}\n\n"
    except Exception as e:
        print(f"Error in generate_response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.route("/")
def index():
    # Ensure there's always an active session
    if "active_session_id" not in session:
        default_session = get_or_create_default_session()
        if default_session:
            session["active_session_id"] = default_session
            print(f"Initialized session with ID: {default_session}")
    return render_template("index.html")


@app.route("/ask", methods=["GET"])
def ask():
    """Handle chat questions"""
    question = request.args.get("question")
    session_id = request.args.get("session_id") or session.get("active_session_id")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    # Auto-create session if none exists
    if not session_id:
        session_id = get_or_create_default_session()
        if not session_id:
            return jsonify({"error": "Could not create session"}), 500
        session["active_session_id"] = session_id

    session["active_session_id"] = session_id
    return Response(generate_response(question, session_id), mimetype="text/event-stream")


@app.route("/sessions", methods=["GET"])
def list_sessions():
    """List all chat sessions"""
    try:
        sessions = assistant.list_sessions(page=1, page_size=50)
        session_list = []
        for s in sessions:
            msg_count = 0
            if hasattr(s, 'messages') and s.messages:
                msg_count = len(s.messages)
            session_list.append({
                "id": s.id,
                "name": s.name,
                "message_count": msg_count,
                "created_at": getattr(s, 'created_at', None)
            })
        return jsonify(session_list)
    except Exception as e:
        print(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/sessions", methods=["POST"])
def create_session():
    """Create a new chat session with proper naming"""
    try:
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict()

        session_name = data.get("name", f"Workout Session {datetime.now().strftime('%Y-%m-%d')}")

        # Ensure the name is not empty
        if not session_name.strip():
            session_name = f"Workout Session {datetime.now().strftime('%Y-%m-%d')}"

        new_session = assistant.create_session(name=session_name)
        session["active_session_id"] = new_session.id

        return jsonify({
            "id": new_session.id,
            "name": new_session.name,  # This should be the name we set
            "message_count": 0,
            "created_at": getattr(new_session, 'created_at', None)
        })
    except Exception as e:
        print(f"Error creating session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/sessions/<session_id>/activate", methods=["POST"])
def activate_session(session_id):
    """Set the active session"""
    session["active_session_id"] = session_id
    print(f"Activated session: {session_id}")
    return jsonify({"active_session": session_id})


@app.route("/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    """Get all messages from a session"""
    try:
        connection = get_mysql_connection()

        if not connection:
            return get_session_messages_sdk(session_id)

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT message, name, create_date 
            FROM conversation 
            WHERE dialog_id = %s 
            ORDER BY create_date ASC
            LIMIT 1
        """

        cursor.execute(query, (session_id,))
        row = cursor.fetchone()

        messages = []
        session_name = "Unnamed Session"

        if row:
            session_name = row.get('name', 'Unnamed Session')
            message_json = row.get('message', '[]')

            if isinstance(message_json, str):
                try:
                    messages_array = json.loads(message_json)
                    if isinstance(messages_array, list):
                        for msg in messages_array:
                            if isinstance(msg, dict):
                                content = msg.get('content')
                                role = msg.get('role', 'assistant')
                                if content:
                                    messages.append({"role": role, "content": content})
                except json.JSONDecodeError as je:
                    print(f"Error parsing message JSON: {je}")
            elif isinstance(message_json, list):
                for msg in message_json:
                    if isinstance(msg, dict):
                        content = msg.get('content')
                        role = msg.get('role', 'assistant')
                        if content:
                            messages.append({"role": role, "content": content})

        cursor.close()
        connection.close()

        print(f"Retrieved {len(messages)} messages from MySQL for session {session_id}")

        return jsonify({
            "messages": messages,
            "session_id": session_id,
            "session_name": session_name
        })

    except Exception as e:
        print(f"Error getting messages from MySQL for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
        return get_session_messages_sdk(session_id)


def get_session_messages_sdk(session_id):
    """Fallback method using SDK"""
    try:
        sessions = assistant.list_sessions(id=session_id)

        if not sessions or len(sessions) == 0:
            print(f"Session {session_id} not found")
            return jsonify({"error": "Session not found", "messages": []}), 404

        session_obj = sessions[0]
        messages = []

        if hasattr(session_obj, 'messages') and session_obj.messages is not None:
            try:
                for m in session_obj.messages:
                    role = getattr(m, 'role', None)
                    content = getattr(m, 'content', None) or getattr(m, 'text', None)
                    if content and role:
                        messages.append({"role": role, "content": content})
            except TypeError as te:
                print(f"TypeError iterating messages: {te}")

        print(f"Retrieved {len(messages)} messages via SDK from session {session_id}")

        session_name = getattr(session_obj, 'name', 'Unnamed Session')

        return jsonify({
            "messages": messages,
            "session_id": session_id,
            "session_name": session_name
        })

    except Exception as e:
        print(f"Error getting messages via SDK for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "messages": [],
            "session_id": session_id,
            "session_name": "Error"
        }), 500


@app.route("/sessions/<session_id>/rename", methods=["POST"])
def rename_session(session_id):
    """Rename a session"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        new_name = data.get("name")
        if not new_name:
            return jsonify({"error": "Missing name"}), 400

        print(f"Attempting to rename session {session_id} to '{new_name}'")

        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        update_url = f"{BASE_URL}/api/v1/chats/{CHAT_ID}/sessions/{session_id}"
        response = requests.put(update_url, headers=headers, json={"name": new_name})

        if response.status_code == 200:
            print(f"Successfully renamed using API")
            return jsonify({"id": session_id, "name": new_name})
        else:
            print(f"API rename failed: {response.status_code} - {response.text}")
            return jsonify({"error": "Failed to rename session"}), 500

    except Exception as e:
        print(f"Error renaming session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a session"""
    try:
        assistant.delete_session(session_id=session_id)
        if session.get("active_session_id") == session_id:
            # Set to another session or create new one
            new_session_id = get_or_create_default_session()
            session["active_session_id"] = new_session_id
        print(f"Deleted session {session_id}")
        return jsonify({"success": True, "new_active_session": session.get("active_session_id")})
    except Exception as e:
        print(f"Error deleting session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/current-session", methods=["GET"])
def get_current_session():
    """Get current active session with messages"""
    active_session_id = session.get("active_session_id")

    # Auto-create session if none exists
    if not active_session_id:
        active_session_id = get_or_create_default_session()
        if active_session_id:
            session["active_session_id"] = active_session_id
            print(f"Auto-created new session: {active_session_id}")
        else:
            return jsonify({"active_session": None, "error": "Could not create session"})

    try:
        connection = get_mysql_connection()
        messages = []
        session_name = "Unnamed Session"

        if connection:
            try:
                cursor = connection.cursor(dictionary=True)

                query = """
                    SELECT message, name, create_date 
                    FROM conversation 
                    WHERE dialog_id = %s 
                    ORDER BY create_date ASC
                    LIMIT 1
                """

                cursor.execute(query, (active_session_id,))
                row = cursor.fetchone()

                if row:
                    session_name = row.get('name', 'Unnamed Session')
                    message_json = row.get('message', '[]')

                    if isinstance(message_json, str):
                        try:
                            messages_array = json.loads(message_json)
                            if isinstance(messages_array, list):
                                for msg in messages_array:
                                    if isinstance(msg, dict):
                                        content = msg.get('content')
                                        role = msg.get('role', 'assistant')
                                        if content:
                                            messages.append({"role": role, "content": content})
                        except:
                            pass
                    elif isinstance(message_json, list):
                        for msg in message_json:
                            if isinstance(msg, dict):
                                content = msg.get('content')
                                role = msg.get('role', 'assistant')
                                if content:
                                    messages.append({"role": role, "content": content})

                cursor.close()
                connection.close()
            except Exception as db_error:
                print(f"MySQL error in get_current_session: {db_error}")

        # Fallback to SDK if no messages found
        if not messages:
            try:
                sessions = assistant.list_sessions(id=active_session_id)
                if sessions:
                    session_name = getattr(sessions[0], 'name', 'Unnamed Session')
            except Exception as sdk_error:
                print(f"SDK error getting session name: {sdk_error}")

        print(f"Current session {active_session_id} has {len(messages)} messages")

        return jsonify({
            "active_session": active_session_id,
            "session_name": session_name,
            "messages": messages
        })
    except Exception as e:
        print(f"Error getting current session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"active_session": active_session_id, "error": str(e), "messages": []})


@app.route("/debug/table-structure", methods=["GET"])
def debug_table_structure():
    """Debug endpoint to inspect database structure"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return jsonify({"error": "Could not connect to MySQL"}), 500

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SHOW TABLES")
        tables = [list(row.values())[0] for row in cursor.fetchall()]

        result = {"tables": {}}

        for table in tables:
            cursor.execute(f"DESCRIBE {table}")
            result["tables"][table] = cursor.fetchall()

            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
            sample = cursor.fetchone()
            if sample:
                result["tables"][table + "_sample"] = {
                    k: str(v)[:100] for k, v in sample.items()
                }

        cursor.close()
        connection.close()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Add these helper functions for settings
def get_coaching_style_prompt(style):
    """Get the coaching style modifier for the system prompt"""
    styles = {
        "motivational": "Be motivational and encouraging. Use positive reinforcement and inspiring language. Celebrate small victories and keep the user motivated.",
        "professional": "Be professional and technical. Use precise fitness terminology and scientific explanations. Focus on proper form and evidence-based recommendations.",
        "casual": "Be casual and friendly. Use conversational language and be approachable. Keep it light and relatable.",
        "strict": "Be strict and disciplined. Use direct language and hold the user accountable. Emphasize consistency and hard work."
    }
    return styles.get(style, styles["motivational"])


def get_detail_level_modifier(level):
    """Get the detail level modifier for responses"""
    levels = {
        "brief": "Provide concise answers. Get straight to the point without unnecessary details. Keep responses under 100 words when possible.",
        "moderate": "Provide balanced answers with key details. Include important explanations but avoid excessive length. Aim for 100-200 words for complex topics.",
        "detailed": "Provide comprehensive, in-depth answers. Include detailed explanations, examples, and considerations. Don't worry about response length - prioritize completeness."
    }
    return levels.get(level, levels["moderate"])


def apply_units_to_response(response, units):
    """Convert units in the response based on user preference"""
    if units == "imperial":
        # This would need actual conversion logic, but for now we'll just note it
        return response + "\n\n*Note: Displaying measurements in imperial units*"
    return response


def create_enhanced_system_prompt(profile_data, coaching_style="motivational", detail_level="moderate"):
    """Create a personalized system prompt with settings"""
    base_prompt = """You are a helpful fitness and health assistant. """

    # Add coaching style
    coaching_prompt = get_coaching_style_prompt(coaching_style)
    base_prompt += coaching_prompt + " "

    # Add detail level
    detail_prompt = get_detail_level_modifier(detail_level)
    base_prompt += detail_prompt + " "

    base_prompt += "Always provide personalized recommendations based on the user's specific profile information below:\n\nUSER PROFILE:\n"

    if not profile_data:
        return base_prompt + "No profile information available. Provide general fitness advice."

    profile_sections = []

    # Add basic info
    if profile_data.get('age') or profile_data.get('gender'):
        basic_info = []
        if profile_data.get('age'):
            basic_info.append(f"Age: {profile_data['age']} years")
        if profile_data.get('gender'):
            basic_info.append(f"Gender: {profile_data['gender']}")
        if basic_info:
            profile_sections.append(" • " + ", ".join(basic_info))

    # Add physical stats
    if profile_data.get('height') or profile_data.get('weight'):
        stats = []
        if profile_data.get('height'):
            stats.append(f"Height: {profile_data['height']} cm")
        if profile_data.get('weight'):
            stats.append(f"Weight: {profile_data['weight']} kg")
        if stats:
            profile_sections.append(" • " + ", ".join(stats))

    # Add fitness goal
    if profile_data.get('goal'):
        goal_map = {
            'lose-weight': 'Weight loss',
            'build-muscle': 'Muscle building',
            'improve-endurance': 'Improving endurance',
            'increase-flexibility': 'Increasing flexibility',
            'general-fitness': 'General fitness improvement',
            'sports-performance': 'Sports performance enhancement'
        }
        goal_text = goal_map.get(profile_data['goal'], profile_data['goal'])
        profile_sections.append(f" • Fitness Goal: {goal_text}")

    # Add activity level
    if profile_data.get('activity'):
        activity_map = {
            'sedentary': 'Sedentary (little or no exercise)',
            'light': 'Light activity (1-3 days/week)',
            'moderate': 'Moderate activity (3-5 days/week)',
            'active': 'Active (6-7 days/week)',
            'very-active': 'Very active (2x per day)'
        }
        activity_text = activity_map.get(profile_data['activity'], profile_data['activity'])
        profile_sections.append(f" • Activity Level: {activity_text}")

    # Add dietary preferences
    if profile_data.get('diet') and profile_data['diet'] != 'none':
        diet_map = {
            'vegetarian': 'Vegetarian',
            'vegan': 'Vegan',
            'keto': 'Ketogenic',
            'paleo': 'Paleo',
            'gluten-free': 'Gluten-free'
        }
        diet_text = diet_map.get(profile_data['diet'], profile_data['diet'])
        profile_sections.append(f" • Dietary Preference: {diet_text}")

    # Add medical considerations
    if profile_data.get('medical') and profile_data['medical'].strip():
        profile_sections.append(f" • Medical Considerations: {profile_data['medical']}")

    if profile_sections:
        profile_text = "\n".join(profile_sections)
        full_prompt = base_prompt + profile_text + """

INSTRUCTIONS:
1. Always consider the user's specific profile when giving advice
2. Provide personalized workout plans based on their goals and physical stats
3. Suggest appropriate nutrition plans considering their dietary preferences
4. Adjust exercise intensity based on their activity level
5. Be mindful of any medical considerations
6. Calculate calorie needs based on their age, weight, height, and activity level
7. Provide age-appropriate fitness recommendations

Use {knowledge} from the knowledge base to enhance your responses when relevant."""
    else:
        full_prompt = base_prompt + "No profile information available. Ask the user to complete their profile for personalized advice."

    return full_prompt


# Update the update_assistant_with_profile function to include settings
def update_assistant_with_profile(profile_data, settings=None):
    """Update the RAGFlow assistant with personalized system prompt and settings"""
    try:
        if settings is None:
            settings = {}

        coaching_style = settings.get('coaching_style', 'motivational')
        detail_level = settings.get('detail_level', 'moderate')

        personalized_prompt = create_enhanced_system_prompt(
            profile_data,
            coaching_style,
            detail_level
        )

        # Update the assistant with the new prompt
        update_data = {
            "prompt": {
                "prompt": personalized_prompt
            }
        }

        # Update the assistant
        assistant.update(update_data)
        print(f"✅ Updated RAGFlow assistant with personalized prompt and settings")
        print(f"📝 Coaching Style: {coaching_style}")
        print(f"📝 Detail Level: {detail_level}")
        return True

    except Exception as e:
        print(f"❌ Error updating RAGFlow assistant: {e}")
        return False




@app.route("/settings", methods=["GET"])
def get_settings():
    """Get user settings"""
    try:
        settings = session.get('user_settings', {})
        return jsonify(settings)
    except Exception as e:
        print(f"Error getting settings: {e}")
        return jsonify({"error": str(e)}), 500


# Update the save_settings function to handle profile data properly
@app.route("/settings", methods=["POST"])
def save_settings():
    """Save user settings and update RAGFlow assistant"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        # Extract settings and profile data
        settings_data = {
            'coaching_style': data.get('coaching_style', 'motivational'),
            'detail_level': data.get('detail_level', 'moderate'),
            'units': data.get('units', 'metric'),
            'dark_mode': data.get('dark_mode', False),
            'auto_speak': data.get('auto_speak', False),
            'reminders': data.get('reminders', False),
            'show_calories': data.get('show_calories', True)
        }

        # Save settings to session
        session['user_settings'] = settings_data

        # Get profile data from the request or session
        profile_data = {}
        if 'profile_data' in data:
            profile_data = data['profile_data']
        elif 'user_profile' in session:
            profile_data = session['user_profile']

        # Update the RAGFlow assistant with both profile and settings
        success = update_assistant_with_profile(profile_data, settings_data)

        if success:
            return jsonify({
                "success": True,
                "message": "Settings saved! AI assistant updated with your preferences."
            })
        else:
            return jsonify({"error": "Failed to update AI assistant with settings"}), 500

    except Exception as e:
        print(f"Error saving settings: {e}")
        return jsonify({"error": str(e)}), 500


# Update the profile route to store profile in session
@app.route("/profile", methods=["POST"])
def save_profile():
    """Save user profile and update RAGFlow assistant system prompt with settings"""
    try:
        if request.is_json:
            profile_data = request.get_json()
        else:
            profile_data = request.form.to_dict()

        # Store profile in session
        session['user_profile'] = profile_data

        # Get current settings
        settings = session.get('user_settings', {})

        # Update the RAGFlow assistant with both profile and settings
        success = update_assistant_with_profile(profile_data, settings)

        if success:
            return jsonify({
                "success": True,
                "message": "Profile saved! AI assistant now knows your personal data and will provide personalized recommendations."
            })
        else:
            return jsonify({"error": "Failed to update AI assistant with profile data"}), 500

    except Exception as e:
        print(f"Error saving profile: {e}")
        return jsonify({"error": str(e)}), 500


# Add a route to get both profile and settings
@app.route("/user-data", methods=["GET"])
def get_user_data():
    """Get both user profile and settings"""
    try:
        profile_data = session.get('user_profile', {})
        settings_data = session.get('user_settings', {})

        return jsonify({
            "profile": profile_data,
            "settings": settings_data
        })
    except Exception as e:
        print(f"Error getting user data: {e}")
        return jsonify({"error": str(e)}), 500

# Optional: Debug endpoint to see current system prompt
@app.route("/debug/system-prompt", methods=["GET"])
def debug_system_prompt():
    """Debug endpoint to see the current system prompt"""
    try:
        # This would require storing the current profile somewhere,
        # but for simplicity we can just return a message
        return jsonify({
            "message": "System prompt updated via RAGFlow assistant.update()",
            "note": "Check RAGFlow admin interface to see current system prompt"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, threaded=True)