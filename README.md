# 🔍 SCOSINT_AI

**The most powerful modular OSINT + AI platform — find any digital footprint.**

A fully local, open-source, plugin-based intelligence platform that discovers a person's digital presence across the internet using their name, email, phone number, photo, or any identifier.

## ✨ Key Features

- **🔌 Microkernel Plugin Architecture** — Every tool is a swappable plugin. Add, remove, or replace any component without touching the core.
- **🏠 100% Local & Private** — All processing runs on your infrastructure. No cloud dependencies.
- **🌐 30+ OSINT Plugins** — Username enumeration, email lookup, phone analysis, breach detection, reverse image search, social media scraping.
- **🤖 Local AI Analysis** — Ollama-powered LLM for alias generation, profile summarization, and risk scoring.
- **🛡️ Social Media Bypass** — Playwright stealth engine handles Instagram popups, LinkedIn login walls, and more.
- **⚡ Async & Scalable** — FastAPI + Celery + Redis architecture with multi-queue task processing.
- **📋 License-Clean** — MIT/Apache tools imported directly; GPL tools isolated via subprocess; AGPL tools in separate containers.

## 🏗️ Architecture

```
FastAPI (REST API) ←→ Redis (Broker) ←→ Celery Workers
                                              ↓
                                     Plugin Manager (Core)
                                              ↓
                    ┌──────────┬──────────┬──────────┬──────────┐
                    │ Username │  Email   │  Phone   │  Image   │
                    │ Plugins  │ Plugins  │ Plugins  │ Plugins  │
                    ├──────────┼──────────┼──────────┼──────────┤
                    │  Search  │  Breach  │  Alias   │    AI    │
                    │ Plugins  │ Plugins  │ Plugins  │ Plugins  │
                    └──────────┴──────────┴──────────┴──────────┘
                                              ↓
                    SearXNG Container    Ollama Container    Playwright Pool
```

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/Ali190903/SCOSINT_AI.git
cd SCOSINT_AI

# Start all services
docker compose up --build

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## 📖 Documentation

- [Plugin Development Guide](docs/plugin_development.md)
- [API Reference](docs/api_reference.md)

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
