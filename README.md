<p align="center">
  <h1 align="center">Nix</h1>
  <p align="center">
    <strong>AI-powered CLI for Spring Boot projects</strong>
  </p>
  <p align="center">
    Analyze | Debug | Understand
  </p>
</p>

<p align="center">
  <a href="#installation"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
  <a href="#license"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://groq.com"><img src="https://img.shields.io/badge/powered%20by-Groq-orange.svg" alt="Powered by Groq"></a>
</p>

---

## What Can Nix Do?

Talk to your Spring Boot project in natural language:

```
> analyze my dependencies
> what endpoints do I have?
> find issues in my code
> why am I getting NullPointerException at line 42?
> trace the call chain from UserController to database
> show me potential bean wiring problems
> analyze everything
```

Nix understands your project and gives you instant insights, finds bugs, and helps you debug issues.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/Nikhilsaini2204/nix.git
cd nix
pip install -e .
```

### 2. Configure

Get your free API key from **[Groq Console](https://console.groq.com/keys)**

```bash
nix config YOUR_API_KEY
```

### 3. Use It

Navigate to any Spring Boot project and start asking:

```bash
cd your-springboot-project
nix
```

---

## Demo

```bash
$ nix find issues

Using issue finder...

[BUILD] Compiling project...
  - 2 compilation errors found

[NULLSAFETY] Checking for potential NPEs...
  - 3 potential null pointer issues

[BEANS] Checking dependency injection...
  - 1 circular dependency detected

[ANNOTATIONS] Validating annotations...
  - @Entity without @Id in User.java

=== Issue Summary ===
Critical: 2
Warning: 4
Info: 1

Would you like me to suggest fixes for any of these?
```

---

## Features

### Analysis Tools

| Command | What it does |
|---------|--------------|
| `analyze dependencies` | Shows all Maven/Gradle dependencies with versions |
| `analyze endpoints` | Lists all REST API endpoints with HTTP methods |
| `analyze beans` | Finds all Spring beans (services, repos, components) |
| `analyze entities` | Shows JPA entities and their relationships |
| `analyze configuration` | Reads application.properties/yml settings |
| `analyze code` | Analyzes code structure, packages, and classes |
| `explore project` | Shows complete directory structure |
| `analyze everything` | Runs all analyzers in one go |

### Issue Finding & Debugging

| Command | What it does |
|---------|--------------|
| `find issues` | Comprehensive issue detection (build errors, null safety, bean wiring, annotations) |
| `build project` | Compile and show compilation errors with file:line locations |
| `run tests` | Execute tests and identify failures |
| `trace error <description>` | Diagnose errors from stack traces or descriptions |
| `check null safety` | Find potential NullPointerException issues |
| `check bean wiring` | Detect Spring dependency injection problems |
| `check annotations` | Verify correct usage of Spring/JPA annotations |
| `find call chain <method>` | Trace method calls (Controller -> Service -> Repository) |

### Search & Navigation

| Command | What it does |
|---------|--------------|
| `find <symbol>` | Search for usages of a class or method |
| `search <pattern>` | Search code for patterns |
| `describe <file>` | Explains what a Java file does |
| `semantic search <query>` | Find code by meaning using vector embeddings |

---

## Commands

```
nix                    Start interactive mode
nix <question>         Ask a question directly
nix config <key>       Configure your Groq API key
nix status             Display project information
nix help               Show help
```

**Interactive Commands:**
```
help      Show help
status    Show project status
new       Start fresh conversation
clear     Clear the screen
exit      Exit nix
```

---

## How It Works

Nix uses an agentic architecture with intelligent tool selection:

```
User Input (natural language)
       |
       v
Tool Selection (smart selector chooses relevant tools)
       |
       v
LLM with Function Calling (Groq API)
       |
       v
Tool Execution (24+ specialized tools)
       |
       v
Response Generation
       |
       v
User Output
```

**Key Components:**
- **Smart Tool Selector** - Only sends relevant tool definitions to LLM (saves tokens)
- **Conversation History** - Maintains context across multiple questions
- **Code Indexing** - Tree-sitter based Java parsing for accurate analysis
- **Call Graph Analysis** - Traces method relationships throughout codebase
- **Vector Embeddings** - Semantic search using ChromaDB (optional)

---

## Project Structure

```
nix/
├── main.py                 # CLI entry point with REPL
├── config.py               # Configuration management
├── commands/
│   ├── init.py             # Project initialization
│   └── status.py           # Status display
├── core/
│   ├── agent.py            # Agentic loop with conversation history
│   ├── tool_selector.py    # Smart tool selection
│   ├── tools_registry.py   # Tool registration system
│   ├── capabilities.py     # User guidance system
│   └── detector.py         # Spring Boot detection
├── llm/
│   ├── client.py           # Groq API client with rate limiting
│   ├── prompts.py          # Detection prompts
│   └── system_prompts.py   # Agent system prompt
├── tools/
│   ├── dependency_analyzer.py   # Maven/Gradle parsing
│   ├── code_analyzer.py         # Code structure analysis
│   ├── code_describer.py        # Detailed file analysis
│   ├── code_search.py           # Pattern search & find usages
│   ├── endpoint_analyzer.py     # REST endpoint discovery
│   ├── config_analyzer.py       # Configuration analysis
│   ├── bean_analyzer.py         # Spring bean analysis
│   ├── entity_analyzer.py       # JPA entity analysis
│   ├── project_explorer.py      # Directory tree
│   ├── file_reader.py           # File reading
│   ├── full_analyzer.py         # Combined analysis
│   ├── build_runner.py          # Build and compile
│   ├── test_runner.py           # Test execution
│   ├── error_tracer.py          # Error diagnosis
│   ├── call_chain_finder.py     # Call graph analysis
│   ├── null_safety_checker.py   # NPE detection
│   ├── bean_wiring_checker.py   # Dependency injection issues
│   ├── annotation_checker.py    # Annotation validation
│   ├── issue_finder.py          # Composite issue detection
│   ├── fix_suggester.py         # Fix recommendations
│   ├── semantic_search.py       # Vector-based code search
│   ├── error_diagnostics.py     # Comprehensive error analysis
│   └── smart_query.py           # Context-aware queries
├── indexer/
│   ├── index_builder.py    # Creates code index from Java files
│   ├── java_parser.py      # Tree-sitter based Java AST parsing
│   ├── index_storage.py    # Persistence to .nix/index/
│   ├── call_graph.py       # Call graph generation
│   ├── vector_store.py     # ChromaDB embeddings
│   ├── code_summarizer.py  # Code summarization
│   ├── context_builder.py  # Project context building
│   └── project_summarizer.py # High-level project summary
├── storage/
│   └── store.py            # Configuration and cache storage
└── utils/
    └── output.py           # CLI output formatting
```

---

## Requirements

- **Python** 3.8 or higher
- **Groq API Key** - [Get one free](https://console.groq.com/keys)

**Dependencies:**
- `requests` - HTTP client for API calls
- `tree-sitter` - Code AST parsing
- `tree-sitter-java` - Java language support
- `chromadb` - Vector embeddings (optional, for semantic search)

---

## Roadmap

- [x] Spring Boot detection
- [x] Project initialization
- [x] Dependency analysis
- [x] Code structure analysis
- [x] REST endpoint analysis
- [x] Spring bean analysis
- [x] JPA entity analysis
- [x] Configuration analysis
- [x] Code search & symbol finding
- [x] Full project analysis
- [x] Conversational interface with history
- [x] Smart tool selection
- [x] Issue finding system
- [x] Build runner with error parsing
- [x] Null safety checker
- [x] Bean wiring checker
- [x] Annotation validator
- [x] Call chain finder
- [x] Semantic search with embeddings
- [ ] Security vulnerability scanning
- [ ] Code quality suggestions
- [ ] IDE integrations

---

## Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## About The Creator

Built by **Nikhil** - a software developer exploring the world of AI.

- [LinkedIn](https://www.linkedin.com/in/nikhil2204/)
- [GitHub](https://github.com/Nikhilsaini2204)
- Instagram: [@ni.khll](https://instagram.com/ni.khll)
- Email: nikhilsaini6742@gmail.com

---

<p align="center">
  <sub>If you found this helpful, consider giving it a star</sub>
</p>
