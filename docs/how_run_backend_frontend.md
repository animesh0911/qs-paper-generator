# Run The App With Docker

Use Docker for the demo stack. The browser opens the frontend on the host, but the
frontend container proxies API calls to the backend container, and the backend
uses the Postgres container.

```text
browser -> http://localhost:5173 -> frontend -> web:8000 -> db:5432
```

## Start

Stop any host Vite server first if it owns port 5173:

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
kill <PID>
```

Start the stack:

```bash
docker compose up -d --build db web frontend
```

Check it:

```bash
docker compose ps
```

Expected services:

```text
db        Up healthy
web       Up
frontend  Up, 0.0.0.0:5173->5173
```

Open:

```text
http://localhost:5173
```

Demo login:

```text
teacher@example.com
teacher123
```

## Load Questions And Answers

The backend auto-runs migrations and seed questions on startup. To load the full
committed bank and generated answers into the Docker DB, run:

```bash
docker compose exec web python manage.py load_questions /content/parsed
docker compose exec web python manage.py load_question_overrides /content/bank-overrides/question_overrides.json
```

`load_questions` is idempotent; duplicates are skipped. `load_question_overrides`
applies committed AI-generated answers and disables diagram-required questions.

Verify the loaded bank:

```bash
docker compose exec web python manage.py shell -c '
from bank.models import Question
print("eligible", Question.objects.filter(parse_quality__in=["clean","partial"]).count())
print("answered eligible", Question.objects.filter(parse_quality__in=["clean","partial"]).exclude(answer="").count())
print("disabled diagrams", Question.objects.filter(review_flags__contains=["disabled_diagram_required"]).count())
'
```

Current expected result:

```text
eligible 344
answered eligible 344
disabled diagrams 34
```

## Useful Commands

Backend checks:

```bash
docker compose exec web python manage.py check
docker compose exec web pytest
```

Frontend checks:

```bash
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npm run type-check
```

Stop the stack:

```bash
docker compose down
```

Remove stopped containers:

```bash
docker container prune -f
```
