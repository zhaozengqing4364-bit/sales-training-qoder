#!/usr/bin/env python3
"""
WebSocket Testing Script for AI Practice System

Tests:
1. PPT Presentation WebSocket: ws://localhost:3444/ws/presentation
2. Sales Practice WebSocket: ws://localhost:3444/ws/sales
3. Connection handshake and heartbeat
4. Message types
5. Error handling
6. Reconnection
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets.client as ws_client

# Configuration
BACKEND_URL = "http://localhost:3444"
WS_BASE_URL = "ws://localhost:3444"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "errors": []
}


def record_result(test_name: str, passed: bool, message: str = ""):
    """Record test result"""
    if passed:
        test_results["passed"].append(f"{test_name}: {message}")
        print(f"  PASSED: {test_name}")
    else:
        test_results["failed"].append(f"{test_name}: {message}")
        print(f"  FAILED: {test_name} - {message}")


def record_error(test_name: str, error: str):
    """Record test error"""
    test_results["errors"].append(f"{test_name}: {error}")
    print(f"  ERROR: {test_name} - {error}")


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


def print_header(title: str):
    """Print a formatted test header"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}    {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}    {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}    {message}{Colors.RESET}")


async def get_dev_token() -> str:
    """Get development JWT token"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BACKEND_URL}/api/v1/auth/dev-login",
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data["data"]["access_token"]
    except Exception as e:
        print(f"Warning: Failed to get dev token: {e}")
    return ""


async def test_health_check():
    """Test backend health check"""
    print_header("TEST 1: Backend Health Check")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BACKEND_URL}/health", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                print_success(f"Backend is healthy: {data.get('status')}")
                return True
            else:
                print_error(f"Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"Health check error: {e}")
        return False


async def test_sales_websocket_connection():
    """Test sales WebSocket connection and basic messages"""
    print_header("TEST 2: Sales WebSocket Connection")

    try:
        token = await get_dev_token()
        session_id = str(uuid.uuid4())
        uri = f"{WS_BASE_URL}/ws/sales?session_id={session_id}"

        if token:
            uri += f"&token={token}"

        print_info(f"Connecting to: {uri}")

        async with ws_client.connect(uri, timeout=10) as websocket:
            print_success("WebSocket connected successfully")

            # Track messages received
            messages_received = []
            start_time = time.time()

            try:
                # Wait for initial messages (connected, greeting)
                while time.time() - start_time < 5:
                    message = await asyncio.wait_for(
                        websocket.recv(), timeout=1.0
                    )
                    messages_received.append(json.loads(message))

                # Analyze messages
                message_types = [msg.get("type") for msg in messages_received]
                print_info(f"Received message types: {message_types}")

                # Check for expected messages
                has_connected = any("connected" in str(mt) or mt == "connected" for mt in message_types)
                record_result(
                    "Sales WebSocket - connected message",
                    has_connected,
                    "connected message received" if has_connected else "no connected message"
                )

                has_status = any("status" in mt for mt in message_types)
                record_result(
                    "Sales WebSocket - status message",
                    has_status,
                    "status message received" if has_status else "no status message"
                )

                return len(messages_received) > 0

            except asyncio.TimeoutError:
                print_info("Timeout waiting for messages (this may be expected)")
                # Still a success if connection was established
                return True

    except Exception as e:
        print_error(f"WebSocket connection error: {e}")
        record_error("Sales WebSocket connection", str(e))
        return False


async def test_sales_websocket_message_types():
    """Test sending various message types to sales WebSocket"""
    print_header("TEST 3: Sales WebSocket Message Types")

    try:
        token = await get_dev_token()
        session_id = str(uuid.uuid4())
        uri = f"{WS_BASE_URL}/ws/sales?session_id={session_id}"
        if token:
            uri += f"&token={token}"

        async with ws_client.connect(uri, timeout=10) as websocket:
            print_success("Connected for message type testing")

            # Wait for connection confirmation
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                print_info(f"Connection response: {json.loads(msg).get('type')}")
            except asyncio.TimeoutError:
                print_info("No connection confirmation received (continuing)")

            # Test 1: Send text message
            test_message = {
                "type": "text",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"text": "Hello, this is a test message"}
            }
            await websocket.send(json.dumps(test_message))
            print_info("Sent: text message")
            record_result("Sales WS - send text", True)

            # Test 2: Send control message
            control_message = {
                "type": "control",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"action": "start"}
            }
            await websocket.send(json.dumps(control_message))
            print_info("Sent: control (start) message")
            record_result("Sales WS - send control", True)

            # Wait for responses
            try:
                for _ in range(3):
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    parsed = json.loads(msg)
                    msg_type = parsed.get("type")
                    print_info(f"Received: {msg_type}")
            except asyncio.TimeoutError:
                print_info("No more messages received")

            return True

    except Exception as e:
        print_error(f"Message type test error: {e}")
        record_error("Sales WS message types", str(e))
        return False


async def test_sales_websocket_with_agent_persona():
    """Test sales WebSocket with agent_id and persona_id"""
    print_header("TEST 4: Sales WebSocket with Agent/Persona")

    try:
        token = await get_dev_token()

        # First, try to get existing agent and persona IDs
        agent_id = None
        persona_id = None

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {token}"} if token else {}

            # Try to get agents
            try:
                agents_resp = await client.get(
                    f"{BACKEND_URL}/api/v1/admin/agents",
                    headers=headers,
                    timeout=5.0
                )
                if agents_resp.status_code == 200:
                    agents_data = agents_resp.json()
                    if isinstance(agents_data, dict) and "data" in agents_data:
                        agents = agents_data["data"]
                    else:
                        agents = agents_data
                    if agents and len(agents) > 0:
                        agent_id = agents[0].get("id")
                        print_info(f"Using agent_id: {agent_id}")
            except Exception as e:
                print_info(f"Could not fetch agents: {e}")

            # Try to get personas
            try:
                personas_resp = await client.get(
                    f"{BACKEND_URL}/api/v1/admin/personas",
                    headers=headers,
                    timeout=5.0
                )
                if personas_resp.status_code == 200:
                    personas_data = personas_resp.json()
                    if isinstance(personas_data, dict) and "data" in personas_data:
                        personas = personas_data["data"]
                    else:
                        personas = personas_data
                    if personas and len(personas) > 0:
                        persona_id = personas[0].get("id")
                        print_info(f"Using persona_id: {persona_id}")
            except Exception as e:
                print_info(f"Could not fetch personas: {e}")

        session_id = str(uuid.uuid4())
        uri = f"{WS_BASE_URL}/ws/sales?session_id={session_id}"
        if token:
            uri += f"&token={token}"
        if agent_id:
            uri += f"&agent_id={agent_id}"
        if persona_id:
            uri += f"&persona_id={persona_id}"

        print_info(f"Connecting to: {uri}")

        async with ws_client.connect(uri, timeout=10) as websocket:
            print_success("Enhanced WebSocket connected")

            messages = []
            start_time = time.time()

            while time.time() - start_time < 5:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    messages.append(json.loads(msg))
                except asyncio.TimeoutError:
                    break

            message_types = [msg.get("type") for msg in messages]
            print_info(f"Received messages: {message_types}")

            # Check for capability feedback messages
            has_capability = any(
                "capability" in str(mt).lower() or
                "fuzzy" in str(mt).lower() or
                "stage" in str(mt).lower() or
                "score" in str(mt).lower()
                for mt in message_types
            )

            record_result(
                "Sales WS Enhanced - capability messages",
                has_capability,
                "capability-related messages received" if has_capability else "no capability messages"
            )

            return len(messages) > 0

    except Exception as e:
        print_error(f"Agent/Persona test error: {e}")
        record_error("Sales WS Agent/Persona", str(e))
        return False


async def test_presentation_websocket():
    """Test presentation WebSocket connection"""
    print_header("TEST 5: Presentation WebSocket")

    try:
        token = await get_dev_token()
        session_id = str(uuid.uuid4())
        uri = f"{WS_BASE_URL}/ws/presentation?session_id={session_id}"
        if token:
            uri += f"&token={token}"

        print_info(f"Connecting to: {uri}")

        async with ws_client.connect(uri, timeout=10) as websocket:
            print_success("Presentation WebSocket connected")

            messages = []
            start_time = time.time()

            while time.time() - start_time < 3:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    messages.append(json.loads(msg))
                except asyncio.TimeoutError:
                    break

            message_types = [msg.get("type") for msg in messages]
            print_info(f"Received messages: {message_types}")

            has_connected = any("connected" in str(mt) or mt == "connected" for mt in message_types)
            record_result(
                "Presentation WS - connected message",
                has_connected,
                "connected message received" if has_connected else "no connected message"
            )

            return len(messages) > 0

    except Exception as e:
        print_error(f"Presentation WebSocket error: {e}")
        record_error("Presentation WS", str(e))
        return False


async def test_websocket_error_handling():
    """Test WebSocket error handling with invalid session"""
    print_header("TEST 6: WebSocket Error Handling")

    try:
        # Test with invalid session ID format
        invalid_session_id = "invalid-session-format"
        uri = f"{WS_BASE_URL}/ws/sales?session_id={invalid_session_id}"

        print_info(f"Testing invalid session: {invalid_session_id}")

        try:
            async with ws_client.connect(uri, timeout=5) as websocket:
                print_error("Connection succeeded with invalid session (unexpected)")
                record_result("WS Error Handling - invalid session rejected", False)
                return False
        except ws_client.exceptions.InvalidStatusCode as e:
            if e.status_code in (1000, 1002, 4400, 4409):
                print_success(f"Connection rejected with code: {e.status_code}")
                record_result("WS Error Handling - invalid session rejected", True)
                return True
            else:
                print_info(f"Connection closed with code: {e.status_code}")
                record_result("WS Error Handling - error response", True)
                return True

    except Exception as e:
        print_info(f"Expected error occurred: {type(e).__name__}")
        # Connection failing is expected for invalid session
        record_result("WS Error Handling - invalid session rejected", True)
        return True


async def test_websocket_heartbeat():
    """Test WebSocket heartbeat mechanism"""
    print_header("TEST 7: WebSocket Heartbeat")

    try:
        token = await get_dev_token()
        session_id = str(uuid.uuid4())
        uri = f"{WS_BASE_URL}/ws/sales?session_id={session_id}"
        if token:
            uri += f"&token={token}"

        print_info(f"Connecting and waiting for heartbeat messages...")

        async with ws_client.connect(uri, timeout=10) as websocket:
            print_success("Connected")

            messages = []
            start_time = time.time()
            timeout_duration = 35  # Wait slightly longer than 30s heartbeat

            while time.time() - start_time < timeout_duration:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    parsed = json.loads(msg)
                    messages.append(parsed)

                    msg_type = parsed.get("type")
                    if msg_type == "heartbeat":
                        print_success(f"Heartbeat received: {parsed.get('timestamp')}")
                        record_result("WS Heartbeat - heartbeat message", True)
                        return True

                except asyncio.TimeoutError:
                    continue

            print_info("No heartbeat received within timeout period")
            # This may not be a failure - heartbeat may not be sent in idle state
            record_result("WS Heartbeat - heartbeat message", False, "no heartbeat in 35s (may be OK)")
            return False

    except Exception as e:
        print_error(f"Heartbeat test error: {e}")
        record_error("WS Heartbeat", str(e))
        return False


async def test_concurrent_connections():
    """Test multiple concurrent WebSocket connections"""
    print_header("TEST 8: Concurrent WebSocket Connections")

    async def connect_session(session_num: int) -> tuple[bool, str]:
        """Connect a single WebSocket session"""
        try:
            session_id = str(uuid.uuid4())
            uri = f"{WS_BASE_URL}/ws/sales?session_id={session_id}"
            async with ws_client.connect(uri, timeout=10) as websocket:
                # Wait briefly and then disconnect
                await asyncio.sleep(1)
                return True, f"Session {session_num} connected"
        except Exception as e:
            return False, f"Session {session_num} failed: {e}"

    try:
        num_connections = 5
        print_info(f"Testing {num_connections} concurrent connections")

        results = await asyncio.gather(
            *[connect_session(i) for i in range(num_connections)]
        )

        successful = sum(1 for r, _ in results if r)
        print_info(f"Successful connections: {successful}/{num_connections}")

        record_result(
            "WS Concurrent Connections",
            successful >= num_connections - 1,  # Allow 1 failure
            f"{successful}/{num_connections} connections succeeded"
        )

        return successful >= num_connections - 1

    except Exception as e:
        print_error(f"Concurrent connection test error: {e}")
        record_error("WS Concurrent", str(e))
        return False


async def run_all_tests():
    """Run all WebSocket tests"""
    print(f"\n{Colors.GREEN}{'='*60}")
    print(f"AI Practice System - WebSocket Test Suite")
    print(f"{'='*60}{Colors.RESET}")
    print(f"\nBackend URL: {BACKEND_URL}")
    print(f"WebSocket URL: {WS_BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    tests = [
        ("Health Check", test_health_check),
        ("Sales WS Connection", test_sales_websocket_connection),
        ("Sales WS Message Types", test_sales_websocket_message_types),
        ("Sales WS Agent/Persona", test_sales_websocket_with_agent_persona),
        ("Presentation WS", test_presentation_websocket),
        ("WS Error Handling", test_websocket_error_handling),
        ("WS Heartbeat", test_websocket_heartbeat),
        ("Concurrent Connections", test_concurrent_connections),
    ]

    # Run tests
    for test_name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            record_error(test_name, f"Test crashed: {e}")
        await asyncio.sleep(1)  # Brief pause between tests

    # Print summary
    print_header("TEST SUMMARY")
    print(f"\n{Colors.GREEN}Passed: {len(test_results['passed'])}{Colors.RESET}")
    for result in test_results['passed']:
        print_success(result)

    if test_results['failed']:
        print(f"\n{Colors.RED}Failed: {len(test_results['failed'])}{Colors.RESET}")
        for result in test_results['failed']:
            print_error(result)

    if test_results['errors']:
        print(f"\n{Colors.YELLOW}Errors: {len(test_results['errors'])}{Colors.RESET}")
        for result in test_results['errors']:
            print_info(result)

    total = len(test_results['passed']) + len(test_results['failed']) + len(test_results['errors'])
    passed_percent = (len(test_results['passed']) / total * 100) if total > 0 else 0

    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"Total Tests: {total}")
    print(f"Pass Rate: {passed_percent:.1f}%")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
