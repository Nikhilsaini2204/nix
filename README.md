<p align="center">
  <h1 align="center">⚡ Nix</h1>
  <p align="center">
    <strong>AI-powered CLI for Spring Boot projects</strong>
  </p>
  <p align="center">
    Analyze • Explore • Understand
  </p>
</p>

<p align="center">
  <a href="#installation"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
  <a href="#license"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://groq.com"><img src="https://img.shields.io/badge/powered%20by-Groq-orange.svg" alt="Powered by Groq"></a>
</p>

---

## ✨ What Can Nix Do?

Talk to your Spring Boot project in natural language:

```
> analyze my dependencies
> what endpoints do I have?
> show me the project structure
> analyze everything
> find usages of UserService
> what does TestController do?
```

Nix understands your project and gives you instant insights.

---

## 🚀 Quick Start

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

## 🎬 Demo

```bash
$ nix analyze everything

Using 1 tool...

⏺ Exploring project structure
  ⎿  12 directories, 45 files
⏺ Analyzing dependencies
  ⎿  23 dependencies (8 Spring) via maven
⏺ Analyzing code structure
  ⎿  15 Java files, 6 packages
  ⎿  3 controllers, 4 services, 2 repositories
⏺ Finding REST endpoints
  ⎿  12 endpoints in 3 controllers
  ⎿  Methods: 6 GET, 4 POST, 2 DELETE
⏺ Reading configuration
  ⎿  18 properties in 2 file(s)
⏺ Scanning Spring beans
  ⎿  9 beans total
⏺ Finding JPA entities
  ⎿  3 entities, 5 relationships

That's the full overview. Want me to dive deeper into anything specific?
```

---

## 🛠 Available Analysis Tools

| Command | What it does |
|---------|--------------|
| `analyze dependencies` | Shows all Maven/Gradle dependencies with versions |
| `analyze endpoints` | Lists all REST API endpoints with HTTP methods |
| `analyze beans` | Finds all Spring beans (services, repos, components) |
| `analyze entities` | Shows JPA entities and their relationships |
| `analyze configuration` | Reads application.properties/yml settings |
| `explore project` | Shows complete directory structure |
| `analyze everything` | Runs all analyzers in one go |
| `find <symbol>` | Searches for usages of a class/method |
| `describe <file>` | Explains what a Java file does |

---

## 📖 Commands

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

## 📁 Project Structure

```
nix/
├── main.py                 # CLI entry point
├── config.py               # Configuration management
├── commands/
│   ├── init.py             # Project initialization
│   └── status.py           # Status display
├── core/
│   ├── agent.py            # Agentic loop with conversation history
│   ├── capabilities.py     # User guidance system
│   ├── detector.py         # Spring Boot detection
│   └── tools_registry.py   # Tool registration system
├── llm/
│   ├── client.py           # Groq API client with rate limiting
│   ├── prompts.py          # Detection prompts
│   └── system_prompts.py   # Agent system prompt
├── tools/
│   ├── bean_analyzer.py    # Spring bean analysis
│   ├── code_analyzer.py    # Code structure analysis
│   ├── code_describer.py   # Local Java file parsing
│   ├── code_search.py      # Code search & find usages
│   ├── config_analyzer.py  # Configuration analysis
│   ├── dependency_analyzer.py  # Dependency analysis
│   ├── endpoint_analyzer.py    # REST endpoint analysis
│   ├── entity_analyzer.py  # JPA entity analysis
│   ├── file_reader.py      # File reading
│   ├── full_analyzer.py    # Combined full analysis
│   └── project_explorer.py # Project structure explorer
└── utils/
    └── output.py           # CLI output formatting
```

---

## 📋 Requirements

- **Python** 3.8 or higher
- **Groq API Key** - [Get one free](https://console.groq.com/keys)

---

## 🗺 Roadmap

- [x] Spring Boot detection
- [x] Project initialization
- [x] Dependency analysis
- [x] Code structure analysis
- [x] REST endpoint analysis
- [x] Spring bean analysis
- [x] JPA entity analysis
- [x] Configuration analysis
- [x] Code search
- [x] Full project analysis
- [x] Conversational interface
- [ ] Security vulnerability scanning
- [ ] Code quality suggestions
- [ ] IDE integrations

---

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 👨‍💻 About The Creator

Built with ❤️ by **Nikhil** - a software developer exploring the world of AI.

Feel free to connect:
- 💼 [LinkedIn](https://www.linkedin.com/in/nikhil2204/)
- 🐙 [GitHub](https://github.com/Nikhilsaini2204)
- 📸 Instagram: [@ni.khll](https://instagram.com/ni.khll)
- 📧 Email: nikhilsaini6742@gmail.com

---

<p align="center">
  <sub>If you found this helpful, consider giving it a ⭐</sub>
</p>
