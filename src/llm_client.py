"""
Groq API client for the AI Code Reviewer Action.

This module provides a client for interacting with Groq's LLM API.
Features:
- Adds line numbers to code for precise issue location
- Supports custom review and documentation prompts
- Handles API errors gracefully with fallback responses
- Parses JSON responses and ensures required fields exist
"""

import os
import json
import httpx
from typing import Dict, Any, Optional


class GroqClient:
    """
    Client for Groq's LLM API (Llama 3.3 70B).

    This client handles:
    - Building prompts with optional custom overrides
    - Adding line numbers to code for accurate issue tracking
    - Making HTTP requests to Groq API
    - Parsing JSON responses and validating required fields
    - Graceful fallback on API errors

    Attributes:
        api_key (str): Groq API key (starts with 'gsk_')
        model (str): Model name (default: "llama-3.3-70b-versatile")
        base_url (str): Groq API endpoint
        custom_review_prompt (Optional[str]): User-provided review instructions
        custom_doc_prompt (Optional[str]): User-provided documentation instructions
    """

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile",
                 review_prompt: Optional[str] = None,
                 doc_prompt: Optional[str] = None):
        """
        Initializes the Groq API client.

        Args:
            api_key (str): Groq API key (get from https://console.groq.com)
            model (str, optional): Model name. Defaults to "llama-3.3-70b-versatile"
            review_prompt (Optional[str], optional): Custom prompt for code review
            doc_prompt (Optional[str], optional): Custom prompt for documentation
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.custom_review_prompt = review_prompt
        self.custom_doc_prompt = doc_prompt

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Sends code to Groq for analysis with line numbers.

        This is the main entry point for code analysis. It:
        1. Adds line numbers to the code for precise issue location
        2. Builds an appropriate prompt (custom or default)
        3. Sends the prompt to Groq API
        4. Parses and validates the JSON response

        Args:
            code (str): Source code to analyze
            language (str, optional): Programming language. Defaults to "python"

        Returns:
            Dict[str, Any]: Parsed response containing:
                - documentation: dict with description, functions, classes, dependencies
                - review: dict with issues, overall_score, summary

        Note:
            The code is sent with line numbers in format "N | code" to help
            the model identify exact issue locations.
        """
        numbered_code = self._add_line_numbers(code)
        prompt = self._build_prompt(numbered_code, language)
        response = self._call_api(prompt)
        return self._parse_response(response)

    def _add_line_numbers(self, code: str) -> str:
        """
        Adds line numbers to code for reference.

        Formats each line as "    N | code" where N is the line number (1-indexed).
        This helps the LLM return precise line numbers for issues.

        Args:
            code (str): Source code without line numbers

        Returns:
            str: Code with line numbers prefixed

        Example:
            >>> _add_line_numbers("def add(a,b):\\n    return a+b")
            '   1 | def add(a,b):\\n   2 |     return a+b'
        """
        lines = code.split('\n')
        numbered = '\n'.join([f"{i+1:4d} | {line}" for i, line in enumerate(lines)])
        return numbered

    def _build_prompt(self, numbered_code: str, language: str) -> str:
        """
        Builds the prompt for the LLM with optional custom overrides.

        Priority order:
        1. Both custom prompts → combine them
        2. Only review prompt → use custom review + default doc
        3. Only doc prompt → use custom doc + default review
        4. Neither → use default combined prompt

        Args:
            numbered_code (str): Code with line numbers
            language (str): Programming language

        Returns:
            str: Complete prompt ready for API call
        """
        if self.custom_review_prompt and self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```\n" + numbered_code + "\n```\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON."

        if self.custom_review_prompt:
            return self._default_doc_prompt() + "\n\nCode:\n```\n" + numbered_code + "\n```\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON."

        if self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```\n" + numbered_code + "\n```\n\n" + self._default_review_prompt() + "\n\nReturn ONLY valid JSON."

        return self._default_prompt(numbered_code, language)

    def _default_doc_prompt(self) -> str:
        """
        Returns the default prompt for documentation generation.

        Focuses on:
        - Business purpose of the code
        - Main functions and their parameters
        - Classes and their responsibilities
        - External dependencies

        Returns:
            str: Default documentation prompt
        """
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
        """
        Returns the default prompt for code review.

        Focuses on:
        - Security vulnerabilities
        - Performance problems
        - Potential bugs
        - Best practices violations

        Also requests line numbers and code snippets for each issue.

        Returns:
            str: Default code review prompt
        """
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
        """
        Returns the default combined prompt for both documentation and review.

        This is the most comprehensive prompt that asks the LLM to:
        1. Generate documentation (description, functions, classes, dependencies)
        2. Perform code review (issues with severity, line numbers, snippets)

        Args:
            numbered_code (str): Code with line numbers
            language (str): Programming language

        Returns:
            str: Combined default prompt
        """
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
        """
        Makes the HTTP request to Groq API.

        Args:
            prompt (str): Complete prompt to send to the LLM

        Returns:
            Dict[str, Any]: Raw JSON response from Groq API

        Note:
            Timeout is set to 90 seconds to handle large files.
            Uses JSON response format to ensure structured output.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # Low temperature for consistent, predictable output
            "response_format": {"type": "json_object"}  # Force JSON output
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
        """
        Parses the LLM response and ensures required fields exist.

        Args:
            response (Dict[str, Any]): Raw response from Groq API

        Returns:
            Dict[str, Any]: Parsed response with guaranteed structure

        Note:
            Strips markdown code blocks (```json ... ```) from the response.
            Ensures every issue has 'line' and 'code_snippet' fields.
        """
        try:
            content = response["choices"][0]["message"]["content"]
            content = content.strip()
            # Strip markdown code blocks if present
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
        """
        Returns a safe fallback response when the API call fails.

        This ensures the Action can continue even if the LLM is unavailable.

        Returns:
            Dict[str, Any]: Fallback response with empty documentation and no issues
        """
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