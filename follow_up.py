import os
import sys
import time
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

REPORT_FILE = "research_report.md" 
# Fallback if the user specifically wants to use the saved one
if not os.path.exists(REPORT_FILE) and os.path.exists("saved_report.md"):
    REPORT_FILE = "saved_report.md"

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # 1. Read the previous report
    if not os.path.exists(REPORT_FILE):
        print(f"Error: Could not find previous report file '{REPORT_FILE}'.")
        print("Please ensure you have run 'market_research.py' first.")
        sys.exit(1)
        
    print(f"Reading context from '{REPORT_FILE}'...")
    with open(REPORT_FILE, "r") as f:
        previous_context = f.read()

    # 2. Get the follow-up question
    if len(sys.argv) > 1:
        if os.path.isfile(sys.argv[1]):
            with open(sys.argv[1], "r") as f:
                question = f.read()
        else:
            question = " ".join(sys.argv[1:])
    else:
        print("\nEnter your follow-up question:")
        question = input("> ")

    # 3. Construct the Contextual Prompt
    # We explicitly tell the agent this is a follow-up task.
    final_prompt = (
        f"CONTEXT:\n"
        f"The following is a market research report generated previously:\n"
        f"===\n{previous_context}\n===\n\n"
        f"TASK:\n"
        f"Based on the report above (and performing additional research if necessary), "
        f"please answer this follow-up request:\n"
        f"{question}"
    )

    print(f"\nStarting follow-up research for: '{question}'\n")

    try:
        # Start the interaction
        interaction = client.interactions.create(
            agent='deep-research-pro-preview-12-2025',
            input=final_prompt,
            background=True
        )
        print(f"Follow-up task started with ID: {interaction.id}")
        
        # Poll for results
        print("Waiting for results...")
        while True:
            interaction = client.interactions.get(interaction.id)
            status = interaction.status
            
            if status == 'completed':
                print("\n--- Follow-up Completed ---\n")
                full_output = ""
                if interaction.outputs:
                    for output in interaction.outputs:
                        print(output.text)
                        full_output += output.text
                    
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    report_filename = f"followup_report_{timestamp}.md"

                    # Save the follow-up specifically
                    with open(report_filename, "w") as f:
                        f.write(full_output)
                    print(f"\n\n[INFO] Saved to '{report_filename}'")
                    
                    # Update latest alias
                    with open("followup_report.md", "w") as f:
                        f.write(full_output)
                    print(f"[INFO] Updated 'followup_report.md' (latest)")
                else:
                    print("No output received.")
                break
            elif status == 'failed':
                print(f"\nError: {interaction.error}")
                break
            
            print(".", end="", flush=True)
            time.sleep(10)

    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
