from app.services.llm import ask_with_usage, LLMError


def main():
    prompt = "Explain what an AI agent is in two sentences."

    print("Sending prompt to Groq...\n")

    try:
        result = ask_with_usage(prompt)

        print("Reply:")
        print(result.reply)

        print("\nToken Usage:")
        print(f"Prompt tokens: {result.prompt_tokens}")
        print(f"Completion tokens: {result.completion_tokens}")
        print(f"Total tokens: {result.total_tokens}")

    except LLMError as exc:
        print(f"Request failed: {exc}")


if __name__ == "__main__":
    main()