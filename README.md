# Devstral Engineer v2 🐋

## Overview

Devstral Engineer v2 is a powerful AI-powered coding assistant that provides an interactive terminal interface for seamless code development. It integrates with Devstral's advanced reasoning models to offer intelligent file operations, code analysis, and development assistance through natural conversation and function calling.

## 🚀 Latest Update: Function Calling Architecture

**Version 2.0** introduces a big upgrade from structured JSON output to native function calling, providing:
- **Natural conversations** with the AI without rigid response formats
- **Automatic file operations** through intelligent function calls
- **Real-time reasoning visibility** with Chain of Thought (CoT) capabilities
- **Enhanced reliability** and better error handling

## Key Features

### 🧠 **AI Capabilities**
- **Elite Software Engineering**: Decades of experience across all programming domains
- **Chain of Thought Reasoning**: Visible thought process before providing solutions
- **Code Analysis & Discussion**: Expert-level insights and optimization suggestions
- **Intelligent Problem Solving**: Automatic file reading and context understanding
- **Built-in Web Search**: Fetch DuckDuckGo results on demand with `/search` or `/deep-research`

### 🛠️ **Function Calling Tools**
The AI can automatically execute these operations when needed:

#### `read_file(file_path: str)`
- Read single file content with automatic path normalization
- Built-in error handling for missing or inaccessible files
- **Automatic**: AI can read any file you mention or reference in conversation

#### `read_multiple_files(file_paths: List[str])`
- Batch read multiple files efficiently
- Formatted output with clear file separators

#### `view(file_path: str, offset: int, limit: int)`
- Display part of a file starting at `offset` showing up to `limit` lines
- For very large files a short summary is appended

#### `create_file(file_path: str, content: str)`
- Create new files or overwrite existing ones
- Automatic directory creation and safety checks

#### `create_multiple_files(files: List[Dict])`
- Create multiple files in a single operation
- Perfect for scaffolding projects or creating related files

#### `edit_file(file_path: str, original_snippet: str, new_snippet: str)`
- Precise snippet-based file editing
- Safe replacement with exact matching
#### `list_directory(path: str)`
- List files in a directory
#### `create_directory(dir_path: str)`
- Create directories recursively
#### `run_bash(command: str, timeout_ms: int)`
- Execute safe shell commands
#### `tree_view(path: str, depth: int)`
- Display a directory tree
#### `run_tests(test_path: str, options: str)`
- Run project tests via pytest
#### `linter_checker(path: str, linter_command: str)`
- Run a code linter like ruff
#### `formatter(path: str, formatter_command: str)`
- Run a code formatter like black
#### `grep(pattern: str, file_path: str, ignore_case: bool)`
- Search for a regex pattern within a file and return matching lines
#### `glob(pattern: str, cwd: str)`
- List files matching a glob pattern
#### `summarize_code(file_path: str)`
- Summarize a large code file for quick context
#### `git_status()` / `git_diff(path: str)` / `git_log(n: int)` / `git_add(path: str)`
- Interact with git to inspect and stage changes
#### `run_build(command: str)`
- Trigger project build systems
#### `manage_dependency(action: str, package: str)`
- Install or uninstall dependencies via pip

### 📁 **File Operations**

#### **Automatic File Reading (Recommended)**
The AI can automatically read files you mention:
```
You> Can you review the main.py file and suggest improvements?
→ AI automatically calls read_file("main.py")

You> Look at src/utils.py and tests/test_utils.py
→ AI automatically calls read_multiple_files(["src/utils.py", "tests/test_utils.py"])
```

#### **Manual Context Addition (Optional)**
For when you want to preload files into conversation context:
- **`/add path/to/file`** - Include single file in conversation context
- **`/add path/to/folder`** - Include entire directory (with smart filtering)
- **`/undo`** - Undo the last file change (`/undo N` for multiple steps)
- **`/search your query`** - Fetch DuckDuckGo results and add them as context
- **`/deep-research your query`** - Fetch articles for multi-page research

**Note**: The `/add` command is mainly useful when you want to provide extra context upfront. The AI can read files automatically via function calls whenever needed during the conversation.

### 🎨 **Rich Terminal Interface**
- **Color-coded feedback** (green for success, red for errors, yellow for warnings)
- **Real-time streaming** with visible reasoning process
- **Structured tables** for diff previews
- **Progress indicators** for long operations

### 🛡️ **Security & Safety**
- **Path normalization** and validation
- **Directory traversal protection**
- **File size limits** (5MB per file)
- **Binary file detection** and exclusion

## Getting Started

### Prerequisites
1. **OpenRouter API Key**: Get your API key from [OpenRouter](https://openrouter.ai)
2. **Python 3.11+**: Required for optimal performance

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd devstral-engineer
   ```

2. **Set up configuration**:
   ```bash
   mkdir -p ~/.config/devstral-engineer
   cat > ~/.config/devstral-engineer/config.yaml <<'EOF'
   api_key: your_api_key_here
   default_model: mistralai/devstral-small:free
   EOF
   ```

3. **Install dependencies** (choose one method):

   #### Using uv (recommended - faster)
   ```bash
   uv venv
   uv run -m devstral_cli setup  # create config interactively
   uv run -m devstral_cli        # start chatting
   ```

   #### Using pip
   ```bash
   pip install -r requirements.txt
   devstral setup  # one-time configuration
   devstral        # start the chat
   ```

### Usage Examples

#### **Natural Conversation with Automatic File Operations**
```
You> Can you read the main.py file and create a test file for it?

💭 Reasoning: I need to first read the main.py file to understand its structure...

🤖 Assistant> I'll read the main.py file first to understand its structure.
⚡ Executing 1 function call(s)...
→ read_file
✓ Read file 'main.py'

🔄 Processing results...
Now I'll create comprehensive tests based on the code structure I found.
⚡ Executing 1 function call(s)...
→ create_file
✓ Created/updated file at 'test_main.py'

I've analyzed main.py and created comprehensive tests covering all the main functions...
```

#### **Automatic Multi-File Analysis**
```
You> Compare the implementation in utils.py with the tests in test_utils.py

💭 Reasoning: I need to read both files to compare them...

🤖 Assistant> I'll read both files to analyze the implementation and tests.
⚡ Executing 1 function call(s)...
→ read_multiple_files
✓ Read files: utils.py, test_utils.py

🔄 Processing results...
After analyzing both files, I can see several areas where the tests could be improved...
```

#### **Manual Context Loading (Optional)**
```
You> /add src/

✓ Added folder 'src/' to conversation.
📁 Added files: (15 files)
  📄 src/utils.py
  📄 src/models.py
  ...

You> Now review this codebase structure

🤖 Assistant> I've reviewed your codebase and found several areas for improvement:

1. **Error Handling**: The utils.py file could benefit from more robust error handling...
```

## Technical Details

### **Model**: mistralai/devstral-small:free
- Powered by Devstral with Chain-of-Thought reasoning
- Real-time reasoning visibility during processing
- Enhanced problem-solving capabilities

### **Function Call Execution Flow**
1. **User Input** → Natural language request
2. **AI Reasoning** → Visible thought process (CoT)
3. **Function Calls** → Automatic tool execution
4. **Real-time Feedback** → Operation status and results
5. **Follow-up Response** → AI processes results and responds

### **Streaming Architecture**
- **Triple-stream processing**: reasoning + content + tool_calls
- **Real-time tool execution** during streaming
- **Automatic follow-up** responses after tool completion
- **Error recovery** and graceful degradation

## Advanced Features

### **Intelligent Context Management**
- **Automatic file detection** from user messages
- **Smart conversation cleanup** to prevent token overflow
- **File content preservation** across conversation history
- **Tool message integration** for complete operation tracking

### **Batch Operations**
```
You> Create a complete Flask API with models, routes, and tests

🤖 Assistant> I'll create a complete Flask API structure for you.
⚡ Executing 1 function call(s)...
→ create_multiple_files
✓ Created 4 files: app.py, models.py, routes.py, test_api.py
```

### **Project Analysis**
```
You> /add .
You> Analyze this entire project and suggest a refactoring plan

🤖 Assistant> ⚡ Executing 1 function call(s)...
→ read_multiple_files
Based on my analysis of your project, here's a comprehensive refactoring plan...
```

## File Operations Comparison

| Method | When to Use | How It Works |
|--------|-------------|--------------|
| **Automatic Reading** | Most cases - just mention files | AI automatically calls `read_file()` when you reference files |
| **`/add` Command** | Preload context, bulk operations | Manually adds files to conversation context upfront |

**Recommendation**: Use natural conversation - the AI will automatically read files as needed. Use `/add` only when you want to provide extra context upfront.

## Troubleshooting

### **Common Issues**

**API Key Not Found**
```bash
# Ensure ~/.config/devstral-engineer/config.yaml contains your key
cat ~/.config/devstral-engineer/config.yaml
```

**Import Errors**
```bash
# Install dependencies
uv sync  # or pip install -r requirements.txt
```

**File Permission Errors**
- Ensure you have write permissions in the working directory
- Check file paths are correct and accessible

## Contributing

This is an experimental project showcasing Devstral reasoning model capabilities. Contributions are welcome!

### **Development Setup**
```bash
git clone <repository-url>
cd devstral-engineer
uv venv
uv sync
```

### **Run**
```bash
# Preferred way using uv
uv run -m devstral_cli
```
or
```bash
devstral
```

### Debug Profiling
Run with `--debug` to see timing information for context management:
```bash
uv run -m devstral_cli --debug
```
Sample output on a 50 message history showed `_manage_context_window` averaging
around 6ms per call while `trim_conversation_history` completed in under
10ms. Optimization isn't currently necessary.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

This project is experimental and developed for testing Devstral reasoning model capabilities.

---

> **Note**: This is an experimental project developed to explore the capabilities of Devstral's reasoning model with function calling. The AI can automatically read files you mention in conversation, while the `/add` command is available for when you want to preload context. Use responsibly and enjoy the enhanced AI pair programming experience! 🚀

