# AI Code Docs & Reviewer

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-AI%20Code%20Reviewer-blue)](https://github.com/marketplace/ai-code-docs-reviewer)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Automated code documentation and review powered by Groq's Llama 3.3 70B.

## ✨ Features

- 🐍 **Multi-language support** — Python, JavaScript, TypeScript, Go, Java, Rust, and more
- 💬 **Inline comments** — Issues are commented directly on the relevant lines of code
- 📝 **Custom prompts** — Tailor the analysis to your project's needs
- 🎯 **Exclude patterns** — Skip tests, generated code, or specific folders
- 📚 **Auto-documentation** — Generates/updates documentation for changed files
- 🚀 **Fast** — Uses Groq API for sub-10 second responses

## 🚀 Quick Start

Add this to `.github/workflows/ai-review.yml`:

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
        with:
          api-key: ${{ secrets.GROQ_API_KEY }}