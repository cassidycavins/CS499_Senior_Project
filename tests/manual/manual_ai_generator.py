
from app.study_tools.ai_generator import generate_ai_quiz

notes = """
Big Data refers to extremely large datasets.

The five Vs of Big Data are Volume, Velocity,
Variety, Veracity, and Value.

Volume describes the amount of data.

Velocity describes how quickly data is
generated and processed.

Variety describes different forms of data,
including structured and unstructured data.
"""
print("Starting AI generator test...")
try:
    print("Sending request to OpenAI...")
    result = generate_ai_quiz(
        text=notes,
        title="Big Data Test Notes",
        count=3,
    )
    print("OpenAI response received!")

    for question in result["questions"]:
        print("\nQUESTION:", question["question"])

        for index, choice in enumerate(question["choices"]):
            print(f"{index + 1}. {choice}")

        print(
            "CORRECT ANSWER:",
            question["correct_index"] + 1
        )

        print(
            "SOURCE:",
            question["citation"]["excerpt"]
        )

except Exception as error:
    print(f"AI generation failed: {error}")