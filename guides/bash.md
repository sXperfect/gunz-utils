# A Comprehensive Guide to Robust Bash Scripting
_version: 1.0.0_

This guide provides a set of best practices for writing safe, robust, and maintainable Bash scripts,
drawing on real-world examples. Whether you're automating simple tasks or building complex workflows
that interact with tools like Conda and Mamba, these principles will help you write better code.

## The Script Header: Your Script's ID Card
---

Every script should start with a header that provides essential metadata. This makes the script
easier to understand, use, and maintain.

- **Shebang (`#!`)**: The first line, `#!/usr/bin/env bash`, is crucial. It tells the system to
  execute the script using the `bash` interpreter found in the user's environment, which is more
  portable than a hardcoded path like `#!/bin/bash`.
- **Metadata**: Include a description, author, version, and usage instructions. A dedicated `--help`
  flag is a professional touch.

**Example:**

```bash
#!/usr/bin/env bash
#
# Description:
#   A robust script to start a server with specific configurations.
#
# Author:
#   Yeremia Gunawan Adhisantoso (sXperfect)
#
# Version: 1.9
#
# Usage:
#   ./your_script_name.sh [FLAGS]
#
# Flags:
#   --include-config: Optional. Includes detailed model sampling parameters.
#   --help:           Show this help message and exit.
```

## Unofficial Bash Strict Mode
---

To make your scripts safer and catch common errors early, always start with the "unofficial strict
mode."

```bash
set -o errexit   # Exit immediately if a command exits with a non-zero status.
set -o nounset   # Treat unset variables as an error when substituting.
set -o xtrace    # Print each command to stdout before executing it (great for debugging).
set -o pipefail  # A pipeline's exit code is that of the rightmost command to fail.
```

_You can write this more concisely as `set -euxo pipefail`._

## Variable and Constant Management
---

- **Use `readonly` for Constants**: If a variable's value should not change, declare it as a
  constant with `readonly`. This prevents accidental modification.
- **Descriptive Naming**: Use clear, uppercase names for global constants (e.g., `MODEL_PATH`) and
  lowercase for local variables within functions.
- **Quote Your Variables**: Always enclose variable expansions in double quotes (e.g., `"$MY_VAR"`)
  to prevent issues with word splitting and globbing if the variable contains spaces or special
  characters.
- **Use `${}` Braces**: While not always required, using braces like `${MY_VAR}` is a good habit. It
  avoids ambiguity when a variable is next to other characters (e.g., `echo "${MY_VAR}_suffix"`).
## Modular Code with Functions
---

Break down your script's logic into functions. This makes the code more readable, easier to debug,
and allows for reuse. A `main` function should serve as the primary entry point for your script's
logic.

**Example:**

```bash
#!/usr/bin/env bash
set -euxo pipefail

# --- Global Configuration ---
readonly LLAMA_SERVER_BIN="/path/to/server"
readonly DEFAULT_PORT="8080"

# --- Functions ---
function show_help() {
    # ... help message ...
}

function parse_arguments() {
    # ... argument parsing logic ...
}

function run_server() {
    local port="$1" # Receive arguments from main
    echo "Starting server on port ${port}..."
    "$LLAMA_SERVER_BIN" --port "$port"
}

# --- Main Execution ---
function main() {
    # Set default values
    local port="$DEFAULT_PORT"

    # Argument parsing would modify local variables like 'port'
    # parse_arguments "$@"

    # Run the main logic
    run_server "$port"
}

# Pass all script arguments to the main function
main "$@"
```

## Robust Argument Parsing
---

A `while` loop with a `case` statement is the standard, robust way to parse command-line flags and
arguments. It's flexible and handles various combinations of options gracefully.

**Example:**

```bash
function main() {
    # Default values
    local silent_mode=false
    local extend_ctx=false
    local port="8080"

    # Parse command-line arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --silent)
                silent_mode=true
                shift # Consume the flag
                ;;
            --port)
                port="$2" # Consume the flag and its value
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "Error: Unknown argument: $1" >&2
                show_help >&2
                exit 1
                ;;
        esac
    done

    # Now use the parsed variables
    echo "Configuration: Silent Mode=${silent_mode}, Port=${port}"
    # ... rest of main function ...
}
```

## Building Commands Safely with Arrays
---

When constructing a command with a variable number of arguments, **do not build it as a single
string**. This can lead to major quoting and word-splitting problems. The best practice is to use an
array.

**Example:**

```bash
function build_command_args() {
    local silent_mode="$1"
    local port="$2"
    local args=()

    # Base server arguments
    args+=(--model "/path/to/model.gguf")
    args+=(--port "$port")

    # Conditionally add a flag
    if [[ "$silent_mode" == "true" ]]; then
        args+=(--log-disable)
    fi

    # Conditionally add an argument with a value
    if [[ "$port" -gt "1024" ]]; then
        args+=(--threads "8")
    fi

    # Return the array elements as a string
    echo "${args[@]}"
}

# In main function:
# The read command splits the string from the function back into an array
read -r -a server_args <<< "$(build_command_args "$silent_mode" "$port")"

# Execute the command by expanding the array. The quotes are essential!
"$LLAMA_SERVER_BIN" "${server_args[@]}"
```

## Working with Conda/Mamba Environments in Scripts
---

Activating a Conda environment inside a script is tricky because `conda activate` is a shell
function, not a regular program. It needs to modify the _current_ shell's environment, which scripts
running in a subshell cannot do by default. Here are the modern, correct ways to handle this.

#### Method 1: Activating an Environment for a Sequence of Commands (Our Style)

If your script needs to run a series of commands within the context of an activated environment
(like our server script), you need to make the `conda` shell functions available to your script.
This is the most flexible approach for complex workflows.
- **How it works**: You `source` the Conda initialization script. This defines the `conda` and
  `mamba` functions in your script's shell, allowing `conda activate` to work as expected.
- **When to use it**: Use this method when you have a sequence of commands that all depend on the
  activated environment's `PATH` and variables.


**Example (The method used in our server script):**

```bash
# Define the path to your conda installation.
# This could be a readonly variable or sourced from an environment variable.
readonly CONDA_BASE_PATH="${CONDA_INSTALL_PATH:-/opt/conda}"

function setup_environment() {
    # Make the conda functions available
    # Use 'set +x' and 'set -x' to hide the verbose output of the init scripts
    set +x

    # Check for and source the conda initialization script
    local conda_init_script="${CONDA_BASE_PATH}/etc/profile.d/conda.sh"
    if [[ -f "$conda_init_script" ]]; then
        source "$conda_init_script"
    else
        echo "Error: Conda initialization script not found at $conda_init_script" >&2
        exit 1
    fi
    set -x

    # Now you can activate the environment
    mamba activate my-server-env
}

# In main function:
setup_environment

# Now, all subsequent commands will run inside the 'my-server-env'
echo "Running server setup..."
./configure_server.sh

echo "Starting server..."
# The GGML variables are set only for the server command's environment
GGML_CUDA_FORCE_MMQ=1 "$LLAMA_SERVER_BIN" "${server_args[@]}"
```

#### Method 2: The Recommended Approach for Single, Non-Interactive Commands (`conda run`)

For running a single command or a self-contained script within a Conda environment, the officially
recommended tool is `conda run`. It handles the environment activation and execution in a single,
clean step without altering your main script's environment.

- **How it works**: `conda run` starts a clean, non-interactive shell, activates the environment,
  runs your command, and then tears it all down.
- **When to use it**: This is the best choice for running Python scripts, build commands, or any
  single tool that resides in a Conda environment.


**Example:**

```bash
# Define the path to your conda installation.
readonly CONDA_BASE_PATH="${CONDA_INSTALL_PATH:-/opt/conda}"
readonly CONDA_BIN="${CONDA_BASE_PATH}/bin/conda"

# Check if the conda executable exists before trying to use it.
if [[ ! -x "$CONDA_BIN" ]]; then
    echo "Error: Conda executable not found or not executable at $CONDA_BIN" >&2
    exit 1
fi

# No need to 'source' or 'activate' first.
# This runs my_analysis.py using the python from the 'data-science' env.
"$CONDA_BIN" run -n data-science python my_analysis.py

# The --no-capture-output flag is useful for seeing live output
"$CONDA_BIN" run -n data-science --no-capture-output ./my_build_script.sh
```

## Advanced Best Practices
---

- **Check for Dependencies**: Before using a command, verify it exists. This provides a much clearer
  error message to the user.

    ```bash
    if ! command -v mamba &> /dev/null; then
        echo "Error: 'mamba' command not found. Please ensure Conda/Mamba is installed and in your PATH." >&2
        exit 1
    fi
    ```

- **Secure Temporary Files**: Never create predictable temporary file names like
  `/tmp/my_script.tmp`. Use the `mktemp` command, which creates a secure temporary file or
  directory.
- **Reliable Cleanup with `trap`**: What if your script errors out before it can clean up its
  temporary files? The `trap` command can execute cleanup code when the script exits, for any
  reason.

    ```bash
    # Create a temporary directory
    TMP_DIR=$(mktemp -d)

    # Set a trap to clean up the directory on EXIT, TERM, or INT signals
    trap 'echo "Cleaning up temporary files..."; rm -rf "$TMP_DIR"' EXIT TERM INT

    # ... your script logic uses $TMP_DIR ...
    echo "Processing data in $TMP_DIR"
    touch "${TMP_DIR}/my_file.log"

    echo "Script finished."
    # The trap will automatically execute when the script exits here.
    ```
