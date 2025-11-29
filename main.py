from flask import Flask, render_template, Response, request, jsonify, session
from openai import OpenAI
from ragflow_sdk import RAGFlow
from dotenv import load_dotenv
import json
import os
import threading
import requests
import mysql.connector
from mysql.connector import Error
import uuid
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
app = Flask(__name__)
app.secret_key = os.urandom(24)

load_dotenv()
# Configure RAGFlow + Ollama
MODEL = os.getenv("MODEL")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")

MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 5455,
    'database': 'rag_flow',
    'user': 'root',
    'password': 'infini_rag_flow'
}

# Create directory for workout stats JSON files
STATS_DIR = "workout_stats"
os.makedirs(STATS_DIR, exist_ok=True)

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


def create_workout_stats_table():
    """Create the workout_stats table if it doesn't exist"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return False

        cursor = connection.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS workout_stats (
            id VARCHAR(36) PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            session_id VARCHAR(100) NOT NULL,
            exercise_name VARCHAR(200) NOT NULL,
            exercise_type VARCHAR(50),
            weight DECIMAL(10, 2),
            weight_unit VARCHAR(10),
            reps INT,
            sets INT,
            duration INT,
            duration_unit VARCHAR(20),
            distance DECIMAL(10, 2),
            distance_unit VARCHAR(10),
            calories INT,
            notes TEXT,
            workout_date DATE NOT NULL,
            create_time BIGINT,
            create_date DATETIME,
            INDEX idx_user_date (user_id, workout_date),
            INDEX idx_session (session_id),
            INDEX idx_exercise (exercise_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        cursor.execute(create_table_query)
        connection.commit()
        cursor.close()
        connection.close()
        print("✅ Workout stats table created/verified")
        return True

    except Exception as e:
        print(f"Error creating workout_stats table: {e}")
        return False


class AIWorkoutDetector:
    """AI-powered workout detection using Ollama"""

    def __init__(self, ollama_base_url: str = "http://localhost:11434", model: str = None):
        self.ollama_base_url = ollama_base_url
        # Use the same model as your main app, or specify a different one
        self.model = model or os.getenv("MODEL", "llama2")

    def detect_workouts(self, message: str, conversation_history: List[Dict] = None) -> List[Dict]:
        """
        Use AI to detect workout information from natural language.
        """

        # Build context from recent conversation
        context = ""
        if conversation_history:
            recent_messages = conversation_history[-3:]  # Last 3 messages
            context = "Recent conversation:\n"
            for msg in recent_messages:
                role = msg.get('role', 'user')
                content = msg.get('content', '')[:150]
                context += f"{role}: {content}\n"
            context += "\n"

        # Use OpenAI-style chat completion for better structured output
        system_prompt = """
        Extract workouts from the user message. 
        Return ONLY a JSON array. 
        If no workout is found, return [].

        FOR EACH workout, extract ONLY these fields:

        - exercise_name
        - exercise_type ("strength" or "cardio")
        - weight (number or null)
        - weight_unit ("kg" or "lbs" or null)
        - reps (number or null)
        - sets (number or null)
        - duration (minutes or null)
        - duration_unit ("minutes" or "hours" or null)
        - distance (number or null)
        - distance_unit ("km" or "miles" or null)
        - calories (number or null)
        - notes (string or null)

        RULES:
        - Do NOT infer distance or duration. Only include if clearly stated.
        - Do NOT guess calories.
        - Do NOT include fields not mentioned.
        - Return a JSON ARRAY, even for one workout.
        - No extra text.

        Example:
        "I benched 80kg for 5 reps, 3 sets"
        → [{"exercise_name":"bench press","exercise_type":"strength","weight":80,"weight_unit":"kg","reps":5,"sets":3}]
        """

        user_prompt = f"{context}Extract workouts from this message:\n\n{message}"

        try:
            # Try using Ollama's chat endpoint first (more reliable)
            response = requests.post(
                f"{self.ollama_base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1000
                    }
                },
                timeout=60
            )

            if response.status_code != 200:
                print(f"⚠️ Ollama chat API error: {response.status_code} - {response.text}")
                # Fallback to generate endpoint
                return self._detect_with_generate(system_prompt, user_prompt)

            result = response.json()
            ai_response = result.get('message', {}).get('content', '[]').strip()

            print(f"🤖 Raw AI response: {ai_response[:300]}")


            # Clean up the response
            ai_response = self._clean_json_response(ai_response)

            workouts = json.loads(ai_response)

            if not isinstance(workouts, list):
                print(f"⚠️ AI response is not a list: {type(workouts)}")
                return []

            # Validate and clean
            validated_workouts = self._validate_workouts(workouts)

            if validated_workouts:
                print(
                    f"💪 AI detected {len(validated_workouts)} workout(s): {[w['exercise_name'] for w in validated_workouts]}")
            else:
                print(f"ℹ️ No workouts detected in message: {message[:50]}")

            return validated_workouts

        except requests.exceptions.Timeout:
            print("⚠️ Ollama timeout - skipping workout detection")
            return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Ollama request error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {e}")
            if 'ai_response' in locals():
                print(f"Response was: {ai_response[:300]}")
            return []
        except Exception as e:
            print(f"⚠️ Unexpected error in workout detection: {e}")
            import traceback
            traceback.print_exc()
            return []



def save_workout_stats(session_id, user_id, workouts, workout_date=None):
    """Save workout statistics to MySQL and JSON file"""
    if not workouts:
        return

    if workout_date is None:
        workout_date = datetime.now().date()
    elif isinstance(workout_date, str):
        workout_date = datetime.strptime(workout_date, '%Y-%m-%d').date()

    try:
        connection = get_mysql_connection()
        if not connection:
            print("❌ No MySQL connection for workout stats")
            return

        cursor = connection.cursor()
        now_ms = int(time.time() * 1000)
        now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for workout in workouts:
            workout_id = uuid.uuid4().hex

            insert_query = """
            INSERT INTO workout_stats 
            (id, user_id, session_id, exercise_name, exercise_type, 
             weight, weight_unit, reps, sets, duration, duration_unit,
             distance, distance_unit, calories, notes, workout_date, 
             create_time, create_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                workout_id,
                user_id,
                session_id,
                workout['exercise_name'],
                workout['exercise_type'],
                workout['weight'],
                workout['weight_unit'],
                workout['reps'],
                workout['sets'],
                workout['duration'],
                workout['duration_unit'],
                workout['distance'],
                workout['distance_unit'],
                workout['calories'],
                workout['notes'],
                workout_date,
                now_ms,
                now_dt
            )

            cursor.execute(insert_query, values)

        connection.commit()
        cursor.close()
        connection.close()

        print(f"💪 Saved {len(workouts)} workout stats to MySQL")

        # Also save to JSON file for easy frontend access
        export_workout_stats_to_json(user_id)

    except Exception as e:
        print(f"Error saving workout stats: {e}")


def export_workout_stats_to_json(user_id="default_user"):
    """Export all workout stats for a user to a JSON file"""
    try:
        connection = get_mysql_connection()
        if not connection:
            return None

        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT * FROM workout_stats 
        WHERE user_id = %s 
        ORDER BY workout_date DESC, create_time DESC
        """

        cursor.execute(query, (user_id,))
        workouts = cursor.fetchall()

        # Convert decimal and date objects to JSON-serializable formats
        for workout in workouts:
            if workout.get('weight'):
                workout['weight'] = float(workout['weight'])
            if workout.get('distance'):
                workout['distance'] = float(workout['distance'])
            if workout.get('workout_date'):
                workout['workout_date'] = workout['workout_date'].strftime('%Y-%m-%d')
            if workout.get('create_date'):
                workout['create_date'] = workout['create_date'].strftime('%Y-%m-%d %H:%M:%S')

        cursor.close()
        connection.close()

        # Save to JSON file
        json_file_path = os.path.join(STATS_DIR, f"{user_id}_workout_stats.json")
        with open(json_file_path, 'w') as f:
            json.dump({
                'user_id': user_id,
                'total_workouts': len(workouts),
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'workouts': workouts
            }, f, indent=2)

        print(f"📊 Exported {len(workouts)} workouts to {json_file_path}")
        return json_file_path

    except Exception as e:
        print(f"Error exporting workout stats: {e}")
        return None


def save_to_mysql(session_id: str, question: str, answer: str):
    """Save Q&A into MySQL conversation table and extract workout stats"""
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
                    uuid.uuid4().hex,
                    now_ms, now_dt,
                    now_ms, now_dt,
                    session_id,
                    question[:255],
                    json.dumps(messages),
                    "[]",
                    "default_user"
                )
            )

        connection.commit()
        cursor.close()
        connection.close()
        print(f"💾 Saved conversation to MySQL for session {session_id}")

        # Extract and save workout data from the user's question
        workouts = extract_workout_data(question)
        if workouts:
            print(f"🏋️ Found {len(workouts)} workout(s) in message")
            save_workout_stats(session_id, "default_user", workouts)

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
            # Save to MySQL (which also extracts workout stats)
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
    # Create workout stats table on startup
    create_workout_stats_table()

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


# NEW ENDPOINTS FOR WORKOUT STATS

@app.route("/workout-stats", methods=["GET"])
def get_workout_stats():
    """Get workout statistics for a user"""
    user_id = request.args.get("user_id", "default_user")
    days = request.args.get("days", 30, type=int)
    exercise_type = request.args.get("type")  # strength, cardio, other

    try:
        connection = get_mysql_connection()
        if not connection:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)

        # Build query based on filters
        query = """
        SELECT * FROM workout_stats 
        WHERE user_id = %s 
        AND workout_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        """
        params = [user_id, days]

        if exercise_type:
            query += " AND exercise_type = %s"
            params.append(exercise_type)

        query += " ORDER BY workout_date DESC, create_time DESC"

        cursor.execute(query, params)
        workouts = cursor.fetchall()

        # Convert to JSON-serializable format
        for workout in workouts:
            if workout.get('weight'):
                workout['weight'] = float(workout['weight'])
            if workout.get('distance'):
                workout['distance'] = float(workout['distance'])
            if workout.get('workout_date'):
                workout['workout_date'] = workout['workout_date'].strftime('%Y-%m-%d')
            if workout.get('create_date'):
                workout['create_date'] = workout['create_date'].strftime('%Y-%m-%d %H:%M:%S')

        cursor.close()
        connection.close()

        return jsonify({
            "total": len(workouts),
            "workouts": workouts
        })

    except Exception as e:
        print(f"Error getting workout stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/workout-stats/summary", methods=["GET"])
def get_workout_summary():
    """Get summary statistics for workouts"""
    user_id = request.args.get("user_id", "default_user")
    days = request.args.get("days", 30, type=int)

    try:
        connection = get_mysql_connection()
        if not connection:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)

        # Get summary by exercise type
        query = """
        SELECT 
            exercise_type,
            COUNT(*) as workout_count,
            COUNT(DISTINCT workout_date) as days_worked_out,
            SUM(CASE WHEN sets IS NOT NULL THEN sets ELSE 1 END) as total_sets,
            SUM(reps) as total_reps,
            AVG(weight) as avg_weight,
            MAX(weight) as max_weight,
            SUM(duration) as total_duration,
            SUM(distance) as total_distance
        FROM workout_stats
        WHERE user_id = %s 
        AND workout_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY exercise_type
        """

        cursor.execute(query, (user_id, days))
        summary_by_type = cursor.fetchall()

        # Convert decimals to float
        for row in summary_by_type:
            if row.get('avg_weight'):
                row['avg_weight'] = float(row['avg_weight'])
            if row.get('max_weight'):
                row['max_weight'] = float(row['max_weight'])
            if row.get('total_distance'):
                row['total_distance'] = float(row['total_distance'])

        # Get personal records
        pr_query = """
        SELECT exercise_name, MAX(weight) as max_weight, weight_unit
        FROM workout_stats
        WHERE user_id = %s AND weight IS NOT NULL
        GROUP BY exercise_name, weight_unit
        ORDER BY max_weight DESC
        LIMIT 10
        """

        cursor.execute(pr_query, (user_id,))
        personal_records = cursor.fetchall()

        for pr in personal_records:
            if pr.get('max_weight'):
                pr['max_weight'] = float(pr['max_weight'])

        cursor.close()
        connection.close()

        return jsonify({
            "summary_by_type": summary_by_type,
            "personal_records": personal_records,
            "period_days": days
        })

    except Exception as e:
        print(f"Error getting workout summary: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/workout-stats/exercise/<exercise_name>", methods=["GET"])
def get_exercise_history(exercise_name):
    """Get history for a specific exercise"""
    user_id = request.args.get("user_id", "default_user")

    try:
        connection = get_mysql_connection()
        if not connection:
            return jsonify({"error": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT * FROM workout_stats
        WHERE user_id = %s AND exercise_name = %s
        ORDER BY workout_date DESC, create_time DESC
        """

        cursor.execute(query, (user_id, exercise_name))
        history = cursor.fetchall()

        # Convert to JSON-serializable format
        for workout in history:
            if workout.get('weight'):
                workout['weight'] = float(workout['weight'])
            if workout.get('distance'):
                workout['distance'] = float(workout['distance'])
            if workout.get('workout_date'):
                workout['workout_date'] = workout['workout_date'].strftime('%Y-%m-%d')
            if workout.get('create_date'):
                workout['create_date'] = workout['create_date'].strftime('%Y-%m-%d %H:%M:%S')

        cursor.close()
        connection.close()

        return jsonify({
            "exercise": exercise_name,
            "total_sessions": len(history),
            "history": history
        })

    except Exception as e:
        print(f"Error getting exercise history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/workout-stats/export", methods=["GET"])
def export_stats():
    """Export workout stats to JSON file"""
    user_id = request.args.get("user_id", "default_user")

    try:
        json_file_path = export_workout_stats_to_json(user_id)

        if json_file_path and os.path.exists(json_file_path):
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({"error": "Failed to export stats"}), 500

    except Exception as e:
        print(f"Error exporting stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/workout-stats", methods=["POST"])
def manual_add_workout():
    """Manually add a workout (for testing or manual entry)"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        user_id = data.get("user_id", "default_user")
        session_id = session.get("active_session_id", "manual_entry")

        workout = {
            'exercise_name': data.get('exercise_name'),
            'exercise_type': data.get('exercise_type', 'other'),
            'weight': float(data['weight']) if data.get('weight') else None,
            'weight_unit': data.get('weight_unit'),
            'reps': int(data['reps']) if data.get('reps') else None,
            'sets': int(data['sets']) if data.get('sets') else None,
            'duration': int(data['duration']) if data.get('duration') else None,
            'duration_unit': data.get('duration_unit'),
            'distance': float(data['distance']) if data.get('distance') else None,
            'distance_unit': data.get('distance_unit'),
            'calories': int(data['calories']) if data.get('calories') else None,
            'notes': data.get('notes')
        }

        workout_date = data.get('workout_date')
        if not workout_date:
            workout_date = datetime.now().date()

        save_workout_stats(session_id, user_id, [workout], workout_date)

        return jsonify({
            "success": True,
            "message": "Workout added successfully"
        })

    except Exception as e:
        print(f"Error manually adding workout: {e}")
        return jsonify({"error": str(e)}), 500


# Keep all your existing routes below...
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

        if not session_name.strip():
            session_name = f"Workout Session {datetime.now().strftime('%Y-%m-%d')}"

        new_session = assistant.create_session(name=session_name)
        session["active_session_id"] = new_session.id

        return jsonify({
            "id": new_session.id,
            "name": new_session.name,
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


def create_enhanced_system_prompt(profile_data, coaching_style="motivational", detail_level="moderate"):
    """Create a personalized system prompt with settings"""
    base_prompt = """You are a helpful fitness and health assistant. """

    coaching_prompt = get_coaching_style_prompt(coaching_style)
    base_prompt += coaching_prompt + " "

    detail_prompt = get_detail_level_modifier(detail_level)
    base_prompt += detail_prompt + " "

    base_prompt += """
IMPORTANT: When users mention their workouts, acknowledge them and extract the workout data. 
Examples of workout mentions you should recognize:
- "I benched 80kg for 5 reps, 3 sets"
- "Did 100kg squats today, 5x5"
- "Ran 5km in 30 minutes"
- "Deadlifted 120kg"

Always provide personalized recommendations based on the user's specific profile information below:

USER PROFILE:
"""

    if not profile_data:
        return base_prompt + "No profile information available. Provide general fitness advice."

    profile_sections = []

    if profile_data.get('age') or profile_data.get('gender'):
        basic_info = []
        if profile_data.get('age'):
            basic_info.append(f"Age: {profile_data['age']} years")
        if profile_data.get('gender'):
            basic_info.append(f"Gender: {profile_data['gender']}")
        if basic_info:
            profile_sections.append(" • " + ", ".join(basic_info))

    if profile_data.get('height') or profile_data.get('weight'):
        stats = []
        if profile_data.get('height'):
            stats.append(f"Height: {profile_data['height']} cm")
        if profile_data.get('weight'):
            stats.append(f"Weight: {profile_data['weight']} kg")
        if stats:
            profile_sections.append(" • " + ", ".join(stats))

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

        update_data = {
            "prompt": {
                "prompt": personalized_prompt
            }
        }

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


@app.route("/settings", methods=["POST"])
def save_settings():
    """Save user settings and update RAGFlow assistant"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        settings_data = {
            'coaching_style': data.get('coaching_style', 'motivational'),
            'detail_level': data.get('detail_level', 'moderate'),
            'units': data.get('units', 'metric'),
            'dark_mode': data.get('dark_mode', False),
            'auto_speak': data.get('auto_speak', False),
            'reminders': data.get('reminders', False),
            'show_calories': data.get('show_calories', True)
        }

        session['user_settings'] = settings_data

        profile_data = {}
        if 'profile_data' in data:
            profile_data = data['profile_data']
        elif 'user_profile' in session:
            profile_data = session['user_profile']

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


@app.route("/profile", methods=["POST"])
def save_profile():
    """Save user profile and update RAGFlow assistant system prompt with settings"""
    try:
        if request.is_json:
            profile_data = request.get_json()
        else:
            profile_data = request.form.to_dict()

        session['user_profile'] = profile_data

        settings = session.get('user_settings', {})

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


@app.route("/debug/system-prompt", methods=["GET"])
def debug_system_prompt():
    """Debug endpoint to see the current system prompt"""
    try:
        return jsonify({
            "message": "System prompt updated via RAGFlow assistant.update()",
            "note": "Check RAGFlow admin interface to see current system prompt"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Create workout stats table on startup
    create_workout_stats_table()
    app.run(debug=True, threaded=True)