"""
V.I.E.R.N.E.S Tier-2 Semantic LLM Classifier
Connects to LLM endpoints to perform structured triage, action extraction, and draft generation.
"""

import json
import logging
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None

from src.config import settings
from src.email_intelligence.models import (
    ActionItem,
    EmailCategory,
    EmailPriority,
    HeuristicEvaluation,
    LLMTriageOutput,
    UnifiedEmail,
)
from src.email_intelligence.prompts import (
    EMAIL_INTELLIGENCE_SYSTEM_PROMPT,
    FEW_SHOT_EXAMPLES,
)

logger = logging.getLogger("VIERNES.LLMClassifier")


class LLMClassifier:
    """
    Executes semantic evaluation of emails that passed Tier-1 pre-filtering.
    """

    def __init__(
        self,
        api_key: Optional[str] = settings.OPENAI_API_KEY or settings.GEMINI_API_KEY,
        model: str = settings.DEFAULT_LLM_MODEL,
    ):
        self.api_key = api_key
        self.model = model

    def build_user_prompt(
        self, email_obj: UnifiedEmail, heuristic_eval: Optional[HeuristicEvaluation] = None
    ) -> str:
        heuristic_context = ""
        if heuristic_eval:
            heuristic_context = (
                f"\n[Tier-1 Heuristic Hint: score={heuristic_eval.heuristic_score:.1f}, "
                f"reasons={'; '.join(heuristic_eval.reasons)}]\n"
            )

        truncated_body = email_obj.body_text[:3500]

        return f"""Please analyze this incoming email:
{heuristic_context}
- SENDER: {email_obj.sender_name or ''} <{email_obj.sender_email}>
- RECIPIENTS: {', '.join(email_obj.recipient_emails)}
- CC: {', '.join(email_obj.cc_emails)}
- DATE: {email_obj.date.isoformat()}
- SUBJECT: {email_obj.subject}
- HAS ATTACHMENTS: {email_obj.has_attachments} ({', '.join(email_obj.attachment_filenames)})

EMAIL BODY:
\"\"\"
{truncated_body}
\"\"\"

Produce the JSON response according to the specified taxonomy and schema.
"""

    async def classify(
        self, email_obj: UnifiedEmail, heuristic_eval: Optional[HeuristicEvaluation] = None
    ) -> LLMTriageOutput:
        """
        Calls LLM to classify email and parse structured response into LLMTriageOutput.
        """
        user_prompt = self.build_user_prompt(email_obj, heuristic_eval)

        # If an OpenAI or Gemini API key is configured and httpx is available, execute HTTP request
        if httpx and settings.OPENAI_API_KEY:
            return await self._call_openai_api(user_prompt)
        elif httpx and settings.GEMINI_API_KEY:
            return await self._call_gemini_api(user_prompt)
        else:
            # Fallback heuristic emulator for offline/development mode
            logger.info("No LLM API key provided; using built-in semantic rule fallback.")
            return self._fallback_semantic_classifier(email_obj, heuristic_eval)

    async def _call_openai_api(self, user_prompt: str) -> LLMTriageOutput:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = [{"role": "system", "content": EMAIL_INTELLIGENCE_SYSTEM_PROMPT}]

        # Inject few-shots
        for example in FEW_SHOT_EXAMPLES:
            messages.append({"role": "user", "content": json.dumps(example["input"])})
            messages.append({"role": "assistant", "content": json.dumps(example["output"])})

        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed_json = json.loads(content)
            return LLMTriageOutput(**parsed_json)

    async def _call_gemini_api(self, user_prompt: str) -> LLMTriageOutput:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        prompt_full = f"{EMAIL_INTELLIGENCE_SYSTEM_PROMPT}\n\n{user_prompt}"

        payload = {
            "contents": [{"parts": [{"text": prompt_full}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_json = json.loads(content)
            return LLMTriageOutput(**parsed_json)

    def _fallback_semantic_classifier(
        self, email_obj: UnifiedEmail, heuristic_eval: Optional[HeuristicEvaluation]
    ) -> LLMTriageOutput:
        """Deterministic semantic fallback when running in testing or offline mode."""
        subject = email_obj.subject.lower()
        body = email_obj.body_text.lower()
        sender = email_obj.sender_email.lower()

        # Critical triggers
        if any(w in subject or w in body for w in ["outage", "production down", "sev-1", "security breach"]):
            return LLMTriageOutput(
                category=EmailCategory.CRITICAL,
                priority=EmailPriority.P1_CRITICAL,
                urgency_reasoning="Critical keyword detected in subject or message body.",
                executive_summary=f"Emergency communication regarding {email_obj.subject} from {email_obj.sender_email}.",
                action_items=[ActionItem(task="Investigate incident immediately", assignee="User", deadline="Immediate")],
                deadline="Immediate",
                suggested_reply="Acknowledged. Investigating the issue immediately.",
                requires_immediate_push=True,
            )

        # Action Required
        if any(w in subject or w in body for w in ["please review", "approval needed", "action required", "can you send"]):
            return LLMTriageOutput(
                category=EmailCategory.ACTION_REQUIRED,
                priority=EmailPriority.P2_HIGH if (heuristic_eval and heuristic_eval.is_vip) else EmailPriority.P3_MEDIUM,
                urgency_reasoning="Direct action or feedback requested in email.",
                executive_summary=f"{email_obj.sender_name or sender} requested action/review on '{email_obj.subject}'.",
                action_items=[ActionItem(task=f"Review and respond to: {email_obj.subject}", assignee="User", deadline="Today")],
                deadline="Today",
                suggested_reply=f"Hi {email_obj.sender_name or 'there'}, received. Reviewing this and will follow up shortly.",
                requires_immediate_push=False,
            )

        # Default fallback to Important or FYI
        if heuristic_eval and heuristic_eval.is_vip:
            return LLMTriageOutput(
                category=EmailCategory.IMPORTANT,
                priority=EmailPriority.P2_HIGH,
                urgency_reasoning="Sender is recognized as a VIP stakeholder.",
                executive_summary=f"Important message from VIP sender {sender}: '{email_obj.subject}'.",
                action_items=[],
                deadline=None,
                suggested_reply=None,
                requires_immediate_push=False,
            )

        return LLMTriageOutput(
            category=EmailCategory.FYI_TRANSACTIONAL,
            priority=EmailPriority.P4_LOW,
            urgency_reasoning="General information / non-urgent message.",
            executive_summary=f"Notification: {email_obj.subject}.",
            action_items=[],
            deadline=None,
            suggested_reply=None,
            requires_immediate_push=False,
        )
