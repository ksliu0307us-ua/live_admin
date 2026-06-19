"""Mock LLM client with realistic canned responses for demo/testing."""

import logging
import re
from datetime import date, timedelta

from app.llm.client import BaseLLMClient
from app.logging_config import StepTimer, log_event

logger = logging.getLogger("app.llm.mock")

TODAY = date.today()


def _date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _future(days: int) -> str:
    return _date_str(TODAY + timedelta(days=days))


def _past(days: int) -> str:
    return _date_str(TODAY - timedelta(days=days))


def _fc(value, confidence: float, explanation: str) -> dict:
    """Create a field confidence entry."""
    return {"value": value, "confidence": confidence, "explanation": explanation}


MOCK_EXTRACTIONS: list[tuple[list[str], dict]] = [
    (
        ["netflix"],
        {
            "merchant": _fc("Netflix", 0.99, "Explicitly named in subject and body"),
            "document_type": _fc("subscription", 0.95, "Renewal email for a streaming subscription"),
            "amount": _fc(22.99, 0.95, "Dollar amount found in billing details"),
            "currency": _fc("USD", 0.90, "Dollar sign used, US-based service"),
            "purchase_date": _fc(None, 0.0, "No purchase date mentioned"),
            "subscription_status": _fc("active", 0.95, "Email confirms upcoming renewal"),
            "renewal_date": _fc(_future(8), 0.95, "Renewal date explicitly stated"),
            "free_trial_end_date": _fc(None, 0.0, "No trial mentioned"),
            "return_deadline": _fc(None, 0.0, "Not applicable for subscriptions"),
            "cancellation_deadline": _fc(_future(8), 0.85, "Must cancel before renewal date"),
            "warranty_end_date": _fc(None, 0.0, "Not applicable"),
            "cancellation_policy": _fc(
                "Cancel anytime at netflix.com/account before billing date",
                0.90,
                "Cancellation instructions included in email",
            ),
            "refund_opportunity": _fc(None, 0.3, "No explicit refund option mentioned"),
            "price_increased": _fc(False, 0.85, "No price change mentioned"),
            "old_price": _fc(None, 0.0, "Not applicable"),
            "new_price": _fc(None, 0.0, "Not applicable"),
            "detected_risk": _fc("Upcoming recurring charge of $22.99", 0.90, "Renewal approaching"),
            "recommended_action": _fc("cancel_subscription", 0.80, "User may want to cancel before renewal"),
            "explanation": _fc("Netflix Premium subscription renewing soon for $22.99/mo", 0.95, "Key finding summary"),
        },
    ),
    (
        ["amazon", "order", "shipped"],
        {
            "merchant": _fc("Amazon", 0.99, "Amazon.com explicitly named"),
            "document_type": _fc("receipt", 0.95, "Order confirmation / shipping notification"),
            "amount": _fc(278.00, 0.98, "Item price clearly listed"),
            "currency": _fc("USD", 0.95, "Dollar sign used"),
            "purchase_date": _fc(_past(7), 0.90, "Order placement date in email"),
            "subscription_status": _fc("one_time", 0.95, "Single item purchase"),
            "renewal_date": _fc(None, 0.0, "Not a subscription"),
            "free_trial_end_date": _fc(None, 0.0, "Not applicable"),
            "return_deadline": _fc(
                _future(23), 0.90, "30-day return policy from delivery date"
            ),
            "cancellation_deadline": _fc(None, 0.0, "Not a subscription"),
            "warranty_end_date": _fc(None, 0.3, "No warranty information in email"),
            "cancellation_policy": _fc(None, 0.0, "Not a subscription"),
            "refund_opportunity": _fc(
                "Full refund available if returned in original packaging within 30 days",
                0.85,
                "Return policy explicitly stated",
            ),
            "price_increased": _fc(False, 0.95, "Not applicable for one-time purchase"),
            "old_price": _fc(None, 0.0, "Not applicable"),
            "new_price": _fc(None, 0.0, "Not applicable"),
            "detected_risk": _fc("Return window closing in 23 days", 0.85, "Time-limited return policy"),
            "recommended_action": _fc("return_item", 0.70, "Return window is open if item is unwanted"),
            "explanation": _fc("Amazon order for $278.00 headphones with 30-day return window", 0.95, "Key finding summary"),
        },
    ),
    (
        ["spotify", "free trial"],
        {
            "merchant": _fc("Spotify", 0.99, "Spotify Premium explicitly named"),
            "document_type": _fc("subscription", 0.95, "Free trial for a subscription service"),
            "amount": _fc(10.99, 0.95, "Monthly charge after trial stated"),
            "currency": _fc("USD", 0.90, "Dollar sign used"),
            "purchase_date": _fc(None, 0.0, "Trial start date not mentioned"),
            "subscription_status": _fc("trial", 0.98, "Free trial explicitly mentioned"),
            "renewal_date": _fc(None, 0.0, "Not yet a paid subscription"),
            "free_trial_end_date": _fc(
                _future(5), 0.95, "Trial end date explicitly stated"
            ),
            "return_deadline": _fc(None, 0.0, "Not applicable"),
            "cancellation_deadline": _fc(_future(5), 0.95, "Must cancel before trial ends"),
            "warranty_end_date": _fc(None, 0.0, "Not applicable"),
            "cancellation_policy": _fc(
                "Cancel at spotify.com/account > Your plan > Cancel Premium before trial ends",
                0.95,
                "Step-by-step cancellation instructions in email",
            ),
            "refund_opportunity": _fc(None, 0.2, "No refund for free trial"),
            "price_increased": _fc(False, 0.90, "No price increase mentioned"),
            "old_price": _fc(None, 0.0, "Not applicable"),
            "new_price": _fc(None, 0.0, "Not applicable"),
            "detected_risk": _fc("Automatic charge of $10.99/mo after trial ends", 0.95, "Trial converting to paid"),
            "recommended_action": _fc("trial_ending_alert", 0.90, "Cancel before trial ends to avoid charge"),
            "explanation": _fc("Spotify free trial ending in 5 days, will charge $10.99/mo after", 0.95, "Key finding summary"),
        },
    ),
    (
        ["applecare", "warranty", "coverage", "expir"],
        {
            "merchant": _fc("Apple", 0.99, "AppleCare+ from Apple explicitly named"),
            "document_type": _fc("warranty", 0.95, "Warranty/coverage expiration notice"),
            "amount": _fc(279.00, 0.90, "AppleCare+ price paid listed"),
            "currency": _fc("USD", 0.90, "Dollar sign used"),
            "purchase_date": _fc(_past(730), 0.85, "Purchase date mentioned as 2 years ago"),
            "subscription_status": _fc("active", 0.90, "Coverage is still active but expiring"),
            "renewal_date": _fc(None, 0.0, "AppleCare+ does not auto-renew"),
            "free_trial_end_date": _fc(None, 0.0, "Not applicable"),
            "return_deadline": _fc(None, 0.0, "Not applicable"),
            "cancellation_deadline": _fc(None, 0.0, "Not a recurring subscription"),
            "warranty_end_date": _fc(
                _future(23), 0.95, "Coverage expiration date explicitly stated"
            ),
            "cancellation_policy": _fc(None, 0.0, "Not a recurring subscription"),
            "refund_opportunity": _fc(None, 0.2, "No refund applicable"),
            "price_increased": _fc(False, 0.90, "Not applicable"),
            "old_price": _fc(None, 0.0, "Not applicable"),
            "new_price": _fc(None, 0.0, "Not applicable"),
            "detected_risk": _fc("AppleCare+ coverage expiring in 23 days", 0.95, "Warranty ending soon"),
            "recommended_action": _fc("warranty_reminder", 0.90, "Consider extending coverage before expiry"),
            "explanation": _fc("AppleCare+ warranty for MacBook Pro expiring in 23 days", 0.95, "Key finding summary"),
        },
    ),
    (
        ["youtube", "price increase", "price change", "price will change"],
        {
            "merchant": _fc("YouTube Premium", 0.99, "YouTube Premium explicitly named"),
            "document_type": _fc("bill", 0.90, "Billing notification with price change"),
            "amount": _fc(19.99, 0.95, "New monthly price explicitly stated"),
            "currency": _fc("USD", 0.90, "Dollar sign used"),
            "purchase_date": _fc(None, 0.0, "Original purchase date not mentioned"),
            "subscription_status": _fc("active", 0.95, "Active subscription with price change"),
            "renewal_date": _fc(_future(28), 0.90, "Next billing date mentioned"),
            "free_trial_end_date": _fc(None, 0.0, "Not applicable"),
            "return_deadline": _fc(None, 0.0, "Not applicable"),
            "cancellation_deadline": _fc(_future(28), 0.85, "Cancel before new price takes effect"),
            "warranty_end_date": _fc(None, 0.0, "Not applicable"),
            "cancellation_policy": _fc(
                "Cancel anytime at youtube.com/paid_memberships",
                0.90,
                "Cancellation URL provided in email",
            ),
            "refund_opportunity": _fc(
                "Price increasing from $13.99 to $19.99/month -- may be able to negotiate or find a promotional rate",
                0.60,
                "Significant price increase may warrant requesting adjustment",
            ),
            "price_increased": _fc(True, 0.99, "Price change explicitly announced"),
            "old_price": _fc(13.99, 0.99, "Current price explicitly stated"),
            "new_price": _fc(19.99, 0.99, "New price explicitly stated"),
            "detected_risk": _fc("43% price increase from $13.99 to $19.99/mo", 0.99, "Significant price hike"),
            "recommended_action": _fc("bill_increase_alert", 0.95, "Price increase warrants review"),
            "explanation": _fc("YouTube Premium price increasing 43% from $13.99 to $19.99/month", 0.95, "Key finding summary"),
        },
    ),
]


MOCK_DRAFTS = {
    "cancel_subscription": {
        "subject": "Cancellation Request -- {merchant} Subscription",
        "body": """Dear {merchant} Support,

I am writing to request the immediate cancellation of my {merchant} subscription.

{context}

Please confirm the cancellation and ensure that no further charges are applied to my payment method. I would appreciate written confirmation that my subscription has been cancelled and the effective date of cancellation.

If there are any remaining days on my current billing cycle, I would like to retain access until the end of that period.

Thank you for your prompt attention to this matter.

Best regards,
[Your Name]""",
    },
    "return_item": {
        "subject": "Return Request -- {merchant} Order",
        "body": """Dear {merchant} Customer Service,

I am writing to initiate a return for a recent purchase.

{context}

I understand this falls within the return policy window. Please provide me with:
1. A return shipping label or return instructions
2. Confirmation of the refund amount and timeline
3. Any additional steps required on my end

I will ensure the item is returned in its original packaging and condition.

Thank you for your assistance.

Best regards,
[Your Name]""",
    },
    "request_refund": {
        "subject": "Refund Request -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing to request a refund for a recent charge.

{context}

I believe a refund is warranted in this case and would appreciate your prompt review of this request. Please let me know the expected timeline for processing and any additional information you may need.

Thank you for your time and attention to this matter.

Best regards,
[Your Name]""",
    },
    "request_price_adjustment": {
        "subject": "Price Adjustment Request -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing to request a price adjustment for my subscription.

{context}

As a loyal customer, I would like to inquire about:
1. Any available promotional rates or loyalty discounts
2. Whether the previous rate can be honored for existing subscribers
3. Alternative plan options at a lower price point

I value the service and would prefer to continue my subscription at a fair price.

Thank you for considering my request.

Best regards,
[Your Name]""",
    },
    "dispute_bill_increase": {
        "subject": "Dispute: Recent Bill Increase -- {merchant}",
        "body": """Dear {merchant} Billing Department,

I am writing to formally dispute the recent increase to my bill.

{context}

I was not adequately notified of this change, and I believe the increase is unreasonable. I would like to request:
1. A detailed explanation of why the price has increased
2. Restoration of my previous rate, or a comparable alternative
3. A credit or adjustment for any overcharges already applied

If this matter cannot be resolved, I may need to explore alternative service providers. I would prefer to remain a customer and hope we can reach a fair resolution.

Thank you for your attention to this matter.

Best regards,
[Your Name]""",
    },
    "bill_increase_alert": {
        "subject": "Regarding Recent Price Increase -- {merchant}",
        "body": """Dear {merchant} Support,

I recently received notice of an upcoming price increase for my subscription.

{context}

As a loyal customer, I would like to inquire about:
1. Any available promotional rates or loyalty discounts
2. Alternative plan options at a lower price point
3. Whether the previous rate can be honored for existing subscribers

I value the service and would prefer to continue my subscription, but the price increase is significant. I would appreciate any options you can offer.

Thank you for considering my request.

Best regards,
[Your Name]""",
    },
    "warranty_reminder": {
        "subject": "Warranty Coverage Inquiry -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing regarding my warranty coverage, which is approaching its expiration date.

{context}

Before my coverage expires, I would like to:
1. Understand my options for extending coverage
2. Know if there are any inspections or services I should schedule before expiration
3. Get information about the cost of any available extended warranty plans

Please let me know the available options and any deadlines for extending my coverage.

Thank you for your assistance.

Best regards,
[Your Name]""",
    },
    "warranty_claim": {
        "subject": "Warranty Claim -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing to submit a warranty claim for a product covered under my warranty/extended coverage plan.

{context}

I would like to request:
1. A repair or replacement under my warranty coverage
2. Information about the claim process and expected timeline
3. Any documentation I need to provide

Please advise on the next steps to process this claim before my coverage expires.

Thank you for your prompt assistance.

Best regards,
[Your Name]""",
    },
    "trial_ending_alert": {
        "subject": "Cancellation Before Trial Ends -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing to cancel my subscription before my free trial period ends to avoid being charged.

{context}

Please confirm that:
1. My subscription/trial has been cancelled
2. No charges will be applied to my payment method
3. The effective date of cancellation

If I am unable to cancel through my account settings, please process this cancellation request on your end.

Thank you for your prompt attention.

Best regards,
[Your Name]""",
    },
    "monitor_price": {
        "subject": "Pricing Inquiry -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing to inquire about current pricing and any available promotions for my account.

{context}

I would appreciate information about:
1. Any current promotional rates or discounts
2. Loyalty programs for existing subscribers
3. Whether my current rate can be reviewed

Thank you for your time.

Best regards,
[Your Name]""",
    },
    "no_action": {
        "subject": "Account Inquiry -- {merchant}",
        "body": """Dear {merchant} Support,

I am writing to inquire about the status of my account.

{context}

Please let me know if there are any actions I need to take or any important updates regarding my account.

Thank you.

Best regards,
[Your Name]""",
    },
}


class MockLLMClient(BaseLLMClient):
    def extract(self, text: str) -> dict:
        with StepTimer() as timer:
            text_lower = text.lower()
            matched_template = None
            for keywords, response in MOCK_EXTRACTIONS:
                if any(kw in text_lower for kw in keywords):
                    matched_template = keywords[0]
                    result = response
                    break
            else:
                result = self._generic_extraction(text)

        merchant = result.get("merchant", {}).get("value", "unknown")
        doc_type = result.get("document_type", {}).get("value", "unknown")
        log_event(logger, logging.INFO, "mock_extraction",
                  model="mock",
                  matched_template=matched_template,
                  input_chars=len(text),
                  output_fields=len(result),
                  merchant=merchant,
                  document_type=doc_type,
                  elapsed_ms=timer.elapsed_ms)
        return result

    def draft_email(
        self, action_type: str, merchant: str, context: str, tone: str = "professional"
    ) -> dict:
        with StepTimer() as timer:
            template = MOCK_DRAFTS.get(action_type, MOCK_DRAFTS["request_refund"])
            result = {
                "subject": template["subject"].format(merchant=merchant, context=context),
                "body": template["body"].format(merchant=merchant, context=context),
            }
        log_event(logger, logging.INFO, "mock_draft",
                  model="mock",
                  action_type=action_type,
                  merchant=merchant,
                  tone=tone,
                  output_chars=len(result["body"]),
                  elapsed_ms=timer.elapsed_ms)
        return result

    def _generic_extraction(self, text: str) -> dict:
        """Fallback for unrecognized inputs -- attempts basic extraction."""
        merchant = "Unknown Merchant"
        amount = None

        amount_match = re.search(r"\$(\d+(?:\.\d{2})?)", text)
        if amount_match:
            amount = float(amount_match.group(1))

        return {
            "merchant": _fc(merchant, 0.30, "Could not confidently identify the merchant"),
            "document_type": _fc("unknown", 0.30, "Could not classify document type"),
            "amount": _fc(amount, 0.50 if amount else 0.0, "Attempted to extract dollar amount"),
            "currency": _fc("USD", 0.50, "Assumed USD"),
            "purchase_date": _fc(None, 0.0, "Could not determine purchase date"),
            "subscription_status": _fc(None, 0.20, "Could not determine subscription status"),
            "renewal_date": _fc(None, 0.0, "No renewal date found"),
            "free_trial_end_date": _fc(None, 0.0, "No trial information found"),
            "return_deadline": _fc(None, 0.0, "No return deadline found"),
            "cancellation_deadline": _fc(None, 0.0, "No cancellation deadline found"),
            "warranty_end_date": _fc(None, 0.0, "No warranty information found"),
            "cancellation_policy": _fc(None, 0.0, "No cancellation policy found"),
            "refund_opportunity": _fc(None, 0.0, "No refund opportunity identified"),
            "price_increased": _fc(False, 0.50, "No price increase detected"),
            "old_price": _fc(None, 0.0, "Not applicable"),
            "new_price": _fc(None, 0.0, "Not applicable"),
            "detected_risk": _fc(None, 0.0, "No specific risk detected"),
            "recommended_action": _fc("no_action", 0.50, "Insufficient information to recommend action"),
            "explanation": _fc("Could not extract enough information to provide a useful summary", 0.30, "Low confidence extraction"),
        }
