"""
LLM Client for Groq API.
Handles sending code to LLM and parsing responses.
"""

import os
import json
import httpx
from typing import Dict, Any


class GroqClient:
    """Client for Groq API (Llama 3.3 70B)"""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Send code to LLM for documentation and review."""
        prompt = self._build_prompt(code, language)
        response = self._call_api(prompt)
        return self._parse_response(response)

    def _build_prompt(self, code: str, language: str) -> str:
        """Build prompt for the LLM with escaped backticks"""
        return f"""You are a code documentation and review expert.

Analyze the following {language} code and return TWO things in JSON format:

1. Documentation: Describe what this code does, its functions, classes, and dependencies
2. Code Review: Find issues (security, performance, style, bugs)

Code:
\\`\\`\\`{language}
{code}
\\`\\`\\`

Return ONLY valid JSON in this exact format:
{{
  "documentation": {{
    "description": "Brief description of what this code does",
    "functions": ["list of function names"],
    "classes": ["list of class names"],
    "dependencies": ["list of imported libraries"]
  }},
  "review": {{
    "issues": [
      {{
        "severity": "high|medium|low",
        "type": "security|performance|style|bug",
        "description": "What is the problem",
        "suggestion": "How to fix it"
      }}
    ],
    "overall_score": 1-10,
    "summary": "Brief summary of code quality"
  }}
}}"""

    def _call_api(self, prompt: str) -> Dict[str, Any]:
        """Make API call to Groq"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            print("⚠️ Groq API timeout")
            return self._get_fallback_response()
        except Exception as e:
            print(f"⚠️ Groq API error: {e}")
            return self._get_fallback_response()

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response, extract JSON"""
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
        except (KeyError, json.JSONDecodeError) as e:
            print(f"⚠️ Failed to parse LLM response: {e}")
            return self._get_fallback_response()

    def _get_fallback_response(self) -> Dict[str, Any]:
        """Return safe fallback when API fails"""
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


# For local testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ GROQ_API_KEY not found in .env")
        exit(1)

    client = GroqClient(api_key)

    test_code = """
def divide(a, b):
    return a / b
"""

    result = client.analyze_code(test_code)
    print(json.dumps(result, indent=2))