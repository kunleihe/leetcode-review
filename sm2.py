from datetime import date, timedelta

QUALITY = {"Again": 1, "Hard": 2, "Good": 4, "Easy": 5}


def calculate(rating, interval, ease_factor, repetitions, today):
    quality = QUALITY[rating]

    if quality >= 3:
        new_interval = max(1, round(interval * ease_factor))
        new_repetitions = repetitions + 1
    else:
        new_interval = 1
        new_repetitions = 0

    new_ease = ease_factor + 0.1 - (5 - quality) * 0.08
    new_ease = round(max(1.3, new_ease), 4)

    due = date.fromisoformat(today) + timedelta(days=new_interval)

    return {
        "interval": new_interval,
        "ease_factor": new_ease,
        "repetitions": new_repetitions,
        "due_date": due.isoformat(),
    }
