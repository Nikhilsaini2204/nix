
### AI-powered CLI for Spring Boot projects

</div>

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](#requirements)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](#license)
[![Powered by Groq](https://img.shields.io/badge/powered%20by-Groq-orange.svg)](https://groq.com)

---

---

## 👨‍💻 Team & Contributors

| Name         | Roll Number |
| ------------ | ----------- |
| Nikhil Saini | 2211981245  |
| Akshit Mehta | 2211981043  |

---

## 🎓 Mentors

| Name             | Email                                                               |
| ---------------- | ------------------------------------------------------------------- |
| Dr. Rajat Takkar | [rajat.takkar@chitkara.edu.in](mailto:rajat.takkar@chitkara.edu.in) |
| Isha Kansal      | [isha.kansal@chitkatra.edu.in](mailto:isha.kansal@chitkatra.edu.in) |

---


Talk to your Spring Boot project in plain English:

```
$ nix

        ███╗   ██╗ ██╗ ██╗  ██╗
        ████╗  ██║ ██║ ╚██╗██╔╝
        ██╔██╗ ██║ ██║  ╚███╔╝
        ██║╚██╗██║ ██║  ██╔██╗
        ██║ ╚████║ ██║ ██╔╝ ██╗
        ╚═╝  ╚═══╝ ╚═╝ ╚═╝  ╚═╝

        ════════════════════════

    AI-powered assistant for Spring Boot projects
    Type your question or 'help' for options. Ctrl+C to exit.

> find issues in my code

Using 1 tool...
⏺ find_issues
  ⎿  Found 5 issues

[CRITICAL] Missing @Id annotation
  at User.java:15

[HIGH] Potential null pointer
  at UserService.java:42

[MEDIUM] Circular dependency detected
  at OrderService.java:28

Summary: Critical: 1 | High: 1 | Medium: 3

> what endpoints do I have?

Using 1 tool...
⏺ smart_query
  ⎿  Found answer in context

This project has 12 REST endpoints:
- GET    /api/users
- GET    /api/users/{id}
- POST   /api/users
- DELETE /api/users/{id}
- GET    /api/products
...
```

---

## Quick Start

```bash
# Install
git clone https://github.com/Nikhilsaini2204/nix.git
cd nix
pip install -e .

# Configure (get free key from console.groq.com/keys)
nix config YOUR_API_KEY

# Use
cd your-springboot-project
nix
```

---

## What You Can Ask

**Analysis**
```
> analyze my dependencies
> what endpoints do I have?
> show me all Spring beans
> analyze JPA entities
> explore project structure
> analyze everything
```

**Issue Finding**
```
> find issues in my code
> check for null pointer problems
> check bean wiring issues
> validate my annotations
> build the project
> run the tests
```

**Search & Debug**
```
> find usages of UserService
> trace call chain from UserController
> where is authentication handled?
> describe UserController.java
> why am I getting NullPointerException at line 42?
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Dependency Analysis** | Parse Maven/Gradle dependencies |
| **Endpoint Discovery** | Find all REST APIs with methods |
| **Bean Analysis** | Detect Spring components |
| **Entity Mapping** | Analyze JPA entities and relationships |
| **Issue Finder** | Find bugs, NPEs, wiring problems |
| **Build Runner** | Compile and parse errors |
| **Test Runner** | Run tests and report failures |
| **Call Chain Tracer** | Trace Controller → Service → Repository |
| **Semantic Search** | Find code by meaning |

---

## Commands

```
nix                    Start interactive mode
nix <question>         Ask directly
nix config <key>       Set API key
nix status             Show project info
nix help               Show help
```

**In interactive mode:**
```
help      Show commands
status    Project status
new       Fresh conversation
clear     Clear screen
exit      Quit
```

---

## Requirements

- Python 3.8+
- [Groq API Key](https://console.groq.com/keys) (free)

---

## How It Works

```
User Question (natural language)
        ↓
   Tool Selector (picks relevant tools)
        ↓
   LLM + Function Calling (Groq)
        ↓
   Tool Execution (24+ tools)
        ↓
   Response
```

---

## Project Structure

```
nix/
├── main.py              # CLI entry
├── core/
│   ├── agent.py         # Conversation loop
│   ├── tool_selector.py # Smart tool picking
│   └── tools_registry.py
├── tools/               # 24+ analysis tools
│   ├── issue_finder.py
│   ├── build_runner.py
│   ├── endpoint_analyzer.py
│   ├── null_safety_checker.py
│   └── ...
├── indexer/             # Code indexing
│   ├── java_parser.py   # Tree-sitter parsing
│   └── call_graph.py
└── llm/
    └── client.py        # Groq API
```

---

## License

MIT

---

## Author

**Nikhil** - [LinkedIn](https://www.linkedin.com/in/nikhil2204/) | [GitHub](https://github.com/Nikhilsaini2204)

---

*If this helped you, consider giving it a star*
