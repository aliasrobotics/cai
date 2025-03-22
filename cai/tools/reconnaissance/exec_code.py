"""
Tool for executing code via LLM tool calls.
"""
from cai.tools.common import run_command  # pylint: disable=import-error

def execute_code(code: str = "", language: str = "python",
                filename: str = "exploit", timeout: int = 100, ctf=None) -> str:
    """
    Create a file code store it and execute it

    This tool allows for executing code provided in different
    programming languages. It creates a permanent file with the provided code
    and executes it using the appropriate interpreter. You can exec this
    code as many times as you want using `generic_linux_command` tool.

    Priorize: Python and Perl

    Args:
        code: The code snippet to execute
        language: Programming language to use (default: python)
        filename: Base name for the file without extension (default: exploit)
        timeout: Timeout for the execution (default: 100 seconds)
                Use high timeout for long running code 
                Use low timeout for short running code
    Returns:
        Command output or error message from execution
    """

    if not code:
        return "No code provided to execute"

    # Map file extensions
    extensions = {
        "python": "py",
        "php": "php",
        "bash": "sh",
        "ruby": "rb",
        "perl": "pl",
        "golang": "go",
        "javascript": "js",
        "typescript": "ts",
        "rust": "rs",
        "csharp": "cs",
        "java": "java",
        "kotlin": "kt",
        "solidity": "sol"
    }
    ext = extensions.get(language.lower(), "txt")
    full_filename = f"{filename}.{ext}"

    create_cmd = f"cat << 'EOF' > {full_filename}\n{code}\nEOF"
    result = run_command(create_cmd, ctf=ctf)
    if "error" in result.lower():
        return f"Failed to create code file: {result}"
    if language.lower() == "python":
        exec_cmd = f"python3 {full_filename}"
    elif language.lower() == "php":
        exec_cmd = f"php {full_filename}"
    elif language.lower() in ["bash", "sh"]:
        exec_cmd = f"bash {full_filename}"
    elif language.lower() == "ruby":
        exec_cmd = f"ruby {full_filename}"
    elif language.lower() == "perl":
        exec_cmd = f"perl {full_filename}"
    elif language.lower() == "golang" or language.lower() == "go":
        temp_dir = f"/tmp/go_exec_{filename}"
        run_command(f"mkdir -p {temp_dir}", ctf=ctf)
        run_command(f"cp {full_filename} {temp_dir}/main.go", ctf=ctf)
        run_command(f"cd {temp_dir} && go mod init temp", ctf=ctf)
        exec_cmd = f"cd {temp_dir} && go run main.go"
    elif language.lower() == "javascript":
        exec_cmd = f"node {full_filename}"
    elif language.lower() == "typescript":
        exec_cmd = f"ts-node {full_filename}"
    elif language.lower() == "rust":
        # For Rust, we need to compile first
        run_command(f"rustc {full_filename} -o {filename}", ctf=ctf)
        exec_cmd = f"./{filename}"
    elif language.lower() == "csharp":
        # For C#, compile with dotnet
        run_command(f"dotnet build {full_filename}", ctf=ctf)
        exec_cmd = f"dotnet run {full_filename}"
    elif language.lower() == "java":
        # For Java, compile first
        run_command(f"javac {full_filename}", ctf=ctf)
        exec_cmd = f"java {filename}"
    elif language.lower() == "kotlin":
        # For Kotlin, compile first
        run_command(f"kotlinc {full_filename} -include-runtime -d {filename}.jar", ctf=ctf)
        exec_cmd = f"java -jar {filename}.jar"
    elif language.lower() == "solidity":
        # For Solidity, compile with solc
        run_command(f"mkdir -p {filename}_build", ctf=ctf)
        exec_cmd = f"npx solc --bin --abi --optimize -o {filename}_build {full_filename}"
    else:
        return f"Unsupported language: {language}"

    output = run_command(exec_cmd, ctf=ctf, timeout=timeout)

    return output
