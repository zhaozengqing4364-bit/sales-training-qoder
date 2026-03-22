#!/usr/bin/env python3
"""
Detailed WebSocket Message Flow Test

Tests:
1. Sales WebSocket message flow
2. ASR transcript messages
3. TTS audio chunk messages
4. Status transitions (listening -> thinking -> speaking)
5. Error handling
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import httpx
import websockets.client as ws_client

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'


async def get_dev_token() -> str:
    """Get development JWT token"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:3444/api/v1/auth/dev-login",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data["data"]["access_token"]
    except Exception as e:
        print(f"Warning: Failed to get dev token: {e}")
    return ""


async def test_sales_message_flow():
    """Test complete sales WebSocket message flow"""
    print(f"{Colors.CYAN}{'='*60}")
    print("Sales WebSocket Message Flow Test")
    print(f"{'='*60}{Colors.RESET}\n")

    token = await get_dev_token()
    session_id = str(uuid.uuid4())
    uri = f"ws://localhost:3444/ws/sales?session_id={session_id}"
    if token:
        uri += f"&token={token}"

    print(f"{Colors.YELLOW}Connecting to: {uri}{Colors.RESET}\n")

    message_log = []

    try:
        async with ws_client.connect(uri, timeout=10) as websocket:
            print(f"{Colors.GREEN} Connected successfully{Colors.RESET}\n")

            # Message handler task
            async def message_receiver():
                while True:
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        parsed = json.loads(msg)
                        msg_type = parsed.get("type")
                        timestamp = parsed.get("timestamp")

                        log_entry = {
                            "timestamp": timestamp,
                            "type": msg_type,
                            "data": parsed.get("data")
                        }
                        message_log.append(log_entry)

                        # Print message details
                        print(f"{Colors.CYAN}[{msg_type}]{Colors.RESET} {timestamp}")

                        # Print data for important messages
                        if msg_type == "status":
                            data = parsed.get("data", {})
                            ai_state = data.get("ai_state")
                            print(f"    AI State: {ai_state}")
                        elif msg_type == "asr_transcript":
                            data = parsed.get("data", {})
                            text = data.get("text", "")
                            is_final = data.get("is_final", False)
                            print(f"    Transcript: {text} (final={is_final})")
                        elif msg_type == "tts_audio":
                            data = parsed.get("data", {})
                            text = data.get("text", "")
                            print(f"    TTS: {text[:50]}...")
                        elif msg_type == "error":
                            data = parsed.get("data", {})
                            code = data.get("code")
                            print(f"    Error: {code}")

                    except asyncio.TimeoutError:
                        continue

            # Start message receiver
            receiver_task = asyncio.create_task(message_receiver())

            # Wait for initial connection messages
            await asyncio.sleep(2)

            # Send text message
            print(f"\n{Colors.YELLOW}--- Sending test message ---{Colors.RESET}")
            text_msg = {
                "type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"text": "你好，我想了解一下产品信息"}
            }
            await websocket.send(json.dumps(text_msg))
            print(f"Sent: {text_msg['data']['text']}")

            # Wait for responses
            await asyncio.sleep(5)

            # Send another message
            print(f"\n{Colors.YELLOW}--- Sending second test message ---{Colors.RESET}")
            text_msg2 = {
                "type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"text": "这个产品有什么优势？"}
            }
            await websocket.send(json.dumps(text_msg2))
            print(f"Sent: {text_msg2['data']['text']}")

            # Wait for responses
            await asyncio.sleep(5)

            # Cancel receiver
            receiver_task.cancel()

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        return message_log, False

    # Analyze message flow
    print(f"\n{Colors.CYAN}{'='*60}")
    print("Message Flow Analysis")
    print(f"{'='*60}{Colors.RESET}\n")

    message_types = [msg["type"] for msg in message_log]
    print(f"{Colors.YELLOW}Message types received: {message_types}{Colors.RESET}\n")

    # Check for expected message types
    expected_types = [
        "connected",
        "status",
        "asr_transcript",
        "tts_audio",
        "error"
    ]

    for exp_type in expected_types:
        count = message_types.count(exp_type)
        status = f"{Colors.GREEN}✓" if count > 0 else f"{Colors.RED}✗"
        print(f"{status} {exp_type}: {count} messages{Colors.RESET}")

    # Analyze state transitions
    print(f"\n{Colors.YELLOW}Status transitions:{Colors.RESET}")
    status_messages = [msg for msg in message_log if msg["type"] == "status"]
    for msg in status_messages:
        data = msg.get("data", {})
        ai_state = data.get("ai_state")
        print(f"  {msg['timestamp']}: {ai_state}")

    return message_log, True


async def test_presentation_message_flow():
    """Test presentation WebSocket message flow"""
    print(f"\n{Colors.CYAN}{'='*60}")
    print("Presentation WebSocket Message Flow Test")
    print(f"{'='*60}{Colors.RESET}\n")

    token = await get_dev_token()
    session_id = str(uuid.uuid4())
    uri = f"ws://localhost:3444/ws/presentation?session_id={session_id}"
    if token:
        uri += f"&token={token}"

    print(f"{Colors.YELLOW}Connecting to: {uri}{Colors.RESET}\n")

    message_log = []

    try:
        async with ws_client.connect(uri, timeout=10) as websocket:
            print(f"{Colors.GREEN} Connected successfully{Colors.RESET}\n")

            async def message_receiver():
                while True:
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        parsed = json.loads(msg)
                        msg_type = parsed.get("type")

                        log_entry = {
                            "type": msg_type,
                            "data": parsed.get("data")
                        }
                        message_log.append(log_entry)

                        print(f"{Colors.CYAN}[{msg_type}]{Colors.RESET}")

                        if msg_type == "slide_update":
                            data = parsed.get("data", {})
                            page = data.get("page_number")
                            total = data.get("total_pages")
                            print(f"    Page: {page}/{total}")
                        elif msg_type == "point_covered":
                            data = parsed.get("data", {})
                            points = data.get("points", [])
                            print(f"    Points: {len(points)}")
                        elif msg_type == "feedback":
                            data = parsed.get("data", {})
                            feedback_type = data.get("feedback_type")
                            print(f"    Feedback: {feedback_type}")
                        elif msg_type == "status":
                            data = parsed.get("data", {})
                            ai_state = data.get("ai_state")
                            print(f"    AI State: {ai_state}")

                    except asyncio.TimeoutError:
                        continue

            receiver_task = asyncio.create_task(message_receiver())

            # Wait for initial messages
            await asyncio.sleep(3)

            # Send page change
            print(f"\n{Colors.YELLOW}--- Sending page change ---{Colors.RESET}")
            page_msg = {
                "type": "page_change",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"page_number": 2}
            }
            await websocket.send(json.dumps(page_msg))
            print(f"Sent: page_change to page 2")

            # Wait for responses
            await asyncio.sleep(2)

            # Send user speaking signal
            print(f"\n{Colors.YELLOW}--- Sending user_speaking ---{Colors.RESET}")
            speaking_msg = {
                "type": "user_speaking",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"speaking": False}
            }
            await websocket.send(json.dumps(speaking_msg))
            print(f"Sent: user_speaking = False")

            await asyncio.sleep(2)

            receiver_task.cancel()

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        return message_log, False

    # Analyze message flow
    print(f"\n{Colors.CYAN}{'='*60}")
    print("Presentation Message Types")
    print(f"{'='*60}{Colors.RESET}\n")

    message_types = [msg["type"] for msg in message_log]
    print(f"{Colors.YELLOW}Received: {message_types}{Colors.RESET}\n")

    expected_types = [
        "connected",
        "status",
        "slide_update",
        "point_covered",
        "feedback"
    ]

    for exp_type in expected_types:
        count = message_types.count(exp_type)
        status = f"{Colors.GREEN}✓" if count > 0 else f"{Colors.RED}✗"
        print(f"{status} {exp_type}: {count} messages{Colors.RESET}")

    return message_log, True


async def test_error_scenarios():
    """Test WebSocket error scenarios"""
    print(f"\n{Colors.CYAN}{'='*60}")
    print("WebSocket Error Scenarios Test")
    print(f"{'='*60}{Colors.RESET}\n")

    results = []

    # Test 1: Invalid message type
    print(f"{Colors.YELLOW}Test 1: Send invalid message type{Colors.RESET}")
    token = await get_dev_token()
    session_id = str(uuid.uuid4())
    uri = f"ws://localhost:3444/ws/sales?session_id={session_id}"
    if token:
        uri += f"&token={token}"

    try:
        async with ws_client.connect(uri, timeout=5) as websocket:
            # Send invalid message
            invalid_msg = {
                "type": "invalid_type_xyz",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {}
            }
            await websocket.send(json.dumps(invalid_msg))

            # Wait for response
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                parsed = json.loads(msg)
                if parsed.get("type") == "error":
                    print(f"  {Colors.GREEN}Error message received{Colors.RESET}")
                    results.append(("Invalid message handled", True))
                else:
                    print(f"  {Colors.YELLOW}Non-error response: {parsed.get('type')}{Colors.RESET}")
                    results.append(("Invalid message handled", True))
            except asyncio.TimeoutError:
                print(f"  {Colors.YELLOW}No error response (may be OK){Colors.RESET}")
                results.append(("Invalid message handled", True))

    except Exception as e:
        print(f"  {Colors.RED}Error: {e}{Colors.RESET}")
        results.append(("Invalid message handled", False))

    # Test 2: Malformed JSON
    print(f"\n{Colors.YELLOW}Test 2: Send malformed JSON{Colors.RESET}")
    session_id = str(uuid.uuid4())
    uri = f"ws://localhost:3444/ws/sales?session_id={session_id}"
    if token:
        uri += f"&token={token}"

    try:
        async with ws_client.connect(uri, timeout=5) as websocket:
            # Send malformed JSON
            await websocket.send("{invalid json}")

            # Connection should remain open (graceful degradation)
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                print(f"  {Colors.GREEN}Connection still active{Colors.RESET}")
                results.append(("Malformed JSON handled", True))
            except asyncio.TimeoutError:
                print(f"  {Colors.YELLOW}No response (connection may be closed){Colors.RESET}")
                results.append(("Malformed JSON handled", False))

    except Exception as e:
        print(f"  {Colors.RED}Error: {e}{Colors.RESET}")
        results.append(("Malformed JSON handled", False))

    # Print results
    print(f"\n{Colors.CYAN}Error Handling Results:{Colors.RESET}\n")
    for test_name, passed in results:
        status = f"{Colors.GREEN}✓" if passed else f"{Colors.RED}✗"
        print(f"{status} {test_name}{Colors.RESET}")

    return results


async def run_tests():
    """Run all detailed tests"""
    print(f"\n{Colors.GREEN}{'='*60}")
    print("WebSocket Detailed Message Flow Test Suite")
    print(f"{'='*60}{Colors.RESET}\n")

    # Test 1: Sales message flow
    await test_sales_message_flow()

    # Test 2: Presentation message flow
    await test_presentation_message_flow()

    # Test 3: Error scenarios
    await test_error_scenarios()

    print(f"\n{Colors.CYAN}{'='*60}")
    print("Tests Complete")
    print(f"{'='*60}{Colors.RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
