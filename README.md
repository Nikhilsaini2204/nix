<p align="center">
  <h1 align="center">⚡ Nix</h1>
  <p align="center">
    <strong>AI-powered CLI for Spring Boot projects</strong>
  </p>
  <p align="center">
    Detect • Analyze • Manage
  </p>
</p>

<p align="center">
  <a href="#installation"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
  <a href="#license"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT"></a>
  <a href="https://groq.com"><img src="https://img.shields.io/badge/powered%20by-Groq-orange.svg" alt="Powered by Groq"></a>
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Detection** | Automatically identifies Spring Boot projects (Maven & Gradle) |
| 🤖 **AI-Powered** | Uses Groq LLM for intelligent build file analysis |
| 📊 **Project Tracking** | Monitors structure changes and tracks metadata |
| 🚀 **Simple CLI** | Just type `nix` - that's it |

---

## 🚀 Quick Start

### 1. Install

**Option A: Using pipx (Recommended)**
```bash
git clone https://github.com/Nikhilsaini2204/niks.git
pipx install -e /path/to/nix
```

**Option B: Using pip**
```bash
git clone https://github.com/nikhil/nix.git
cd nix
pip install .
```

> **Note:** pipx installs the tool in an isolated environment and makes it globally available without activating a virtual environment.

### 2. Configure

Get your free API key from **[Groq Console](https://console.groq.com/keys)**

```bash
nix config YOUR_API_KEY
```

### 3. Initialize Your Project

Navigate to your Spring Boot project and run:

```bash
cd your-springboot-project
nix
```

On first run, `nix` will:
- ✓ Detect if it's a Spring Boot project (checks for `pom.xml` or `build.gradle`)
- ✓ Analyze your build file using AI
- ✓ Create a `.nix/` folder to store project metadata
- ✓ Scan and count your project files
- ✓ Save project configuration

### 4. Check Status Anytime

```bash
nix status
```

---

## 📖 Commands

```
nix                    Initialize or show project status
nix config <key>       Configure your Groq API key
nix status             Display project information
nix analyze            Analyze your code (coming soon)
nix refresh            Update project index (coming soon)
```

---

## 🎬 Demo

```bash
$ cd my-springboot-app
$ nix

Initializing nix...
Checking if this is a Spring Boot project...
✓ Detected Spring Boot 3.2.0
Scanning project structure...
✓ Nix initialized successfully.
Project contains 15 Java files.

Next steps:
  Run 'nix analyze' to analyze your code
  Run 'nix status' to check project status
```

---

## 🛠 How It Works

```
┌─────────────────────────────────────────────────────────┐
│                         nix                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   1. 📁 Detect      Find pom.xml or build.gradle       │
│                              ↓                          │
│   2. 🤖 Analyze     Send to Groq LLM for analysis      │
│                              ↓                          │
│   3. 💾 Store       Save metadata in .nix/ folder     │
│                              ↓                          │
│   4. 👀 Monitor     Track changes over time            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
nix/
├── 📄 main.py              # CLI entry point
├── 📄 config.py            # Configuration management
├── 📁 commands/
│   ├── init.py             # Project initialization
│   └── status.py           # Status display
├── 📁 core/
│   └── detector.py         # Spring Boot detection
├── 📁 llm/
│   ├── client.py           # Groq API client
│   └── prompts.py          # LLM prompts
├── 📁 utils/
│   ├── file.py             # File operations
│   └── logger.py           # Logging utilities
└── 📁 storage/
    └── store.py            # JSON persistence
```

---

## 📋 Requirements

- **Python** 3.8 or higher
- **Groq API Key** - [Get one free](https://console.groq.com/keys)

---

## 🗺 Roadmap

- [x] Spring Boot detection
- [x] Project initialization
- [x] Status tracking
- [ ] Code analysis
- [ ] Dependency scanning
- [ ] Security checks
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

MIT License - feel free to use this project however you'd like.

---

<p align="center">
  <strong>Built with ❤️ by Nikhil</strong>
</p>

<p align="center">
  <sub>If you found this helpful, consider giving it a ⭐</sub>
</p>
