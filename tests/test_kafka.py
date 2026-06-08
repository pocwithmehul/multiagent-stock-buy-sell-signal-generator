"""Tests for Kafka producer and consumer wrappers."""

import pytest
from unittest.mock import patch, MagicMock
import json
import sys


@pytest.fixture(autouse=True)
def mock_kafka_module():
    """Mock the kafka module before importing the wrappers."""
    mock_kafka = MagicMock()
    mock_kafka.KafkaProducer = MagicMock()
    mock_kafka.KafkaConsumer = MagicMock()
    sys.modules['kafka'] = mock_kafka
    yield mock_kafka
    # Clean up
    if 'kafka' in sys.modules:
        del sys.modules['kafka']
    # Also clean up the infrastructure modules to force reimport
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith('infrastructure.kafka'):
            del sys.modules[mod_name]


class TestKafkaProducerWrapper:
    """Test suite for KafkaProducerWrapper."""

    def test_init_default_servers(self, mock_kafka_module):
        """Test initialization with default bootstrap servers."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()

        assert wrapper.bootstrap_servers == "localhost:9092"
        mock_kafka_module.KafkaProducer.assert_called_once()

    def test_init_custom_servers(self, mock_kafka_module):
        """Test initialization with custom bootstrap servers."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper(bootstrap_servers="kafka:9093")

        assert wrapper.bootstrap_servers == "kafka:9093"

    def test_send(self, mock_kafka_module):
        """Test send method."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()
        wrapper.send("test-topic", "test-key", "test-value")

        mock_producer.send.assert_called_once_with(
            "test-topic",
            key="test-key",
            value="test-value"
        )

    def test_send_multiple_messages(self, mock_kafka_module):
        """Test sending multiple messages."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()
        wrapper.send("topic1", "key1", "value1")
        wrapper.send("topic2", "key2", "value2")
        wrapper.send("topic1", "key3", "value3")

        assert mock_producer.send.call_count == 3

    def test_flush(self, mock_kafka_module):
        """Test flush method."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()
        wrapper.flush()

        mock_producer.flush.assert_called_once()

    def test_close(self, mock_kafka_module):
        """Test close method."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()
        wrapper.close()

        mock_producer.flush.assert_called_once()
        mock_producer.close.assert_called_once()

    def test_close_flushes_before_closing(self, mock_kafka_module):
        """Test that close flushes messages before closing."""
        mock_producer = MagicMock()
        call_order = []
        mock_producer.flush.side_effect = lambda: call_order.append('flush')
        mock_producer.close.side_effect = lambda: call_order.append('close')
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()
        wrapper.close()

        assert call_order == ['flush', 'close']

    def test_serializers(self, mock_kafka_module):
        """Test that serializers are properly configured."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        KafkaProducerWrapper()

        # Check that serializers were passed
        call_kwargs = mock_kafka_module.KafkaProducer.call_args.kwargs
        assert "value_serializer" in call_kwargs
        assert "key_serializer" in call_kwargs

        # Test the serializers work correctly
        value_serializer = call_kwargs["value_serializer"]
        key_serializer = call_kwargs["key_serializer"]

        assert value_serializer("test") == b"test"
        assert key_serializer("key") == b"key"

    def test_value_serializer_with_bytes(self, mock_kafka_module):
        """Test that value serializer handles bytes correctly."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        KafkaProducerWrapper()

        call_kwargs = mock_kafka_module.KafkaProducer.call_args.kwargs
        value_serializer = call_kwargs["value_serializer"]

        # Non-string (bytes) should pass through
        byte_value = b"already bytes"
        assert value_serializer(byte_value) == byte_value

    def test_key_serializer_with_bytes(self, mock_kafka_module):
        """Test that key serializer handles bytes correctly."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        KafkaProducerWrapper()

        call_kwargs = mock_kafka_module.KafkaProducer.call_args.kwargs
        key_serializer = call_kwargs["key_serializer"]

        # Non-string (bytes) should pass through
        byte_key = b"already bytes"
        assert key_serializer(byte_key) == byte_key

    def test_key_serializer_with_none(self, mock_kafka_module):
        """Test that key serializer handles None correctly."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        KafkaProducerWrapper()

        call_kwargs = mock_kafka_module.KafkaProducer.call_args.kwargs
        key_serializer = call_kwargs["key_serializer"]

        # None should pass through (or return None)
        assert key_serializer(None) is None

    def test_send_json_message(self, mock_kafka_module):
        """Test sending JSON serialized message."""
        mock_producer = MagicMock()
        mock_kafka_module.KafkaProducer.return_value = mock_producer

        from infrastructure.kafka_producer import KafkaProducerWrapper
        wrapper = KafkaProducerWrapper()
        json_value = json.dumps({"ticker": "AAPL", "price": 150.0})
        wrapper.send("test-topic", "AAPL", json_value)

        mock_producer.send.assert_called_once_with(
            "test-topic",
            key="AAPL",
            value=json_value
        )


class TestKafkaConsumerWrapper:
    """Test suite for KafkaConsumerWrapper."""

    def test_init_default_servers(self, mock_kafka_module):
        """Test initialization with default settings."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")

        assert wrapper.bootstrap_servers == "localhost:9092"
        assert wrapper.topic == "test-topic"
        mock_kafka_module.KafkaConsumer.assert_called_once()

    def test_init_custom_settings(self, mock_kafka_module):
        """Test initialization with custom settings."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(
            topic="custom-topic",
            bootstrap_servers="kafka:9093",
            group_id="custom-group"
        )

        assert wrapper.bootstrap_servers == "kafka:9093"
        assert wrapper.topic == "custom-topic"

    def test_drain(self, mock_kafka_module):
        """Test drain method."""
        mock_consumer = MagicMock()

        # Create mock messages
        mock_msg1 = MagicMock()
        mock_msg1.key = "key1"
        mock_msg1.value = {"data": 1}
        mock_msg1.topic = "test-topic"
        mock_msg1.partition = 0
        mock_msg1.offset = 0

        mock_msg2 = MagicMock()
        mock_msg2.key = "key2"
        mock_msg2.value = {"data": 2}
        mock_msg2.topic = "test-topic"
        mock_msg2.partition = 0
        mock_msg2.offset = 1

        mock_consumer.__iter__ = MagicMock(return_value=iter([mock_msg1, mock_msg2]))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        messages = wrapper.drain(max_messages=10)

        assert len(messages) == 2
        assert messages[0]["key"] == "key1"
        assert messages[1]["key"] == "key2"

    def test_drain_max_messages(self, mock_kafka_module):
        """Test drain respects max_messages limit."""
        mock_consumer = MagicMock()

        # Create more messages than the limit
        mock_messages = []
        for i in range(10):
            msg = MagicMock()
            msg.key = f"key{i}"
            msg.value = {"data": i}
            msg.topic = "test-topic"
            msg.partition = 0
            msg.offset = i
            mock_messages.append(msg)

        mock_consumer.__iter__ = MagicMock(return_value=iter(mock_messages))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        messages = wrapper.drain(max_messages=3)

        assert len(messages) == 3

    def test_drain_empty_topic(self, mock_kafka_module):
        """Test drain on empty topic returns empty list."""
        mock_consumer = MagicMock()
        mock_consumer.__iter__ = MagicMock(return_value=iter([]))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        messages = wrapper.drain(max_messages=100)

        assert len(messages) == 0
        assert messages == []

    def test_drain_returns_correct_message_structure(self, mock_kafka_module):
        """Test that drain returns messages with correct structure."""
        mock_consumer = MagicMock()

        mock_msg = MagicMock()
        mock_msg.key = "test-key"
        mock_msg.value = {"ticker": "AAPL", "price": 150.0}
        mock_msg.topic = "stock-prices"
        mock_msg.partition = 2
        mock_msg.offset = 42

        mock_consumer.__iter__ = MagicMock(return_value=iter([mock_msg]))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="stock-prices")
        messages = wrapper.drain()

        assert len(messages) == 1
        msg = messages[0]
        assert msg["key"] == "test-key"
        assert msg["value"] == {"ticker": "AAPL", "price": 150.0}
        assert msg["topic"] == "stock-prices"
        assert msg["partition"] == 2
        assert msg["offset"] == 42

    def test_drain_default_max_messages(self, mock_kafka_module):
        """Test drain with default max_messages (1000)."""
        mock_consumer = MagicMock()

        # Create 5 messages (less than default)
        mock_messages = []
        for i in range(5):
            msg = MagicMock()
            msg.key = f"key{i}"
            msg.value = {"data": i}
            msg.topic = "test-topic"
            msg.partition = 0
            msg.offset = i
            mock_messages.append(msg)

        mock_consumer.__iter__ = MagicMock(return_value=iter(mock_messages))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        messages = wrapper.drain()  # Use default max_messages

        assert len(messages) == 5

    def test_close(self, mock_kafka_module):
        """Test close method."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        wrapper.close()

        mock_consumer.close.assert_called_once()

    def test_consumer_config(self, mock_kafka_module):
        """Test consumer configuration."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        KafkaConsumerWrapper(topic="test-topic", group_id="test-group")

        call_args = mock_kafka_module.KafkaConsumer.call_args
        assert call_args.args[0] == "test-topic"
        assert call_args.kwargs["group_id"] == "test-group"
        assert call_args.kwargs["auto_offset_reset"] == "earliest"

    def test_consumer_timeout(self, mock_kafka_module):
        """Test consumer timeout configuration."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        KafkaConsumerWrapper(topic="test-topic")

        call_args = mock_kafka_module.KafkaConsumer.call_args
        assert call_args.kwargs["consumer_timeout_ms"] == 5000

    def test_value_deserializer(self, mock_kafka_module):
        """Test value deserializer is configured correctly."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        KafkaConsumerWrapper(topic="test-topic")

        call_kwargs = mock_kafka_module.KafkaConsumer.call_args.kwargs
        assert "value_deserializer" in call_kwargs

        # Test the deserializer
        deserializer = call_kwargs["value_deserializer"]
        test_data = {"key": "value", "number": 123}
        serialized = json.dumps(test_data).encode("utf-8")
        assert deserializer(serialized) == test_data

    def test_key_deserializer(self, mock_kafka_module):
        """Test key deserializer is configured correctly."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        KafkaConsumerWrapper(topic="test-topic")

        call_kwargs = mock_kafka_module.KafkaConsumer.call_args.kwargs
        assert "key_deserializer" in call_kwargs

        # Test the deserializer with string
        deserializer = call_kwargs["key_deserializer"]
        assert deserializer(b"test-key") == "test-key"

    def test_key_deserializer_with_none(self, mock_kafka_module):
        """Test key deserializer handles None correctly."""
        mock_consumer = MagicMock()
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        KafkaConsumerWrapper(topic="test-topic")

        call_kwargs = mock_kafka_module.KafkaConsumer.call_args.kwargs
        deserializer = call_kwargs["key_deserializer"]

        # None key should return None
        assert deserializer(None) is None

    def test_drain_with_none_key(self, mock_kafka_module):
        """Test drain handles messages with None keys."""
        mock_consumer = MagicMock()

        mock_msg = MagicMock()
        mock_msg.key = None  # None key
        mock_msg.value = {"data": "test"}
        mock_msg.topic = "test-topic"
        mock_msg.partition = 0
        mock_msg.offset = 0

        mock_consumer.__iter__ = MagicMock(return_value=iter([mock_msg]))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        messages = wrapper.drain()

        assert len(messages) == 1
        assert messages[0]["key"] is None
        assert messages[0]["value"] == {"data": "test"}

    def test_drain_multiple_partitions(self, mock_kafka_module):
        """Test drain handles messages from multiple partitions."""
        mock_consumer = MagicMock()

        mock_messages = []
        for i in range(3):
            msg = MagicMock()
            msg.key = f"key{i}"
            msg.value = {"partition": i}
            msg.topic = "test-topic"
            msg.partition = i  # Different partitions
            msg.offset = 0
            mock_messages.append(msg)

        mock_consumer.__iter__ = MagicMock(return_value=iter(mock_messages))
        mock_kafka_module.KafkaConsumer.return_value = mock_consumer

        from infrastructure.kafka_consumer import KafkaConsumerWrapper
        wrapper = KafkaConsumerWrapper(topic="test-topic")
        messages = wrapper.drain()

        assert len(messages) == 3
        partitions = [m["partition"] for m in messages]
        assert partitions == [0, 1, 2]
