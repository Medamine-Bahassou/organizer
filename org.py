#!/usr/bin/env python3

import subprocess
import sys
import os
# groq api
from groq import Groq


# --- Configuration ---
# You can change the model here if needed
GROQ_MODEL = "llama3-70b-8192" # <--- UPDATED MODEL
# Other options:
# GROQ_MODEL = "llama3-8b-8192"
# GROQ_MODEL = "mixtral-8x7b-32768"
# GROQ_MODEL = "gemma-7b-it"

TEMPLATE = f"""
I will give you a list of files and directories in a folder, based on the output of 'tree -L 1'.
Based *only* on the file and directory names provided, generate a Bash script to organize them into appropriate categorized subdirectories.
The script should first create the necessary subdirectories (using `mkdir -p` to avoid errors if they exist) and then move the files/directories into them (using `mv`).
Output *only* the raw Bash script content. Do not include any explanations, comments outside the script, or markdown formatting like ```bash ... ```.
If no organization is needed or possible based on the names, output nothing or just '#!/bin/bash\n# No organization needed'.
Focus on common categories like 'images', 'documents', 'scripts', 'archives', 'videos', 'audio', 'data', 'config', 'apps' etc., based on file extensions or names. Be conservative if the type is unclear. Do not attempt to move directories unless their names strongly suggest they belong in a category (e.g., 'my_images' could go to 'images'). Handle filenames with spaces correctly (quote them). Do not try to move the special Zone.Identifier files.
"""

def run_tree_command():
    """
    Runs the 'tree -L 1' command in the current directory
    and returns its standard output. Handles potential errors.
    """
    command = ['tree', '-L', '1']
    current_dir = os.getcwd()
    print(f"--- Running command: {' '.join(command)} in directory: {current_dir} ---")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=current_dir # Explicitly run in the current directory
        )
        print("\n--- Directory Listing (tree -L 1) ---")
        print(result.stdout)
        return result.stdout

    except FileNotFoundError:
        print(f"\nError: The command '{command[0]}' was not found.", file=sys.stderr)
        print("Please ensure the 'tree' utility is installed.", file=sys.stderr)
        print("On Debian/Ubuntu: sudo apt update && sudo apt install tree", file=sys.stderr)
        print("On macOS (using Homebrew): brew install tree", file=sys.stderr)
        sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"\nError: Command '{' '.join(e.cmd)}' failed with exit code {e.returncode}.", file=sys.stderr)
        if e.stdout:
            print("\n--- Command Output (stdout) before error ---")
            print(e.stdout)
        if e.stderr:
            print("\n--- Command Error Output (stderr) ---", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
        sys.exit(e.returncode)

    except Exception as e:
        print(f"\nAn unexpected error occurred while running tree: {e}", file=sys.stderr)
        sys.exit(1)

def get_groq_completion(text, model=GROQ_MODEL):
    """
    Sends text to the Groq API and returns the completion.
    Handles API key errors and other potential issues.
    """
    # --- CORRECT WAY TO GET THE API KEY ---
    api_key = os.environ.get("GROQ_API_KEY")
    # ----------------------------------------
    if not api_key:
        print("Error: GROQ_API_KEY environment variable not set.", file=sys.stderr)
        print("Please set the GROQ_API_KEY environment variable before running the script.", file=sys.stderr)
        print("Example: export GROQ_API_KEY='your_api_key_here'", file=sys.stderr)
        sys.exit(1)

    print(f"\n--- Requesting Bash script generation from Groq ({model}) ---")

    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates *only* raw Bash scripts as requested, ensuring filenames with spaces are quoted."
                },
                {
                    "role": "user",
                    "content": f"{TEMPLATE}\nDirectory listing:\n{text}",
                }
            ],
            model=model,
            temperature=0.2, # Lower temperature for more deterministic script generation
            stream=False,
        )

        response_content = chat_completion.choices[0].message.content
        print("--- Groq response received ---")

        # Basic check if the response looks like a script
        if not response_content or not response_content.strip():
             print("Warning: Groq returned an empty response.")
             return "#!/bin/bash\n# Groq returned empty response"

        # Sometimes models still add markdown fences despite instructions
        if response_content.strip().startswith("```bash"):
            response_content = response_content.strip()[7:]
            if response_content.endswith("```"):
                response_content = response_content[:-3]
        elif response_content.strip().startswith("```"):
             response_content = response_content.strip()[3:]
             if response_content.endswith("```"):
                 response_content = response_content[:-3]


        # Ensure it starts with a shebang, or add one
        if not response_content.strip().startswith("#!"):
             response_content = "#!/bin/bash\n" + response_content

        return response_content.strip()

    # Handle potential Groq API errors specifically
    except Exception as e:
         # Improve error reporting for Groq specific errors if possible
        try:
            # Attempt to access potential Groq error details (may vary based on library version)
            if hasattr(e, 'status_code') and hasattr(e, 'body'):
                print(f"\nAn error occurred during the Groq API call: Status {e.status_code} - Body: {e.body}", file=sys.stderr)
            elif hasattr(e, 'message'):
                 print(f"\nAn error occurred during the Groq API call: {e.message}", file=sys.stderr)
            else:
                print(f"\nAn error occurred during the Groq API call: {e}", file=sys.stderr)
        except Exception: # Fallback to generic error print
            print(f"\nAn error occurred during the Groq API call: {e}", file=sys.stderr)
        sys.exit(1)


def execute_bash_script(script_content):
    """
    Executes the given Bash script string in the current directory.
    Handles execution errors.
    """
    print("\n--- Attempting to execute generated Bash script ---")

    # Filter out placeholder/empty scripts more robustly
    clean_script = "\n".join(line for line in script_content.splitlines() if line.strip() and not line.strip().startswith('#'))
    if not clean_script:
        print("Script is empty or contains only comments/shebang. No commands to execute.")
        return

    current_dir = os.getcwd()
    print(f"--- Running in directory: {current_dir} ---")

    try:
        # Using /bin/bash -ec "script" is safer:
        # -e: exit immediately if a command exits with a non-zero status.
        # -c: Read commands from string
        result = subprocess.run(
            ['/bin/bash', '-ec', script_content], # Added -e flag
            capture_output=True,
            text=True,
            check=True, # Raise an exception if the script exits with non-zero status
            cwd=current_dir # Ensure execution happens in the intended directory
        )

        print("--- Script Execution Successful ---")
        if result.stdout:
            print("\n--- Script Output (stdout) ---")
            print(result.stdout)
        if result.stderr:
            # Some tools might print informational messages to stderr even on success
            print("\n--- Script Error Output (stderr) ---")
            print(result.stderr, file=sys.stderr)

    except subprocess.CalledProcessError as e:
        print(f"\nError: Generated Bash script failed with exit code {e.returncode}.", file=sys.stderr)
        print("Failed Command String (first line of script likely indicates where):")
        print(script_content.splitlines()[0 if not script_content.startswith("#!") else 1]) # Print first command line
        if e.stdout:
            print("\n--- Script Output (stdout) before error ---")
            print(e.stdout)
        if e.stderr:
            print("\n--- Script Error Output (stderr) ---", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
        # Stop execution since the script failed
        sys.exit(e.returncode)

    except Exception as e:
        print(f"\nAn unexpected error occurred during script execution: {e}", file=sys.stderr)
        sys.exit(1)

# Standard Python idiom to make the script runnable
if __name__ == "__main__":
    # 1. Get directory listing
    tree_output = run_tree_command()

    if not tree_output or not tree_output.strip() or " 0 directories, 0 files" in tree_output:
      print("Warning: 'tree -L 1' produced no significant output. No files/dirs to organize?")
      sys.exit(0)

    # 2. Generate Bash script using Groq
    generated_bash_script = get_groq_completion(tree_output)

    # 3. Show the script and ask for confirmation
    print("\n" + "="*60)
    print("                Generated Bash Script for Review")
    print("="*60)
    print(generated_bash_script)
    print("="*60)
    print("\n" + "#"*60)
    print("    WARNING: Executing AI-generated code can be risky.")
    print("             Review the script above carefully.")
    print("             Ensure filenames with spaces are quoted.")
    print("#"*60)

    try:
        # Default to No
        confirm = input("Do you want to execute this script? (y/N): ")
    except EOFError: # Handle case where input is piped or redirected
        print("\nNon-interactive mode detected. Aborting execution.", file=sys.stderr)
        sys.exit(1)

    if confirm.lower() == 'y':
        # 4. Execute the script if confirmed
        execute_bash_script(generated_bash_script)
        print("\n--- Script execution attempt finished ---")
        print("--- Please verify the changes in your directory ---")
    else:
        print("\n--- Execution cancelled by user ---")
        sys.exit(0)