"""
Small CLI tool to generate realistic workout stats JSON for testing
Usage:
  python tools/generate_workout_stats.py --count 20 --start 2025-11-01 --end 2025-11-30 --seed 42
"""
import argparse, json, os, random, uuid
from datetime import datetime, timedelta

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workout_stats")
os.makedirs(OUT_DIR, exist_ok=True)

STRENGTH_EXERCISES = [("bench press","strength"),("squat","strength"),("deadlift","strength"),("shoulder press","strength"),("bent over row","strength"),("barbell curl","strength")]
CARDIO_EXERCISES = [("running","cardio"),("cycling","cardio"),("swimming","cardio"),("rowing","cardio"),("elliptical","cardio")]
NOTES = ["Good session, felt strong","Progressive overload working","Focus on form next time","Tough but completed all sets","Easy recovery session","Hit a new PR","Felt tired but finished"]

def random_time_on_date(date_obj):
    hour = random.randint(6,20); minute=random.randint(0,59)
    dt = datetime.combine(date_obj, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
    return int(dt.timestamp()*1000), dt.strftime("%Y-%m-%d %H:%M:%S")

def generate_strength_entry(user_id, session_id, date_obj):
    exercise, etype = random.choice(STRENGTH_EXERCISES)
    weight = round(random.uniform(40,120),1); reps = random.choice([3,5,6,8,10]); sets=random.choice([2,3,4,5]); calories=random.randint(150,400)
    create_time, create_date = random_time_on_date(date_obj)
    return {"id": uuid.uuid4().hex, "user_id": user_id, "session_id": session_id, "exercise_name": exercise, "exercise_type": etype, "weight": weight, "weight_unit": "kg", "reps": reps, "sets": sets, "duration": None, "duration_unit": None, "distance": None, "distance_unit": None, "calories": calories, "notes": random.choice(NOTES), "workout_date": date_obj.strftime("%Y-%m-%d"), "create_time": create_time, "create_date": create_date}

def generate_cardio_entry(user_id, session_id, date_obj):
    exercise, etype = random.choice(CARDIO_EXERCISES)
    if exercise == "running":
        distance = round(random.uniform(3.0,12.0),1)
        duration = int(distance / random.uniform(8.0,12.0) * 60)
    elif exercise == "cycling":
        distance = round(random.uniform(10.0,50.0),1)
        duration = int(distance / random.uniform(20.0,30.0) * 60)
    else:
        distance = round(random.uniform(0.5,25.0),2)
        duration = random.randint(15,60)
    calories = int(duration * random.uniform(6,10))
    create_time, create_date = random_time_on_date(date_obj)
    return {"id": uuid.uuid4().hex, "user_id": user_id, "session_id": session_id, "exercise_name": exercise, "exercise_type": etype, "weight": None, "weight_unit": None, "reps": None, "sets": None, "duration": duration, "duration_unit": "minutes", "distance": distance, "distance_unit": "km", "calories": calories, "notes": random.choice(NOTES), "workout_date": date_obj.strftime("%Y-%m-%d"), "create_time": create_time, "create_date": create_date}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--user-id", type=str, default="default_user")
    parser.add_argument("--out-file", type=str, default=os.path.join(OUT_DIR, "default_user_workout_stats.json"))
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.seed is not None: random.seed(args.seed)
    today = datetime.now().date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else today
    start_date = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else end_date - timedelta(days=30)
    dates = [start_date + timedelta(days=random.randint(0,(end_date-start_date).days)) for _ in range(args.count)]
    dates.sort()
    workouts=[]
    for i,d in enumerate(dates):
        if random.random() < 0.6: workouts.append(generate_strength_entry(args.user_id, f"session_{i+1}", d))
        else: workouts.append(generate_cardio_entry(args.user_id, f"session_{i+1}", d))
    payload = {"user_id": args.user_id, "total_workouts": len(workouts), "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "workouts": workouts}
    with open(args.out_file, "w", encoding="utf-8") as f: json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Generated {len(workouts)} workout entries -> {args.out_file}")

if __name__ == "__main__": main()
