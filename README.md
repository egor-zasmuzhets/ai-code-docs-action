# 🤖 AI Code Docs & Reviewer

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-AI%20Code%20Reviewer-blue)](https://github.com/marketplace/ai-code-docs-reviewer)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Automated code documentation and code review powered by LLM.  
> Works with **GitHub Models** (free, no API key) or **Groq** (faster).

---

## ✨ Features

- 🔍 **Code review**
  - Security
  - Performance
  - Style
  - Bug detection
- 📝 **Auto-documentation**
  - Generates and updates docs automatically
- 💬 **Inline comments**
  - Comments directly on PR lines
- 🌍 **Multi-language support**
  - Python, JS, TS, Go, Java, Rust, and more
- 🎯 **Exclude patterns**
  - Skip tests, generated files, or folders
- 🔌 **Multiple LLM providers**
  - GitHub Models (free)
  - Groq (fast)

---

## 🚀 Quick Start

Create a workflow file:

📄 `.github/workflows/ai-review.yml`

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest

    permissions:
      contents: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
      - uses: egor-zasmuzhets/ai-code-docs-action@v1
````

✅ **No API key required** — uses GitHub Models for free.

---

## 🔑 Optional: Use Groq (Faster)

1. Get a free API key: [https://console.groq.com](https://console.groq.com)
2. Add it to repository secrets as `GROQ_API_KEY`
3. Update your workflow:

```yaml
- uses: egor-zasmuzhets/ai-code-docs-action@v1
  with:
    provider: "groq"
    api-key: ${{ secrets.GROQ_API_KEY }}
```

---

## ⚙️ Configuration

```yaml
- uses: egor-zasmuzhets/ai-code-docs-action@v1
  with:
    provider: "auto"                    # auto | groq | github-models
    api-key: ${{ secrets.GROQ_API_KEY }}
    exclude: "tests/**,**/*_test.py"
    review-prompt: "Focus on security only"
```

### Inputs

| Input           | Default | Description                              |
| --------------- | ------- | ---------------------------------------- |
| `provider`      | `auto`  | Auto-selects Groq if API key is provided |
| `api-key`       | —       | Required only for Groq                   |
| `exclude`       | (empty) | Comma-separated glob patterns            |
| `review-prompt` | default | Custom review instructions               |
| `doc-prompt`    | default | Custom documentation instructions        |

---

## 📁 Generated Output

After each PR, the action creates:

```
docs/
├── auto/
│   └── DOCUMENTATION.md   # Auto-generated docs
└── reviews/
    └── PR-123.md          # Detailed review report
```

💬 Plus inline comments directly in the pull request.

---

## 🌍 Supported Languages

| Language                | Extensions                                  |
| ----------------------- | ------------------------------------------- |
| Python                  | `.py`                                       |
| JavaScript / TypeScript | `.js`, `.ts`, `.jsx`, `.tsx`                |
| Go                      | `.go`                                       |
| Java                    | `.java`                                     |
| Rust                    | `.rs`                                       |
| C / C++                 | `.c`, `.cpp`, `.h`                          |
| Other                   | Ruby, PHP, Shell, SQL, HTML/CSS, JSON, YAML |

---

## ❓ FAQ

### Do I need an API key?

No — GitHub Models works for free without any key.

### Is it really free?

Yes. GitHub Models is free (beta). Groq also offers a generous free tier.

### Can I use it in private repositories?

Yes, it works with any repository.

---

## 📄 License

MIT © [egor-zasmuzhets](https://github.com/egor-zasmuzhets)

---

⭐ If you like the project, consider starring it on GitHub:

[![Star on GitHub](https://img.shields.io/github/stars/egor-zasmuzhets/ai-code-docs-action?style=social)](https://github.com/egor-zasmuzhets/ai-code-docs-action)
