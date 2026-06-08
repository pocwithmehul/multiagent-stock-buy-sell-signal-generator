"""Tests for AgenticAIBase class."""

import pytest
from datetime import datetime, timezone
from agentic_ai_base import AgenticAIBase


class ConcreteAgent(AgenticAIBase):
    """Concrete implementation for testing."""

    def __init__(self):
        super().__init__()
        self.register_tool("sample_tool", self._sample_tool, "A sample tool")
        self.register_tool("tool_with_args", self._tool_with_args, "Tool with arguments")

    def _sample_tool(self):
        return {"result": "success"}

    def _tool_with_args(self, arg1, arg2="default"):
        return {"arg1": arg1, "arg2": arg2}

    def plan(self):
        self._state["plan"] = ["Step 1", "Step 2", "Step 3"]

    def perceive(self):
        self._state["data"]["perceived"] = self.use_tool("sample_tool")

    def reason(self):
        self._state["reasoning"] = {"conclusion": "analyzed"}

    def act(self):
        self._state["actions"] = {"action": "completed"}


class TestAgenticAIBase:
    """Test suite for AgenticAIBase."""

    def test_init_state(self):
        """Test initial state is properly set."""
        agent = ConcreteAgent()
        state = agent.get_state()

        assert state["phase"] == "initialized"
        assert state["data"] == {}
        assert state["reasoning"] == {}
        assert state["actions"] == {}
        assert state["plan"] == []
        assert state["tool_log"] == []

    def test_register_tool(self):
        """Test tool registration."""
        agent = ConcreteAgent()

        assert "sample_tool" in agent._tools
        assert "tool_with_args" in agent._tools
        assert agent._tools["sample_tool"]["description"] == "A sample tool"

    def test_use_tool(self):
        """Test using a registered tool."""
        agent = ConcreteAgent()
        result = agent.use_tool("sample_tool")

        assert result == {"result": "success"}
        assert len(agent._state["tool_log"]) == 1
        assert agent._state["tool_log"][0]["tool"] == "sample_tool"

    def test_use_tool_with_args(self):
        """Test using a tool with arguments."""
        agent = ConcreteAgent()
        result = agent.use_tool("tool_with_args", arg1="value1", arg2="value2")

        assert result == {"arg1": "value1", "arg2": "value2"}

    def test_use_tool_with_default_args(self):
        """Test using a tool with default arguments."""
        agent = ConcreteAgent()
        result = agent.use_tool("tool_with_args", arg1="value1")

        assert result == {"arg1": "value1", "arg2": "default"}

    def test_use_unregistered_tool_raises(self):
        """Test that using an unregistered tool raises ValueError."""
        agent = ConcreteAgent()

        with pytest.raises(ValueError, match="Tool 'nonexistent' is not registered"):
            agent.use_tool("nonexistent")

    def test_tool_log_timestamp(self):
        """Test that tool log includes timestamp."""
        agent = ConcreteAgent()
        agent.use_tool("sample_tool")

        log_entry = agent._state["tool_log"][0]
        assert "timestamp" in log_entry
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(log_entry["timestamp"].replace("Z", "+00:00"))

    def test_plan_phase(self):
        """Test plan phase."""
        agent = ConcreteAgent()
        agent.plan()

        assert agent._state["plan"] == ["Step 1", "Step 2", "Step 3"]

    def test_perceive_phase(self):
        """Test perceive phase."""
        agent = ConcreteAgent()
        agent.perceive()

        assert agent._state["data"]["perceived"] == {"result": "success"}

    def test_reason_phase(self):
        """Test reason phase."""
        agent = ConcreteAgent()
        agent.reason()

        assert agent._state["reasoning"] == {"conclusion": "analyzed"}

    def test_act_phase(self):
        """Test act phase."""
        agent = ConcreteAgent()
        agent.act()

        assert agent._state["actions"] == {"action": "completed"}

    def test_execute_full_lifecycle(self):
        """Test the full execute lifecycle."""
        agent = ConcreteAgent()
        result = agent.execute()

        assert result["phase"] == "completed"
        assert result["plan"] == ["Step 1", "Step 2", "Step 3"]
        assert result["data"]["perceived"] == {"result": "success"}
        assert result["reasoning"] == {"conclusion": "analyzed"}
        assert result["actions"] == {"action": "completed"}

    def test_execute_phase_transitions(self):
        """Test that execute transitions through all phases."""
        agent = ConcreteAgent()
        phases_seen = []

        original_plan = agent.plan
        original_perceive = agent.perceive
        original_reason = agent.reason
        original_act = agent.act

        def track_plan():
            phases_seen.append(agent._state["phase"])
            original_plan()

        def track_perceive():
            phases_seen.append(agent._state["phase"])
            original_perceive()

        def track_reason():
            phases_seen.append(agent._state["phase"])
            original_reason()

        def track_act():
            phases_seen.append(agent._state["phase"])
            original_act()

        agent.plan = track_plan
        agent.perceive = track_perceive
        agent.reason = track_reason
        agent.act = track_act

        agent.execute()

        assert phases_seen == ["planning", "perceiving", "reasoning", "acting"]

    def test_get_state_returns_copy(self):
        """Test that get_state returns a copy of state."""
        agent = ConcreteAgent()
        state1 = agent.get_state()
        state1["custom"] = "value"
        state2 = agent.get_state()

        assert "custom" not in state2

    def test_reset(self):
        """Test reset clears state."""
        agent = ConcreteAgent()
        agent.execute()

        # Verify state has data
        assert agent._state["phase"] == "completed"
        assert len(agent._state["tool_log"]) > 0

        agent.reset()

        assert agent._state["phase"] == "initialized"
        assert agent._state["data"] == {}
        assert agent._state["reasoning"] == {}
        assert agent._state["actions"] == {}
        assert agent._state["plan"] == []
        assert agent._state["tool_log"] == []

    def test_multiple_tool_calls(self):
        """Test multiple tool calls are logged."""
        agent = ConcreteAgent()
        agent.use_tool("sample_tool")
        agent.use_tool("sample_tool")
        agent.use_tool("tool_with_args", arg1="test")

        assert len(agent._state["tool_log"]) == 3

    def test_tool_kwargs_logged(self):
        """Test that tool kwargs are logged."""
        agent = ConcreteAgent()
        agent.use_tool("tool_with_args", arg1="val1", arg2="val2")

        log_entry = agent._state["tool_log"][0]
        assert log_entry["kwargs"] == {"arg1": "val1", "arg2": "val2"}


class TestDebugLogging:
    """Test debug logging methods."""

    def test_is_debug_false_by_default(self):
        """Test _is_debug returns False by default."""
        import os
        # Clear any DEBUG env var
        os.environ.pop("DEBUG", None)

        agent = ConcreteAgent()
        assert agent._is_debug() is False

    def test_is_debug_true_when_set(self):
        """Test _is_debug returns True when DEBUG is set."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            assert agent._is_debug() is True
        finally:
            os.environ.pop("DEBUG", None)

    def test_is_debug_with_yes(self):
        """Test _is_debug with 'yes' value."""
        import os
        os.environ["DEBUG"] = "yes"

        try:
            agent = ConcreteAgent()
            assert agent._is_debug() is True
        finally:
            os.environ.pop("DEBUG", None)

    def test_is_debug_with_1(self):
        """Test _is_debug with '1' value."""
        import os
        os.environ["DEBUG"] = "1"

        try:
            agent = ConcreteAgent()
            assert agent._is_debug() is True
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_does_nothing_when_disabled(self):
        """Test debug_log does nothing when DEBUG is disabled."""
        import os
        os.environ.pop("DEBUG", None)

        agent = ConcreteAgent()
        # Should not raise
        agent.debug_log("Test", {"data": "value"})

    def test_debug_log_with_dict(self):
        """Test debug_log with dictionary data."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            # Should not raise
            agent.debug_log("Test Data", {"key": "value", "number": 123})
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_with_custom_agent_name(self):
        """Test debug_log with custom agent name."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            agent.debug_log("Test Data", {"key": "value"}, agent_name="CustomAgent")
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_with_pandas_dataframe(self):
        """Test debug_log with pandas DataFrame."""
        import os
        import pandas as pd
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
            agent.debug_log("DataFrame", df)
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_with_pydantic_model(self):
        """Test debug_log with Pydantic model."""
        import os
        from pydantic import BaseModel
        os.environ["DEBUG"] = "true"

        class TestModel(BaseModel):
            field: str = "value"

        try:
            agent = ConcreteAgent()
            model = TestModel()
            agent.debug_log("Model", model)
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_with_non_serializable(self):
        """Test debug_log with non-JSON-serializable data that triggers fallback."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            # Create an object that causes json.dumps to fail with TypeError
            # and triggers the except branch (lines 59-61)
            class FailsJsonDumps:
                def __repr__(self):
                    return "FailsJsonDumps()"

            # This object will fail json serialization because it's not serializable
            agent.debug_log("Non-serializable", FailsJsonDumps())
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_triggers_except_branch(self):
        """Test debug_log fallback when json.dumps raises TypeError."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            # Create a circular reference which causes json to fail
            circular = {}
            circular["self"] = circular
            agent.debug_log("Circular", circular)
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_no_data_when_disabled(self):
        """Test debug_log_no_data does nothing when DEBUG is disabled."""
        import os
        os.environ.pop("DEBUG", None)

        agent = ConcreteAgent()
        # Should not raise
        agent.debug_log_no_data("Source", "Reason")

    def test_debug_log_no_data_when_enabled(self):
        """Test debug_log_no_data when DEBUG is enabled."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            agent.debug_log_no_data("TestSource", "Data not available")
        finally:
            os.environ.pop("DEBUG", None)

    def test_debug_log_no_data_with_custom_agent_name(self):
        """Test debug_log_no_data with custom agent name."""
        import os
        os.environ["DEBUG"] = "true"

        try:
            agent = ConcreteAgent()
            agent.debug_log_no_data("Source", "Reason", agent_name="MyAgent")
        finally:
            os.environ.pop("DEBUG", None)
