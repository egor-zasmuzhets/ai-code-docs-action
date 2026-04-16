# AI Code Docs & Reviewer

GitHub Action that automatically generates documentation and code review for code in Pull Requests using Groq LLM.

## Features

- 🔍 **Code review** — Security, performance, style, and bug detection
- 📝 **Auto-documentation** — Generates and updates docs automatically
- 💬 **Inline comments** — Issues commented directly on lines of code
- 🌍 **Multi-language** — Python, JavaScript, TypeScript, Go, Java, Rust, and more
- 🎯 **Exclude patterns** — Skip tests, generated code, or folders
- 📊 **Line numbers & code snippets** — Shows exact location of issues

## Quick Start

### 1. Get a free API key

Register at [console.groq.com](https://console.groq.com) and create an API key.

### 2. Add the key to your repository

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`
- **Name:** `GROQ_API_KEY`
- **Secret:** your API key

### 3. Add workflow to your repository

Create `.github/workflows/ai-review.yml`:

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
```

That's it! Create a PR and the Action will run automatically.

## Configuration

```yaml
- uses: egor-zasmuzhets/ai-code-docs-action@v1
  with:
    api-key: ${{ secrets.GROQ_API_KEY }}
    model: "llama-3.3-70b-versatile"     # Optional
    exclude: "tests/**,**/*_test.py"      # Optional
    review-prompt: "Focus on security"    # Optional
    doc-prompt: "Write for beginners"     # Optional
```

### Inputs

| Input | Default | Description |
|-------|---------|-------------|
| `api-key` | (required) | Groq API key |
| `model` | `llama-3.3-70b-versatile` | Groq model to use |
| `exclude` | (empty) | Comma-separated glob patterns |
| `review-prompt` | (default) | Custom review instructions |
| `doc-prompt` | (default) | Custom documentation instructions |
| `doc-output-path` | `docs/auto/DOCUMENTATION.md` | Documentation file path |
| `review-output-path` | `docs/reviews/` | Review reports folder |

## What Gets Generated

After each PR, the Action creates:

```
docs/
├── auto/
│   └── DOCUMENTATION.md    # Auto-generated documentation
└── reviews/
    └── PR-123.md            # Detailed review report with line numbers
```

Plus inline comments in the PR itself.

## Example Output

### Inline comment in PR:

```markdown
**🔴 HIGH** - bug

**Issue:** Division by zero possible when b=0

**Code:**
```python
def divide(a, b): return a / b
```

**Suggestion:** Add check: if b == 0: raise ValueError('Cannot divide by zero')
```

### Review report entry:

```markdown
### 🔴 BUG (line 42)

| Property | Value |
|----------|-------|
| **File** | `titanic.py` |
| **Code** | `def divide(a, b): return a / b` |
| **Description** | Division by zero possible |
| **Suggestion** | Add check for zero |
```

## Supported Languages

| Language | Extensions |
|----------|------------|
| Python | `.py` |
| JavaScript/TypeScript | `.js`, `.ts`, `.jsx`, `.tsx` |
| Go | `.go` |
| Java | `.java` |
| Rust | `.rs` |
| C/C++ | `.c`, `.cpp`, `.h` |
| Ruby | `.rb` |
| PHP | `.php` |
| Shell | `.sh`, `.bash` |
| SQL | `.sql` |
| HTML/CSS | `.html`, `.css`, `.scss` |
| Config | `.json`, `.yaml`, `.yml` |

## FAQ

**Is it free?** Yes. Groq has a generous free tier: 30 requests per minute, 14,400 per day.

**Will it analyze its own files?** No. `docs/auto/` and `docs/reviews/` are automatically ignored.

**Can I use it in private repositories?** Yes. Works with any repository.

## Development

```bash
git clone https://github.com/egor-zasmuzhets/ai-code-docs-action.git
cd ai-code-docs-action
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file with:
# GROQ_API_KEY=your_key
# GITHUB_TOKEN=your_token
# GITHUB_REPOSITORY=owner/repo
# GITHUB_PR_NUMBER=123

python src/main.py
```

## License

MIT © egor-zasmuzhets
```