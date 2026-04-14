"""
Factory for creating LLM clients from different providers.
Supports automatic fallback: Groq if API key provided, otherwise GitHub Models.
"""

import os
import json
import httpx
from typing import Dict, Any, Optional


class BaseLLMClient:
    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        raise NotImplementedError


class GitHubModelsClient(BaseLLMClient):
    def __init__(self, token: str, model: str = "gpt-4o-mini",
                 review_prompt: Optional[str] = None,
                 doc_prompt: Optional[str] = None):
        self.token = token
        self.model = model
        self.base_url = "https://models.inference.ai.azure.com/chat/completions"
        self.custom_review_prompt = review_prompt
        self.custom_doc_prompt = doc_prompt

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        prompt = self._build_prompt(code, language)
        response = self._call_api(prompt)
        return self._parse_response(response)

    def _build_prompt(self, code: str, language: str) -> str:
        if self.custom_review_prompt and self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```" + language + "\n" + code + "\n```\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON in this format:\n{\n  \"documentation\": { ... },\n  \"review\": { ... }\n}"
        if self.custom_review_prompt:
            return self._default_doc_prompt(code, language) + "\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON in this format:\n{\n  \"documentation\": { ... },\n  \"review\": { ... }\n}"
        if self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```" + language + "\n" + code + "\n```\n\n" + self._default_review_prompt() + "\n\nReturn ONLY valid JSON in this format:\n{\n  \"documentation\": { ... },\n  \"review\": { ... }\n}"
        return self._default_prompt(code, language)

    def _default_doc_prompt(self, code: str, language: str) -> str:
        return (
            "You are a code documentation expert.\n\n"
            "Generate documentation for the following " + language + " code.\n\n"
            "Focus on:\n"
            "- What the code does (business purpose)\n"
            "- Main functions and their parameters\n"
            "- Classes and their responsibilities\n"
            "- External dependencies\n\n"
            "Code:\n```" + language + "\n" + code + "\n```"
        )

    def _default_review_prompt(self) -> str:
        return (
            "You are a code review expert.\n\n"
            "Find issues in the code and return them in JSON format.\n\n"
            "Focus on:\n"
            "- Security vulnerabilities (SQL injection, XSS, etc.)\n"
            "- Performance problems\n"
            "- Potential bugs\n"
            "- Best practices violations\n\n"
            "For each issue, provide:\n"
            "- severity (high/medium/low)\n"
            "- type (security/performance/style/bug)\n"
            "- line number (if you can determine it)\n"
            "- description of the problem\n"
            "- suggestion for fixing it"
        )

    def _default_prompt(self, code: str, language: str) -> str:
        return (
            "You are a code documentation and review expert.\n\n"
            "Analyze the following " + language + " code and return TWO things in JSON format:\n\n"
            "1. Documentation: Describe what this code does, its functions, classes, and dependencies\n"
            "2. Code Review: Find issues (security, performance, style, bugs)\n\n"
            "Code:\n```" + language + "\n" + code + "\n```\n\n"
            "Return ONLY valid JSON in this exact format:\n"
            "{\n"
            '  "documentation": {\n'
            '    "description": "Brief description of what this code does",\n'
            '    "functions": ["list of function names"],\n'
            '    "classes": ["list of class names"],\n'
            '    "dependencies": ["list of imported libraries"]\n'
            "  },\n"
            '  "review": {\n'
            '    "issues": [\n'
            "      {\n"
            '        "severity": "high|medium|low",\n'
            '        "type": "security|performance|style|bug",\n'
            '        "line": 0,\n'
            '        "description": "What is the problem",\n'
            '        "suggestion": "How to fix it"\n'
            "      }\n"
            "    ],\n"
            '    "overall_score": 1-10,\n'
            '    "summary": "Brief summary of code quality"\n'
            "  }\n"
            "}"
        )

    def _call_api(self, prompt: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"⚠️ GitHub Models API error: {e}")
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
            return json.loads(content.strip())
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


class GroqClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile",
                 review_prompt: Optional[str] = None,
                 doc_prompt: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.custom_review_prompt = review_prompt
        self.custom_doc_prompt = doc_prompt

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        prompt = self._build_prompt(code, language)
        response = self._call_api(prompt)
        return self._parse_response(response)

    def _build_prompt(self, code: str, language: str) -> str:
        if self.custom_review_prompt and self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```" + language + "\n" + code + "\n```\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON in this format:\n{\n  \"documentation\": { ... },\n  \"review\": { ... }\n}"
        if self.custom_review_prompt:
            return self._default_doc_prompt(code, language) + "\n\n" + self.custom_review_prompt + "\n\nReturn ONLY valid JSON in this format:\n{\n  \"documentation\": { ... },\n  \"review\": { ... }\n}"
        if self.custom_doc_prompt:
            return self.custom_doc_prompt + "\n\nCode:\n```" + language + "\n" + code + "\n```\n\n" + self._default_review_prompt() + "\n\nReturn ONLY valid JSON in this format:\n{\n  \"documentation\": { ... },\n  \"review\": { ... }\n}"
        return self._default_prompt(code, language)

    def _default_doc_prompt(self, code: str, language: str) -> str:
        return (
            "You are a code documentation expert.\n\n"
            "Generate documentation for the following " + language + " code.\n\n"
            "Focus on:\n"
            "- What the code does (business purpose)\n"
            "- Main functions and their parameters\n"
            "- Classes and their responsibilities\n"
            "- External dependencies\n\n"
            "Code:\n```" + language + "\n" + code + "\n```"
        )

    def _default_review_prompt(self) -> str:
        return (
            "You are a code review expert.\n\n"
            "Find issues in the code and return them in JSON format.\n\n"
            "Focus on:\n"
            "- Security vulnerabilities (SQL injection, XSS, etc.)\n"
            "- Performance problems\n"
            "- Potential bugs\n"
            "- Best practices violations\n\n"
            "For each issue, provide:\n"
            "- severity (high/medium/low)\n"
            "- type (security/performance/style/bug)\n"
            "- line number (if you can determine it)\n"
            "- description of the problem\n"
            "- suggestion for fixing it"
        )

    def _default_prompt(self, code: str, language: str) -> str:
        return (
            "You are a code documentation and review expert.\n\n"
            "Analyze the following " + language + " code and return TWO things in JSON format:\n\n"
            "1. Documentation: Describe what this code does, its functions, classes, and dependencies\n"
            "2. Code Review: Find issues (security, performance, style, bugs)\n\n"
            "Code:\n\\`\\`\\`" + language + "\n" + code + "\n\\`\\`\\`\n\n"
            "Return ONLY valid JSON in this exact format:\n"
            "{\n"
            '  "documentation": {\n'
            '    "description": "Brief description of what this code does",\n'
            '    "functions": ["list of function names"],\n'
            '    "classes": ["list of class names"],\n'
            '    "dependencies": ["list of imported libraries"]\n'
            "  },\n"
            '  "review": {\n'
            '    "issues": [\n'
            "      {\n"
            '        "severity": "high|medium|low",\n'
            '        "type": "security|performance|style|bug",\n'
            '        "line": 0,\n'
            '        "description": "What is the problem",\n'
            '        "suggestion": "How to fix it"\n'
            "      }\n"
            "    ],\n"
            '    "overall_score": 1-10,\n'
            '    "summary": "Brief summary of code quality"\n'
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
            with httpx.Client(timeout=60.0) as client:
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
            return json.loads(content.strip())
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


def get_llm_client(provider: str = "auto",
                   groq_api_key: Optional[str] = None,
                   github_token: Optional[str] = None,
                   model: str = "",
                   review_prompt: Optional[str] = None,
                   doc_prompt: Optional[str] = None) -> BaseLLMClient:
    default_models = {
        "groq": "llama-3.3-70b-versatile",
        "github-models": "gpt-4o-mini"
    }

    if provider == "auto":
        if groq_api_key:
            provider = "groq"
            print("🔍 Auto-selected: Groq (API key provided)")
        elif github_token:
            provider = "github-models"
            print("🔍 Auto-selected: GitHub Models (using GITHUB_TOKEN)")
        else:
            raise ValueError(
                "No LLM provider available. Please either:\n"
                "1. Provide GROQ_API_KEY, or\n"
                "2. Ensure GITHUB_TOKEN is available (GitHub Models)"
            )

    if not model:
        model = default_models.get(provider, "gpt-4o-mini")

    if provider == "groq":
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY required for provider='groq'")
        print(f"🚀 Using Groq with model: {model}")
        return GroqClient(groq_api_key, model, review_prompt, doc_prompt)

    elif provider == "github-models":
        if not github_token:
            raise ValueError("GITHUB_TOKEN required for provider='github-models'")
        print(f"🚀 Using GitHub Models with model: {model}")
        return GitHubModelsClient(github_token, model, review_prompt, doc_prompt)

    else:
        raise ValueError(f"Unknown provider: {provider}")