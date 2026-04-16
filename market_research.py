import os
import sys
import time
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def calculate_cost(prompt_tokens, output_tokens):
    # Pricing for Gemini 3 Pro (Deep Research Agent)
    if prompt_tokens <= 200_000:
        input_rate = 1.00
        output_rate = 6.00
    else:
        input_rate = 2.00
        output_rate = 9.00
        
    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    return input_cost + output_cost

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment variables.")
        print("Please set it in a .env file or export it as an environment variable.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Get prompt from command line args or input
    if len(sys.argv) > 1:
        # Check if the argument is a filename
        if os.path.isfile(sys.argv[1]):
            with open(sys.argv[1], "r") as f:
                prompt = f.read()
        else:
            prompt = " ".join(sys.argv[1:])
    else:
        print("Enter your market research prompt:")
        prompt = input("> ")

    print(f"\nStarting research for: '{prompt}'\n")

    try:
        # Start the interaction in background mode
        interaction = client.interactions.create(
            agent='deep-research-pro-preview-12-2025',
            input=prompt,
            background=True
        )
        print(f"Research started with ID: {interaction.id}")
        
        # Poll for results
        print("Waiting for results (this may take a few minutes)...")
        while True:
            interaction = client.interactions.get(interaction.id)
            status = interaction.status
            
            if status == 'completed':
                print("\n--- Research Completed ---\n")
                
                # Display metrics
                if hasattr(interaction, 'usage') and interaction.usage:
                    usage = interaction.usage
                    p_tokens = usage.total_input_tokens or 0
                    o_tokens = usage.total_output_tokens or 0
                    r_tokens = usage.total_reasoning_tokens or 0
                    total_cost = calculate_cost(p_tokens, o_tokens + r_tokens)
                    print(f"Metrics: Input: {p_tokens:,} | Output: {o_tokens:,} | Reasoning: {r_tokens:,} | Est. Cost: ${total_cost:.4f}\n")

                full_report = ""
                if interaction.outputs:
                    for output in interaction.outputs:
                        print(output.text)
                        full_report += output.text
                    
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    report_filename = f"market_research_report_{timestamp}.md"
                    
                    # Save to timestamped file
                    with open(report_filename, "w") as f:
                        f.write(full_report)
                    print(f"\n\n[INFO] Report saved to '{report_filename}'")

                    # Also update 'latest' for convenience
                    with open("research_report.md", "w") as f:
                        f.write(full_report)
                    print(f"[INFO] Report also updated to 'research_report.md' (latest)")
                else:
                    print("No output received.")
                break
            elif status == 'failed':
                print(f"\nError: Research failed with error: {interaction.error}")
                break
            
            print(".", end="", flush=True)
            time.sleep(10)

    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
