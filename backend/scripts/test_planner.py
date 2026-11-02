
from app.agents.planner import make_plan, PlanError


REQUESTS = [
    "Build a simple calculator with addition, subtraction, multiplication, and division.",
    "Build a todo list where users can add, complete, and delete tasks.",
    "Build a Pomodoro timer with work sessions, breaks, and start and reset controls.",
    "Build me a Python web server using FastAPI.",
]


def main():
    for request in REQUESTS:
        print("\n" + "=" * 60)
        print("REQUEST:", request)

        try:
            plan = make_plan(request)
            print(plan.model_dump_json(indent=2))
        except PlanError as exc:
            print("PLANNING FAILED:", exc)


if __name__ == "__main__":
    main()
