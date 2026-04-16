"""
Groq API client for the AI Code Reviewer Action.
"""

import os
import json
import httpx
from typing import Dict, Any, Optional


class GroqClient:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile",
                 review_prompt: Optional[str] = None,
                 doc_prompt: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.custom_review_prompt = review_prompt
        self.custom_doc_prompt = doc_prompt

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Send code to Groq for analysis with line numbers."""
        numbered_code = self._add_line_numbers(code)
        prompt = self._build_prompt(numbered_code, language)
        response = self._call_api(prompt)
        return self._parse_response(response)

    def _add_line_numbers(self, code: str) -> str:
        """Add line numbers to code for reference."""
        lines = code.split('\n')
        numbered = '\n'.join([f"{i+1:4d} | {line}" for i, line in enumerate(lines)])
        return numbered

    def _build_prompt(self, numbered_code: str, language: str) -> str:
        """Build prompt with numbered code."""
        if self.custom_review_prompt and self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```\n" + numbered_code + "\n```\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON."

        if self.custom_review_prompt:
            return self._default_doc_prompt() + "\n\nCode:\n```\n" + numbered_code + "\n```\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON."

        if self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```\n" + numbered_code + "\n```\n\n" + self._default_review_prompt() + "\n\nReturn ONLY valid JSON."

        return self._default_prompt(numbered_code, language)

    def _default_doc_prompt(self) -> str:
        return (
            "You are a code documentation expert.\n\n"
            "Generate documentation for the code below.\n\n"
            "Focus on:\n"
            "- What the code does (business purpose)\n"
            "- Main functions and their parameters\n"
            "- Classes and their responsibilities\n"
            "- External dependencies"
        )

    def _default_review_prompt(self) -> str:
        return (
            "You are a code review expert.\n\n"
            "Find issues in the code and return them in JSON format.\n\n"
            "For each issue, identify the EXACT line number from the numbered code.\n"
            "Also include a short code snippet (1-2 lines) showing the problematic code.\n\n"
            "Focus on:\n"
            "- Security vulnerabilities\n"
            "- Performance problems\n"
            "- Potential bugs\n"
            "- Best practices violations"
        )

    def _default_prompt(self, numbered_code: str, language: str) -> str:
        return (
            "You are a code documentation and review expert.\n\n"
            "Analyze the following " + language + " code and return TWO things in JSON format:\n\n"
            "1. Documentation: Describe what this code does, its functions, classes, and dependencies\n"
            "2. Code Review: Find issues (security, performance, style, bugs)\n\n"
            "IMPORTANT:\n"
            "- The code has LINE NUMBERS in the format ' N | code'\n"
            "- For each issue, specify the EXACT line number where the problem occurs\n"
            "- Also include a short code snippet (the line itself) as 'code_snippet'\n\n"
            "Code with line numbers:\n"
            "```\n" + numbered_code + "\n```\n\n"
            "Return ONLY valid JSON in this exact format:\n"
            "{\n"
            '  "documentation": {\n'
            '    "description": "...",\n'
            '    "functions": ["..."],\n'
            '    "classes": ["..."],\n'
            '    "dependencies": ["..."]\n'
            "  },\n"
            '  "review": {\n'
            '    "issues": [\n'
            "      {\n"
            '        "severity": "high|medium|low",\n'
            '        "type": "security|performance|style|bug",\n'
            '        "line": 42,\n'
            '        "code_snippet": "def divide(a, b): return a / b",\n'
            '        "description": "...",\n'
            '        "suggestion": "..."\n'
            "      }\n"
            "    ],\n"
            '    "overall_score": 7,\n'
            '    "summary": "..."\n'
            "  }\n"
            "}"
        )

    def _call_api(self, prompt: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"⚠️ Groq API error: {e}")
            return self._get_fallback_response()

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        try:
            content = response["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            result = json.loads(content.strip())

            # Ensure each issue has required fields
            if "review" in result and "issues" in result["review"]:
                for issue in result["review"]["issues"]:
                    if "line" not in issue:
                        issue["line"] = 0
                    if "code_snippet" not in issue:
                        issue["code_snippet"] = ""

            return result
        except Exception as e:
            print(f"⚠️ Failed to parse response: {e}")
            return self._get_fallback_response()

    def _get_fallback_response(self) -> Dict[str, Any]:
        return {
            "documentation": {
                "description": "Unable to analyze code (API error)",
                "functions": [],
                "classes": [],
                "dependencies": []
            },
            "review": {
                "issues": [],
                "overall_score": 5,
                "summary": "Analysis failed due to API error"
            }
        }