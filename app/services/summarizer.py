"""Korean summarization service using LLM APIs"""

from typing import Dict, Optional
import asyncio
import json
import logging
import re
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import google.generativeai as genai
from app.config.settings import settings
from app.crawlers.base import RawArticle

logger = logging.getLogger(__name__)


class LLMQuotaExceeded(Exception):
    """Raised when the LLM provider reports quota exhaustion."""


class SummarizerService:
    """Service to generate Korean summaries using LLM APIs"""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.max_tokens = self._resolve_max_tokens()

        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'")
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        elif self.provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'")
            self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        elif self.provider == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER is 'gemini'")
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Using gemini-1.5-flash for higher free tier limits (1500 RPD vs 20 RPD)
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _resolve_max_tokens(self) -> int:
        requested = getattr(settings, "LLM_MAX_TOKENS", 8000) or 8000
        if not isinstance(requested, int) or requested <= 0:
            logger.warning(f"Invalid LLM_MAX_TOKENS={requested}; defaulting to 8000")
            requested = 8000

        if self.provider == "openai":
            hard_cap = 16384  # gpt-4o-mini max completion tokens
            if requested > hard_cap:
                logger.warning(
                    f"LLM_MAX_TOKENS={requested} exceeds gpt-4o-mini limit {hard_cap}; clamping"
                )
            return min(requested, hard_cap)

        return requested

    async def summarize(self, article: RawArticle) -> Dict[str, str]:
        """
        Generate Korean summary and categorization for an article

        Args:
            article: RawArticle to summarize

        Returns:
            Dictionary with 'title_ko', 'summary_ko', and 'category' keys, or None if failed
        """
        try:
            if self.provider == "openai":
                return await self._summarize_openai(article)
            elif self.provider == "anthropic":
                return await self._summarize_anthropic(article)
            elif self.provider == "gemini":
                return await self._summarize_gemini(article)
        except Exception as e:
            logger.error(f"Failed to summarize article: {e}")
            # Return None to indicate failure - don't save articles without proper summarization
            return None

    async def _summarize_openai(self, article: RawArticle) -> Dict[str, str]:
        """Generate summary using OpenAI GPT"""
        prompt = self._build_prompt(article)

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Use mini for cost savings
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes developer content in Korean."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=self.max_tokens  # Max completion tokens (configurable)
        )

        content = response.choices[0].message.content
        return self._parse_response(content)

    async def _summarize_anthropic(self, article: RawArticle) -> Dict[str, str]:
        """Generate summary using Anthropic Claude"""
        prompt = self._build_prompt(article)

        response = await self.anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",  # Use Haiku for cost savings
            max_tokens=self.max_tokens,  # Max completion tokens (configurable)
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.content[0].text
        return self._parse_response(content)

    async def _summarize_gemini(self, article: RawArticle) -> Dict[str, str]:
        """Generate summary using Google Gemini"""
        prompt = self._build_prompt(article)

        # Gemini API is sync, so we need to run it in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=self.max_tokens,  # Max completion tokens (configurable)
                )
            )
        )

        content = response.text
        return self._parse_response(content)

    def _build_batch_prompt(self, articles: list[RawArticle]) -> str:
        """Build prompt for multiple articles at once"""
        articles_text = ""
        for i, article in enumerate(articles, 1):
            # Use FULL content without truncation
            # Quality over speed - this is background processing
            full_content = article.content or ""
            articles_text += f"""
        Article {i}:
        Title: {article.title_en}
        URL: {article.url}
        Tags: {', '.join(article.tags[:10])}
        Content: {full_content}

        """

            prompt = f"""Summarize and categorize these {len(articles)} developer articles in Korean.

        You have access to the FULL CONTENT of each article. Read carefully and provide comprehensive summaries.

        {articles_text}

        For EACH article, provide a JSON object with:
        1. "url": The article URL (to match it back)
        2. "is_technical": Boolean - Is this article relevant for developers/engineers?
            - TRUE if:
              * Technical content: tutorials, how-to guides, code examples, architecture, APIs,
                databases, algorithms, system design, best practices, performance, debugging, testing
              * Tech opinions: thoughts on frameworks, languages, tools, methodologies, industry practices
              * Tech products/tools: new dev tools, frameworks, libraries, platforms, services
              * Tech startups: companies building developer tools, infrastructure, SaaS for devs
              * Developer experience: career advice, learning resources, productivity tools
            - FALSE if:
              * Pure political news (government surveillance, regulations not affecting devs directly)
              * Non-tech business (general layoffs, funding for non-tech products)
              * Consumer products (iPhone reviews, gadgets unless dev-related)
              * Social issues without tech focus (diversity initiatives, workplace culture)
              * Industry drama without technical merit
            - KEY: Ask "Would a developer building software find this useful or interesting?"
            - Examples of FALSE: "DHS tracks citizen who criticized them" (politics, not dev-related),
              "General tech company layoffs" (unless about specific dev tools company)
            - Examples of TRUE: "Why I switched from React to Vue", "Startup launches new API testing tool",
              "The future of serverless", "Y Combinator-backed dev tools startup raises $5M"
        3. "title_ko": A concise Korean title (max 100 characters) that captures the main topic
        4. "summary_ko": A COMPREHENSIVE Korean summary in MARKDOWN format that:
            - Summarizes the ENTIRE article, not just the introduction
            - Explains the main concepts, techniques, and key takeaways
            - Uses markdown formatting (##, ###, -, **, `, etc.) for better readability
            - Can be as long as needed to fully explain the content (no length limit)
            - Should be detailed enough that readers understand the article without reading the original
            - Include code examples or technical details if present in the original
            - Structure fidelity: Preserve the original section order and hierarchy.
            - Headings: If the article has headings/subtitles, reproduce them in the summary in the same order and level (e.g., ##, ###).
            - Heading text: Keep heading titles as close to the original as possible. If you translate, keep the meaning and structure intact.
            - No re-structuring: Do not regroup or reorder content; follow the article's flow.
        5. "category": One of these categories based on the PRIMARY topic:
        - AI_LLM, DEVOPS_SRE, INFRA_CLOUD, DATABASE, BLOCKCHAIN, SECURITY,
        - DATA_SCIENCE, ARCHITECTURE, MOBILE, FRONTEND, BACKEND, OTHER
        6. "tags": 3-5 short, relevant tags (lowercase, no spaces; use hyphens if needed)

        Return a JSON array with {len(articles)} objects in the SAME ORDER as the articles above.

        Response format (MUST be valid JSON):
        [
        {{
            "url": "...",
            "is_technical": true,
            "title_ko": "...",
            "summary_ko": "## 개요\\n\\n이 글은 Python의 \\"equals\\" 연산자에 대해...\\n\\n### 주요 내용\\n\\n- 첫 번째 포인트\\n- 두 번째 포인트",
            "category": "AI_LLM",
            "tags": ["ai", "ml"]
        }},
        {{
            "url": "...",
            "is_technical": false,
            "title_ko": "...",
            "summary_ko": "정치 뉴스입니다...",
            "category": "OTHER",
            "tags": ["politics", "news"]
        }}
        ]

        IMPORTANT:
        - All newlines in summary_ko MUST be \\n (two characters: backslash + n)
        - All quotes in summary_ko MUST be \\" (backslash + quote)
        - Return ONLY the JSON array, no other text

        NOTE: Use is_technical to filter out non-developer content (politics, consumer news, etc.)
              but keep tech opinions, startup news, and developer-relevant discussions.

        CRITICAL - JSON Formatting:
        - Properly escape all special characters in strings
        - Use \\n for newlines (not literal newlines)
        - Use \\" for quotes inside strings
        - Use \\\\ for backslashes
        - Ensure valid JSON array format"""
        return prompt

    def _build_prompt(self, article: RawArticle) -> str:
        """Build the prompt for single article (legacy, keeping for compatibility)"""
        # Use FULL content without truncation
        full_content = article.content or ""

        prompt = f"""Summarize and categorize this developer article in Korean.

    You have access to the FULL CONTENT. Read carefully and provide a high-quality summary.

    Title: {article.title_en}
    Tags: {', '.join(article.tags[:10])}
    Content: {full_content}

    Provide a JSON response with:
    1. "is_technical": Boolean - Is this article relevant for developers/engineers?
        - TRUE if: technical tutorials, tech opinions, new dev tools/products, tech startups,
          developer experience, career advice, framework/language discussions
        - FALSE if: pure political news, non-tech business news, consumer product reviews,
          social issues without tech focus, industry drama without technical merit
        - KEY: Ask "Would a developer building software find this useful or interesting?"
    2. "title_ko": A concise Korean title (max 100 characters)
    3. "summary_ko": A COMPREHENSIVE Korean summary in MARKDOWN format that:
        - Summarizes the ENTIRE article, not just the introduction
        - Explains the main concepts, techniques, and key takeaways
        - Uses markdown formatting (##, ###, -, **, `, etc.) for better readability
        - Can be as long as needed to fully explain the content (no length limit)
        - Should be detailed enough that readers understand the article without reading the original
        - Include code examples or technical details if present in the original
        - Structure fidelity: Preserve the original section order and hierarchy.
        - Headings: If the article has headings/subtitles, reproduce them in the summary in the same order and level (e.g., ##, ###).
        - Heading text: Keep heading titles as close to the original as possible. If you translate, keep the meaning and structure intact.
        - No re-structuring: Do not regroup or reorder content; follow the article's flow.
    4. "category": One of the following categories that best matches this article:
    - AI_LLM (AI, LLM, GPT, machine learning, deep learning)
    - DEVOPS_SRE (DevOps, SRE, CI/CD, monitoring, kubernetes, docker)
    - INFRA_CLOUD (AWS, Azure, GCP, cloud infrastructure, serverless)
    - DATABASE (SQL, NoSQL, PostgreSQL, MongoDB, database design)
    - BLOCKCHAIN (Blockchain, crypto, Ethereum, Web3, smart contracts)
    - SECURITY (Security, authentication, encryption, vulnerabilities)
    - DATA_SCIENCE (Data science, analytics, visualization, big data)
    - ARCHITECTURE (System architecture, microservices, design patterns)
    - MOBILE (iOS, Android, mobile app development)
    - FRONTEND (React, Vue, Angular, JavaScript, CSS, web frontend)
    - BACKEND (Backend, API, Node.js, Python, Java, server-side)
    - OTHER (anything else that doesn't fit above categories)
    5. "tags": 3-5 short, relevant tags (lowercase, no spaces; use hyphens if needed)

    Response format (MUST be valid JSON):
    {{
    "is_technical": true,
    "title_ko": "...",
    "summary_ko": "## 개요\\n\\n이 글은 Python의 \\"equals\\" 연산자...\\n\\n### 주요 내용\\n\\n- 포인트 1\\n- 포인트 2",
    "category": "AI_LLM",
    "tags": ["tag1", "tag2"]
    }}

    IMPORTANT:
    - All newlines in summary_ko MUST be \\n (backslash + n, not literal newline)
    - All quotes MUST be \\" (backslash + quote)
    - Return ONLY valid JSON, no other text
    """

        return prompt

    def _parse_batch_response(self, content: str, articles: list[RawArticle]) -> list[Dict[str, str]]:
        """Parse LLM batch response into list of structured data"""
        try:
            data_array = self._safe_json_loads(content, expect_array=True)
            if data_array is None:
                logger.error("Failed to parse LLM batch response after all repair attempts")
                logger.error(f"Problematic content (first 1000 chars): {content[:1000]}")
                logger.error(f"Problematic content (last 500 chars): {content[-500:]}")
                return [None] * len(articles)

            # If model returned a single object, wrap it
            if isinstance(data_array, dict):
                data_array = [data_array]

            if not isinstance(data_array, list):
                logger.error("LLM response is not a JSON array")
                return [None] * len(articles)

            # Match responses to articles by URL; if mismatched, fall back to positional order
            # Normalize URLs for matching (strip whitespace and trailing slashes)
            url_to_index = {article.url.strip().rstrip("/"): idx for idx, article in enumerate(articles)}
            results: list[Dict[str, str] | None] = [None] * len(articles)
            unmatched_items = []

            for item in data_array:
                url = (item.get("url") or "").strip().rstrip("/")
                tags = self._clean_tags(item.get("tags"))
                if url in url_to_index:
                    idx = url_to_index[url]
                    results[idx] = {
                        "url": url,
                        "is_technical": item.get("is_technical", False),
                        "title_ko": item.get("title_ko", "")[:100],
                        "summary_ko": item.get("summary_ko", ""),  # No length limit - full markdown summary
                        "category": item.get("category", "OTHER"),
                        "tags": tags,
                    }
                else:
                    item["__clean_tags__"] = tags
                    unmatched_items.append(item)

            # Fill remaining slots in order for unmatched items (LLM sometimes tweaks URLs)
            remaining_indices = [i for i, val in enumerate(results) if val is None]
            for item, idx in zip(unmatched_items, remaining_indices):
                url = (item.get("url") or "").strip()
                tags = item.get("__clean_tags__") or self._clean_tags(item.get("tags"))
                logger.warning(f"Could not match URL from LLM response, assigning by order: {url}")
                results[idx] = {
                    "url": url,
                    "is_technical": item.get("is_technical", False),
                    "title_ko": item.get("title_ko", "")[:100],
                    "summary_ko": item.get("summary_ko", ""),  # No length limit - full markdown summary
                    "category": item.get("category", "OTHER"),
                    "tags": tags,
                }

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM batch response as JSON: {e}")
            logger.error(f"Problematic content (first 1000 chars): {content[:1000]}")
            logger.error(f"Problematic content (last 500 chars): {content[-500:]}")
            # Return None for all articles in this batch
            return [None] * len(articles)
        except Exception as e:
            logger.error(f"Unexpected error parsing batch response: {e}")
            return [None] * len(articles)

    def _parse_response(self, content: str) -> Dict[str, str]:
        """Parse LLM response into structured data (single article)"""
        try:
            data = self._safe_json_loads(content, expect_array=False)
            if data is None:
                logger.error("Failed to parse LLM single-article response after all repair attempts")
                logger.error(f"Failed content: {content[:1000]}")
                return None
            if isinstance(data, list) and data:
                data = data[0]

            return {
                "is_technical": data.get("is_technical", False),
                "title_ko": data.get("title_ko", "")[:100],
                "summary_ko": data.get("summary_ko", ""),  # No length limit - full markdown summary
                "category": data.get("category", "OTHER"),
                "tags": self._clean_tags(data.get("tags"))
            }
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response as JSON: {content}")
            # Return None to indicate failure - don't save articles with failed summarization
            return None

    async def _summarize_batch_llm(self, articles: list[RawArticle]) -> list[Dict[str, str]]:
        """Call LLM once with multiple articles"""
        try:
            prompt = self._build_batch_prompt(articles)

            if self.provider == "openai":
                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes developer content in Korean."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=self.max_tokens  # Max completion tokens (configurable)
                )
                content = response.choices[0].message.content

            elif self.provider == "anthropic":
                response = await self.anthropic_client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=self.max_tokens,  # Max completion tokens (configurable)
                    temperature=0.3,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text

            elif self.provider == "gemini":
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.gemini_model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.3,
                            max_output_tokens=self.max_tokens,  # Max completion tokens (configurable)
                        )
                    )
                )
                content = response.text
                logger.debug(f"Gemini response length: {len(content)} chars")

            return self._parse_batch_response(content, articles)

        except Exception as e:
            if self._is_quota_error(e):
                logger.error(f"LLM quota exceeded: {e}")
                raise LLMQuotaExceeded(str(e))
            logger.error(f"Failed to batch summarize {len(articles)} articles: {e}")
            return [None] * len(articles)

    async def summarize_batch(
        self,
        articles: list[RawArticle],
        batch_size: int = 2,
        delay: float = 5.0
    ) -> list[Dict[str, str]]:
        """
        Summarize multiple articles efficiently by batching them into single LLM requests

        NOTE: Uses FULL article content and generates comprehensive markdown summaries
        Reduced to 2 articles per batch to avoid JSON parsing errors and timeouts

        Args:
            articles: List of RawArticles to summarize
            batch_size: Number of articles per LLM request (default: 2, reduced for stability)
            delay: Delay between LLM requests in seconds (default: 5)

        Returns:
            List of summaries (or None for failed articles)
        """
        summaries = []

        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} articles")

            # Send all articles in batch to LLM in one request
            try:
                batch_summaries = await self._summarize_batch_llm(batch)
            except LLMQuotaExceeded:
                summaries.extend([None] * len(batch))
                remaining = len(articles) - (i + len(batch))
                if remaining > 0:
                    summaries.extend([None] * remaining)
                logger.error("Aborting remaining batches due to LLM quota exhaustion")
                break
            summaries.extend(batch_summaries)

            # Delay between batches to respect rate limits
            if i + batch_size < len(articles):
                await asyncio.sleep(delay)

        return summaries

    @staticmethod
    def _fix_json_string(json_str: str) -> str:
        """
        Fix literal newlines and unescaped quotes in JSON string values

        The LLM sometimes generates JSON with:
        1. Literal newlines instead of \\n
        2. Unescaped quotes within string values
        This function uses a state machine to properly escape them
        """
        result = []
        in_string = False
        in_value = False  # True if we're in a string value (after a colon), not a key
        escape_next = False
        i = 0

        while i < len(json_str):
            char = json_str[i]

            # Handle escape sequences
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue

            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue

            # Handle quote characters
            if char == '"':
                # If we're in a value string, check if this quote ends the string or should be escaped
                if in_string and in_value:
                    # Look ahead to see what follows this quote
                    # Skip whitespace
                    j = i + 1
                    while j < len(json_str) and json_str[j] in ' \t\n\r':
                        j += 1

                    # If followed by comma, closing brace, or closing bracket, it's the end of the string
                    if j < len(json_str) and json_str[j] in ',}]':
                        # This is the closing quote
                        result.append(char)
                        in_string = False
                        in_value = False
                    else:
                        # This is an unescaped quote within the content - escape it
                        result.append('\\')
                        result.append(char)
                    i += 1
                    continue

                # Regular quote handling (entering/exiting strings for keys)
                result.append(char)
                if in_string:
                    # Exiting a string
                    in_string = False
                    in_value = False
                else:
                    # Entering a string - determine if it's a key or value
                    # Look backwards to see if we're after a colon (value) or not (key)
                    # Find the last non-whitespace character
                    j = len(result) - 2
                    while j >= 0 and result[j] in ' \t\n\r':
                        j -= 1

                    in_string = True
                    in_value = (j >= 0 and result[j] == ':')

                i += 1
                continue

            # If we're in a value string, escape literal newlines
            if in_string and in_value:
                if char == '\n':
                    result.append('\\n')
                    i += 1
                    continue
                elif char == '\r':
                    result.append('\\r')
                    i += 1
                    continue
                elif char == '\t':
                    result.append('\\t')
                    i += 1
                    continue

            result.append(char)
            i += 1

        fixed = ''.join(result)
        if fixed != json_str:
            logger.debug("JSON string fixed - escaped literal newlines and unescaped quotes in values")
        return fixed

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove wrapping markdown code fences if present."""
        text = text.strip()
        if text.startswith("```"):
            text = text[3:]
            if text.startswith("json"):
                text = text[4:]
            if "```" in text:
                text = text.split("```")[0]
        return text.strip()

    @staticmethod
    def _extract_json_payload(text: str, expect_array: bool) -> str:
        """Extract the JSON array/object substring if response includes extra text."""
        text = text.strip()
        if expect_array:
            start = text.find("[")
            if start == -1:
                return text
            end = SummarizerService._find_matching_bracket(text, start, "[", "]")
        else:
            start = text.find("{")
            if start == -1:
                return text
            end = SummarizerService._find_matching_bracket(text, start, "{", "}")
        if end != -1 and end > start:
            return text[start:end + 1]
        # If no matching end, return from start to allow repair attempts
        return text[start:]

    @staticmethod
    def _find_matching_bracket(text: str, start: int, open_char: str, close_char: str) -> int:
        """Find matching closing bracket for a JSON array/object, ignoring brackets in strings."""
        in_string = False
        escape_next = False
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return i
        return -1

    @staticmethod
    def _remove_trailing_commas(text: str) -> str:
        """Remove trailing commas before closing braces/brackets."""
        return re.sub(r",\s*([}\]])", r"\1", text)

    @staticmethod
    def _close_unterminated_json(text: str, expect_array: bool) -> str:
        """
        Close unterminated strings and brackets/braces to salvage truncated JSON.
        """
        s = text.strip()
        if expect_array and not s.lstrip().startswith("["):
            # If it looks like a single object, wrap it in an array
            if "{" in s:
                s = "[" + s
            else:
                s = "[" + s

        in_string = False
        escape_next = False
        stack: list[str] = []

        for ch in s:
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()

        if in_string:
            s += '"'

        while stack:
            opener = stack.pop()
            s += "}" if opener == "{" else "]"

        if expect_array and not s.rstrip().endswith("]"):
            s += "]"
        return s

    @staticmethod
    def _trim_to_last_complete_object(text: str) -> Optional[str]:
        """
        Trim JSON array to the last complete top-level object.
        Useful when output is truncated mid-object.
        """
        s = text.strip()
        in_string = False
        escape_next = False
        bracket_depth = 0
        brace_depth = 0
        last_obj_end = None

        for i, ch in enumerate(s):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                bracket_depth += 1
            elif ch == "]":
                bracket_depth = max(0, bracket_depth - 1)
            elif ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth = max(0, brace_depth - 1)
                if brace_depth == 0 and bracket_depth >= 1:
                    last_obj_end = i

        if last_obj_end is None:
            return None

        start = s.find("[")
        if start == -1:
            return None
        trimmed = s[start:last_obj_end + 1]
        return trimmed + "]"

    def _safe_json_loads(self, content: str, expect_array: bool):
        """Best-effort JSON parsing with multiple repair attempts."""
        original = content
        content = self._strip_code_fences(content)
        content = self._extract_json_payload(content, expect_array=expect_array)

        candidates: list[tuple[str, str]] = []

        # If we expect an array but got a single object, try wrapping
        if expect_array:
            stripped = content.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                candidates.append(("wrapped_single_object", f"[{content}]"))

        candidates.append(("raw", content))
        candidates.append(("fixed_strings", self._fix_json_string(content)))

        for label, candidate in candidates:
            candidate = self._remove_trailing_commas(candidate)
            try:
                data = json.loads(candidate)
                if label != "raw":
                    logger.info(f"Parsed JSON after repair: {label}")
                return data
            except json.JSONDecodeError as e:
                if label == "raw":
                    logger.warning(f"Initial JSON parse failed at line {e.lineno}, col {e.colno}: {e.msg}")
                    logger.debug(f"Error context: {candidate[max(0, e.pos-100):e.pos+100]}")
                continue

        # Attempt to close unterminated JSON (truncation)
        repaired = self._close_unterminated_json(self._fix_json_string(content), expect_array=expect_array)
        repaired = self._remove_trailing_commas(repaired)
        try:
            data = json.loads(repaired)
            logger.info("Parsed JSON after closing unterminated structures")
            return data
        except json.JSONDecodeError:
            pass

        # Final attempt: trim to last complete object
        if expect_array:
            trimmed = self._trim_to_last_complete_object(repaired)
            if trimmed:
                trimmed = self._remove_trailing_commas(trimmed)
                try:
                    data = json.loads(trimmed)
                    logger.warning("Parsed JSON by trimming to last complete object (truncated output)")
                    return data
                except json.JSONDecodeError:
                    pass

        logger.error("All JSON repair attempts failed")
        logger.error(f"Raw content length: {len(original)} chars")
        return None

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "quota" in msg and "exceed" in msg

    @staticmethod
    def _clean_tags(tags) -> list[str]:
        """Normalize tags list to <=5 lowercase strings without spaces."""
        if not tags:
            return []
        if isinstance(tags, str):
            tags = [tags]
        cleaned = []
        for t in tags:
            if not isinstance(t, str):
                continue
            tag = t.strip().lower().replace(" ", "-")
            if tag:
                cleaned.append(tag)
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for tag in cleaned:
            if tag in seen:
                continue
            seen.add(tag)
            deduped.append(tag)
        return deduped[:5]
