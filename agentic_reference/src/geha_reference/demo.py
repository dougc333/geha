from __future__ import annotations

from .bootstrap import build_agent
from .models import UserContext


def main() -> None:
    agent = build_agent()
    context = UserContext(
        actor_id="synthetic-member-1000",
        role="member",
        subject_member_ids=frozenset({"Gy001000"}),
    )

    for question in (
        "What is the status of CLM-100000?",
        "How do I submit an out-of-network claim?",
        "What do I need to appeal CLM-100000?",
    ):
        response = agent.run(question, context)
        print(f"\nQ: {question}\nA: {response.answer}")
        print("Human review:", response.needs_human_review)
        for citation in response.citations:
            print(f"- {citation.title}: {citation.url}")


if __name__ == "__main__":
    main()

