
# pbl-ragflow
## Overview

This repository contains a project that mixes frontend and backend code. Based on the repository language composition, the project includes JavaScript, Python, CSS, and HTML. The intent of this README is to provide a minimal starting point that you can expand with project-specific details.

## Features (example)
- Web frontend (HTML/CSS/JavaScript)
- Python backend or services
- Integration points for Retrieval-Augmented Generation (RAG) or similar flows (if applicable)
## Quickstart (example)

These are generic instructions — replace paths/commands with the actual project structure.

1. Clone the repo
   ```bash
   git clone https://github.com/Vitalieww/pbl-ragflow.git
   cd pbl-ragflow
   ```
2. Install the requirements using the tool from /tool , also have ragflow and ollama...
3. Set .env variables 
4. Open the app in your browser at the configured port 

## Configuration

- This project uses a .env file to store environment variables.
- Do NOT commit actual .env files with secrets or API keys. Add `.env` to .gitignore if not already ignored.

## Features

The AI fitness assistant now **automatically extracts and saves workout statistics** from your conversations. When you tell the AI about your workouts, it intelligently parses the information and stores it in both MySQL database and JSON files for easy frontend access.

---

## How It Works

### 1. **Automatic Detection**
The AI automatically recognizes workout mentions in natural language:

**Examples:**
```
✅ "I benched 80kg for 5 reps, 3 sets"
✅ "Did 100kg squats today, 5x5"
✅ "Ran 5km in 30 minutes"
✅ "Deadlifted 120kg"
✅ "bench press: 80kg x 5 reps x 3 sets"
✅ "30 minute run"
```

### 2. **Data Storage**
Workout data is saved in two places:

#### **MySQL Database** (`workout_stats` table)
```sql
CREATE TABLE workout_stats (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100),
    session_id VARCHAR(100),
    exercise_name VARCHAR(200),
    exercise_type VARCHAR(50),      -- strength, cardio, other
    weight DECIMAL(10, 2),
    weight_unit VARCHAR(10),         -- kg, lbs
    reps INT,
    sets INT,
    duration INT,
    duration_unit VARCHAR(20),       -- minutes, hours
    distance DECIMAL(10, 2),
    distance_unit VARCHAR(10),       -- km, miles
    calories INT,
    notes TEXT,
    workout_date DATE,
    create_time BIGINT,
    create_date DATETIME
);
```

#### **JSON Export** (`workout_stats/default_user_workout_stats.json`)
```json
{
  "user_id": "default_user",
  "total_workouts": 15,
  "last_updated": "2025-10-25 14:30:00",
  "workouts": [
    {
      "id": "abc123...",
      "exercise_name": "bench press",
      "exercise_type": "strength",
      "weight": 80.0,
      "weight_unit": "kg",
      "reps": 5,
      "sets": 3,
      "workout_date": "2025-10-25",
      "create_date": "2025-10-25 14:30:00"
    }
  ]
}
```

---

## API Endpoints for Frontend

### 1. **Get All Workout Stats**
```http
GET /workout-stats?user_id=default_user&days=30&type=strength
```

**Query Parameters:**
- `user_id` (optional): User identifier (default: "default_user")
- `days` (optional): Number of days to retrieve (default: 30)
- `type` (optional): Filter by exercise type (strength, cardio, other)

**Response:**
```json
{
  "total": 15,
  "workouts": [
    {
      "id": "abc123",
      "exercise_name": "bench press",
      "exercise_type": "strength",
      "weight": 80.0,
      "weight_unit": "kg",
      "reps": 5,
      "sets": 3,
      "workout_date": "2025-10-25"
    }
  ]
}
```

---

### 2. **Get Workout Summary**
```http
GET /workout-stats/summary?user_id=default_user&days=30
```

**Response:**
```json
{
  "summary_by_type": [
    {
      "exercise_type": "strength",
      "workout_count": 12,
      "days_worked_out": 8,
      "total_sets": 36,
      "total_reps": 180,
      "avg_weight": 75.5,
      "max_weight": 100.0
    },
    {
      "exercise_type": "cardio",
      "workout_count": 5,
      "days_worked_out": 5,
      "total_duration": 150,
      "total_distance": 25.0
    }
  ],
  "personal_records": [
    {
      "exercise_name": "deadlift",
      "max_weight": 140.0,
      "weight_unit": "kg"
    },
    {
      "exercise_name": "bench press",
      "max_weight": 100.0,
      "weight_unit": "kg"
    }
  ],
  "period_days": 30
}
```

---

### 3. **Get Exercise History**
```http
GET /workout-stats/exercise/bench%20press?user_id=default_user
```

**Response:**
```json
{
  "exercise": "bench press",
  "total_sessions": 8,
  "history": [
    {
      "weight": 80.0,
      "weight_unit": "kg",
      "reps": 5,
      "sets": 3,
      "workout_date": "2025-10-25"
    },
    {
      "weight": 75.0,
      "weight_unit": "kg",
      "reps": 5,
      "sets": 3,
      "workout_date": "2025-10-18"
    }
  ]
}
```

---

### 4. **Export All Stats to JSON**
```http
GET /workout-stats/export?user_id=default_user
```

Returns the complete JSON file with all workout data.

---

### 5. **Manually Add Workout** (Optional)
```http
POST /workout-stats
Content-Type: application/json

{
  "user_id": "default_user",
  "exercise_name": "squat",
  "exercise_type": "strength",
  "weight": 100,
  "weight_unit": "kg",
  "reps": 5,
  "sets": 3,
  "workout_date": "2025-10-25"
}
```

---

## Exercise Type Classification

The system automatically classifies exercises into three types:

### **Strength** 
bench, squat, deadlift, press, curl, row, pull, push, lift

### **Cardio**
run, jog, cycle, swim, rowing, bike, treadmill, elliptical

### **Other**
Anything not matching above patterns

---

## Usage Examples

### **For Users (Natural Language)**

Just chat naturally with the AI:

```
User: "I just benched 80kg for 5 reps, did 3 sets"
AI: "Great work on the bench press! 80kg for 5 reps is solid..."
[System automatically saves: bench press, 80kg, 5 reps, 3 sets]

User: "Ran 5km today in 30 minutes"
AI: "Nice run! That's a 6:00/km pace..."
[System automatically saves: running, 5km, 30 minutes]
```

### **For Frontend Developers**

#### **Display Recent Workouts:**
```javascript
// Fetch last 7 days of workouts
fetch('/workout-stats?days=7')
  .then(res => res.json())
  .then(data => {
    console.log(`Total workouts: ${data.total}`);
    data.workouts.forEach(w => {
      console.log(`${w.exercise_name}: ${w.weight}${w.weight_unit}`);
    });
  });
```

#### **Show Progress Chart:**
```javascript
// Get bench press history
fetch('/workout-stats/exercise/bench%20press')
  .then(res => res.json())
  .then(data => {
    const dates = data.history.map(w => w.workout_date);
    const weights = data.history.map(w => w.weight);
    // Plot with Chart.js, D3, etc.
  });
```

#### **Display Summary Dashboard:**
```javascript
// Get 30-day summary
fetch('/workout-stats/summary?days=30')
  .then(res => res.json())
  .then(data => {
    console.log('Personal Records:');
    data.personal_records.forEach(pr => {
      console.log(`${pr.exercise_name}: ${pr.max_weight}${pr.weight_unit}`);
    });
  });
```

---

## File Locations

- **MySQL Database**: `rag_flow` database, `workout_stats` table
- **JSON Export**: `workout_stats/default_user_workout_stats.json`
- **Python Code**: Main Flask app with workout tracking functions

---

## Supported Patterns

The system recognizes these workout mention patterns:

1. `"I benched 80kg for 5 reps, 3 sets"`
2. `"bench press: 80kg x 5 reps x 3 sets"`
3. `"squatted 100kg 5x3"` (shorthand notation)
4. `"ran 5km in 30 minutes"`
5. `"5km run"` or `"30 minute run"`
6. `"deadlift 120kg
## Tests
## Contributing

Contributions are welcome. A suggested minimal workflow:
1. Fork the repository
2. Create a feature branch: git checkout -b feat/my-feature
3. Commit your changes and push: git push origin feat/my-feature
4. Open a pull request describing the changes

Please include tests and update this README with any new setup steps.

## License
## Contact
For questions, open an issue or contact the repository owner.
