#!/usr/bin/env python3
"""
Integration Webhook Test Script

Simulates webhook events from telephony providers to test the integration
without requiring a real provider connection.

Usage:
    # Start the Flask app first:
    python main.py

    # Then run this script:
    python scripts/test_integration_webhooks.py

    # Or with custom options:
    python scripts/test_integration_webhooks.py --base-url http://localhost:8000 --provider aircall
"""
import argparse
import hashlib
import hmac
import json
import time
import requests
from datetime import datetime, timezone


# Default configuration
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PROVIDER = "generic"
DEFAULT_INTEGRATION_ID = "test-integration"
DEFAULT_WEBHOOK_SECRET = "test-secret-123"


def generate_signature(payload: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook verification."""
    return hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()


def send_webhook(base_url: str, provider: str, integration_id: str,
                 payload: dict, secret: str = None) -> dict:
    """Send a webhook to the integration endpoint."""
    url = f"{base_url}/api/v1/integrations/{provider}/webhook/{integration_id}"
    payload_bytes = json.dumps(payload).encode('utf-8')

    headers = {
        "Content-Type": "application/json",
    }

    # Add signature if secret provided
    if secret:
        signature = generate_signature(payload_bytes, secret)
        if provider == "aircall":
            headers["X-Aircall-Signature"] = f"sha256={signature}"
        else:
            headers["X-Webhook-Signature"] = signature

    print(f"\n{'='*60}")
    print(f"Sending webhook to: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)[:500]}...")

    try:
        response = requests.post(url, data=payload_bytes, headers=headers)
        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def simulate_aircall_call_flow(base_url: str, integration_id: str, secret: str = None):
    """Simulate a complete Aircall call flow."""
    call_id = f"aircall-{int(time.time())}"
    timestamp = int(time.time())

    print("\n" + "="*70)
    print("SIMULATING AIRCALL CALL FLOW")
    print("="*70)

    # 1. Call Created
    print("\n[1/4] Simulating call.created event...")
    payload = {
        "resource": "call",
        "event": "call.created",
        "timestamp": timestamp,
        "token": "test-token",
        "data": {
            "id": call_id,
            "direct_link": f"https://app.aircall.io/calls/{call_id}",
            "direction": "inbound",
            "status": "initial",
            "started_at": timestamp,
            "raw_digits": "+33612345678",
            "user": {
                "id": 42,
                "name": "Jean Dupont",
                "email": "jean@company.com"
            },
            "contact": {
                "id": 123,
                "first_name": "Marie",
                "last_name": "Customer"
            },
            "number": {
                "id": 1,
                "name": "Support Line",
                "digits": "+33123456789"
            },
            "tags": ["support", "billing"]
        }
    }
    send_webhook(base_url, "aircall", integration_id, payload, secret)
    time.sleep(1)

    # 2. Call Answered
    print("\n[2/4] Simulating call.answered event...")
    payload["event"] = "call.answered"
    payload["timestamp"] = timestamp + 10
    payload["data"]["status"] = "answered"
    payload["data"]["answered_at"] = timestamp + 10
    send_webhook(base_url, "aircall", integration_id, payload, secret)
    time.sleep(1)

    # 3. Call Ended
    print("\n[3/4] Simulating call.ended event...")
    payload["event"] = "call.ended"
    payload["timestamp"] = timestamp + 120
    payload["data"]["status"] = "done"
    payload["data"]["ended_at"] = timestamp + 120
    payload["data"]["duration"] = 110
    payload["data"]["recording"] = f"https://recordings.aircall.io/{call_id}.mp3"
    send_webhook(base_url, "aircall", integration_id, payload, secret)

    print("\n" + "="*70)
    print(f"AIRCALL FLOW COMPLETE - Call ID: {call_id}")
    print("="*70)

    return call_id


def simulate_generic_call_with_transcription(base_url: str, integration_id: str, secret: str = None):
    """Simulate a generic call with transcription events."""
    call_id = f"generic-{int(time.time())}"
    timestamp = datetime.now(timezone.utc).isoformat()

    print("\n" + "="*70)
    print("SIMULATING GENERIC CALL WITH TRANSCRIPTION")
    print("="*70)

    # 1. Call Started
    print("\n[1/5] Simulating call.started event...")
    payload = {
        "event_type": "call.started",
        "call_id": call_id,
        "timestamp": timestamp,
        "data": {
            "direction": "inbound",
            "caller_number": "+33612345678",
            "agent_id": "agent-42",
            "agent_name": "Support Agent",
            "customer_name": "Test Customer",
            "queue": "Technical Support"
        }
    }
    send_webhook(base_url, "generic", integration_id, payload, secret)
    time.sleep(1)

    # 2. First transcription (customer asking about alarm)
    print("\n[2/5] Simulating transcription from customer...")
    payload = {
        "event_type": "transcription.final",
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "text": "Bonjour, j'ai un problème avec mon système d'alarme. Le détecteur de mouvement dans le salon clignote en rouge et l'alarme se déclenche toute seule.",
            "speaker": "customer",
            "confidence": 0.95,
            "language": "fr",
            "start_time": 5.0,
            "end_time": 12.5
        }
    }
    send_webhook(base_url, "generic", integration_id, payload, secret)
    time.sleep(2)

    # 3. Agent response transcription
    print("\n[3/5] Simulating transcription from agent...")
    payload = {
        "event_type": "transcription.final",
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "text": "Je comprends, je vais vérifier cela. Pouvez-vous me donner votre numéro de client ?",
            "speaker": "agent",
            "confidence": 0.92,
            "language": "fr",
            "start_time": 13.0,
            "end_time": 17.5
        }
    }
    send_webhook(base_url, "generic", integration_id, payload, secret)
    time.sleep(1)

    # 4. Customer follow-up (this should trigger AI analysis)
    print("\n[4/5] Simulating another customer transcription (triggers AI)...")
    payload = {
        "event_type": "transcription.final",
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "text": "Mon numéro est 123456. Le problème a commencé hier soir. J'ai essayé de réinitialiser le détecteur mais ça ne marche pas.",
            "speaker": "customer",
            "confidence": 0.94,
            "language": "fr",
            "start_time": 18.0,
            "end_time": 25.0
        }
    }
    send_webhook(base_url, "generic", integration_id, payload, secret)
    time.sleep(1)

    # 5. Call Ended
    print("\n[5/5] Simulating call.ended event...")
    payload = {
        "event_type": "call.ended",
        "call_id": call_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "duration": 180,
            "disposition": "resolved"
        }
    }
    send_webhook(base_url, "generic", integration_id, payload, secret)

    print("\n" + "="*70)
    print(f"GENERIC FLOW COMPLETE - Call ID: {call_id}")
    print("="*70)

    return call_id


def check_session_suggestions(base_url: str, call_id: str, token: str = None):
    """Check suggestions generated for a session."""
    url = f"{base_url}/api/v1/integrations/sessions/by-call/{call_id}"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"\n{'='*60}")
    print(f"Checking session for call: {call_id}")

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"Session found: {result.get('session_id')}")
            print(f"Status: {result.get('status')}")
            print(f"Suggestions count: {result.get('suggestions_count', 0)}")

            # Get suggestions
            if result.get('session_id'):
                suggestions_url = f"{base_url}/api/v1/integrations/sessions/{result['session_id']}/suggestions"
                sug_response = requests.get(suggestions_url, headers=headers)
                if sug_response.status_code == 200:
                    suggestions = sug_response.json()
                    print(f"\nSuggestions retrieved: {suggestions.get('total', 0)}")
                    for sug in suggestions.get('suggestions', [])[:3]:
                        print(f"  - [{sug.get('type')}] {sug.get('title', '')[:50]}...")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error checking session: {e}")


def setup_test_integration(base_url: str, token: str, company_id: int = 1):
    """Create a test integration configuration."""
    url = f"{base_url}/api/v1/admin/integrations"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "name": "Test Integration",
        "integration_type": "cloud_webhook",
        "provider": "generic",
        "integration_id": DEFAULT_INTEGRATION_ID,
        "webhook_secret": DEFAULT_WEBHOOK_SECRET,
        "company_id": company_id,
        "settings": {
            "test_mode": True
        }
    }

    print(f"\n{'='*60}")
    print("Creating test integration configuration...")

    try:
        response = requests.post(url, json=payload, headers=headers)
        result = response.json()
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2)}")

        if response.status_code == 201:
            print(f"\nWebhook URL: {result.get('webhook_url')}")

        return result
    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test integration webhooks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL of the API")
    parser.add_argument("--provider", default="generic", choices=["aircall", "generic"],
                        help="Provider to simulate")
    parser.add_argument("--integration-id", default=DEFAULT_INTEGRATION_ID,
                        help="Integration ID to use")
    parser.add_argument("--secret", default=None, help="Webhook secret for signature")
    parser.add_argument("--token", default=None, help="JWT token for authenticated endpoints")
    parser.add_argument("--setup", action="store_true", help="Setup test integration first")
    parser.add_argument("--company-id", type=int, default=1, help="Company ID for setup")

    args = parser.parse_args()

    print("\n" + "="*70)
    print("INTEGRATION WEBHOOK TEST SCRIPT")
    print("="*70)
    print(f"Base URL: {args.base_url}")
    print(f"Provider: {args.provider}")
    print(f"Integration ID: {args.integration_id}")

    # Setup integration if requested
    if args.setup and args.token:
        setup_test_integration(args.base_url, args.token, args.company_id)

    # Run simulation based on provider
    if args.provider == "aircall":
        call_id = simulate_aircall_call_flow(
            args.base_url,
            args.integration_id,
            args.secret
        )
    else:
        call_id = simulate_generic_call_with_transcription(
            args.base_url,
            args.integration_id,
            args.secret
        )

    # Check results if token provided
    if args.token:
        time.sleep(2)  # Wait for processing
        check_session_suggestions(args.base_url, call_id, args.token)

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("1. Check the application logs for processing details")
    print("2. Use the admin API to verify sessions were created")
    print("3. Check the database for transcription segments")
    print(f"\nTo view session: GET /api/v1/integrations/sessions/by-call/{call_id}")


if __name__ == "__main__":
    main()
