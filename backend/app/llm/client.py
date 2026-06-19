import json
import logging
import time
from abc import ABC, abstractmethod

from openai import OpenAI

from app.config import settings
from app.llm.prompts import (
    DRAFT_EMAIL_SYSTEM_PROMPT,
    DRAFT_EMAIL_USER_TEMPLATE,
    EXTRACTION_SYSTEM_PROMPT,
)
from app.logging_config import StepTimer, log_event

logger = logging.getLogger("app.llm")

MAX_RETRIES = 3
BACKOFF_BASE = 1.0


class BaseLLMClient(ABC):
    @abstractmethod
    def extract(self, text: str) -> dict:
        """Extract structured data from text. Returns raw dict."""

    @abstractmethod
    def draft_email(
        self, action_type: str, merchant: str, context: str, tone: str = "professional"
    ) -> dict:
        """Generate an email draft. Returns dict with 'subject' and 'body'."""


class OpenAILLMClient(BaseLLMClient):
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def _call_with_retry(
        self, messages: list[dict], temperature: float, purpose: str
    ) -> dict:
        last_error = None
        input_chars = sum(len(m.get("content", "")) for m in messages)

        for attempt in range(MAX_RETRIES):
            with StepTimer() as timer:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=temperature,
                    )
                except Exception as e:
                    last_error = e
                    log_event(logger, logging.WARNING, "llm_call_failed",
                              purpose=purpose,
                              model=self.model,
                              attempt=attempt + 1,
                              max_retries=MAX_RETRIES,
                              error=str(e),
                              input_chars=input_chars)
                    if attempt < MAX_RETRIES - 1:
                        wait = BACKOFF_BASE * (2 ** attempt)
                        time.sleep(wait)
                        continue
                    else:
                        log_event(logger, logging.ERROR, "llm_call_exhausted",
                                  purpose=purpose,
                                  model=self.model,
                                  total_attempts=MAX_RETRIES,
                                  error=str(e))
                        raise last_error
                    continue

            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            content = response.choices[0].message.content
            output_chars = len(content) if content else 0

            log_event(logger, logging.INFO, "llm_call_success",
                      purpose=purpose,
                      model=self.model,
                      attempt=attempt + 1,
                      temperature=temperature,
                      input_chars=input_chars,
                      output_chars=output_chars,
                      prompt_tokens=prompt_tokens,
                      completion_tokens=completion_tokens,
                      total_tokens=total_tokens,
                      elapsed_ms=timer.elapsed_ms)

            return json.loads(content)

        raise last_error

    def extract(self, text: str) -> dict:
        return self._call_with_retry(
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            purpose="extraction",
        )

    def draft_email(
        self, action_type: str, merchant: str, context: str, tone: str = "professional"
    ) -> dict:
        user_msg = DRAFT_EMAIL_USER_TEMPLATE.format(
            action_type=action_type, merchant=merchant, context=context, tone=tone
        )
        return self._call_with_retry(
            messages=[
                {"role": "system", "content": DRAFT_EMAIL_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.4,
            purpose="email_draft",
        )


def get_llm_client() -> BaseLLMClient:
    if settings.use_mock_llm:
        from app.llm.mock import MockLLMClient
        log_event(logger, logging.INFO, "llm_client_init", mode="mock")
        return MockLLMClient()
    log_event(logger, logging.INFO, "llm_client_init", mode="openai", model=settings.openai_model)
    return OpenAILLMClient()
