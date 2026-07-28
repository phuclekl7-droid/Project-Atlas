"""
Unit tests for Model Sliders (Model Parameters).

Tests:
- get_model_params returns defaults when not set
- get_model_params reads from session_state
- validate_params clamps temperature (0.0-2.0)
- validate_params clamps top_p (0.0-1.0)
- validate_params clamps max_tokens (100-8000)
- validate_params handles missing keys
- validate_params handles non-numeric values
- Preset buttons logic
"""

import pytest

from ui.model_sliders import get_model_params, validate_params
from ui.model_sliders import render_model_sliders


class TestGetModelParams:
    def test_defaults_when_not_set(self):
        """When session_state has no model_params, should return defaults."""
        # Simulate empty session_state
        import streamlit as st
        if "model_params" in st.session_state:
            del st.session_state["model_params"]

        params = get_model_params()
        assert params["temperature"] == 0.7
        assert params["top_p"] == 0.9
        assert params["max_tokens"] == 2048

    def test_reads_from_session(self):
        import streamlit as st
        st.session_state["model_params"] = {
            "temperature": 0.5,
            "top_p": 0.8,
            "max_tokens": 1000,
        }
        params = get_model_params()
        assert params["temperature"] == 0.5
        assert params["top_p"] == 0.8
        assert params["max_tokens"] == 1000

    def test_partial_params(self):
        import streamlit as st
        st.session_state["model_params"] = {"temperature": 0.3}
        params = get_model_params()
        assert params["temperature"] == 0.3
        assert params["top_p"] == 0.9  # Default
        assert params["max_tokens"] == 2048  # Default


class TestValidateParams:
    def test_valid_values(self):
        params = validate_params({"temperature": 0.5, "top_p": 0.7, "max_tokens": 1500})
        assert params["temperature"] == 0.5
        assert params["top_p"] == 0.7
        assert params["max_tokens"] == 1500

    def test_clamp_temperature_low(self):
        params = validate_params({"temperature": -1.0})
        assert params["temperature"] == 0.0

    def test_clamp_temperature_high(self):
        params = validate_params({"temperature": 5.0})
        assert params["temperature"] == 2.0

    def test_clamp_top_p_low(self):
        params = validate_params({"top_p": -0.5})
        assert params["top_p"] == 0.0

    def test_clamp_top_p_high(self):
        params = validate_params({"top_p": 2.0})
        assert params["top_p"] == 1.0

    def test_clamp_max_tokens_low(self):
        params = validate_params({"max_tokens": 10})
        assert params["max_tokens"] == 100

    def test_clamp_max_tokens_high(self):
        params = validate_params({"max_tokens": 99999})
        assert params["max_tokens"] == 8000

    def test_missing_keys_use_defaults(self):
        params = validate_params({})
        assert params["temperature"] == 0.7
        assert params["top_p"] == 0.9
        assert params["max_tokens"] == 2048

    def test_string_inputs(self):
        """String values should be converted to numbers."""
        params = validate_params({"temperature": "1.5", "top_p": "0.5", "max_tokens": "3000"})
        assert params["temperature"] == 1.5
        assert params["top_p"] == 0.5
        assert params["max_tokens"] == 3000

    def test_all_defaults(self):
        params = validate_params({"temperature": 0.7, "top_p": 0.9, "max_tokens": 2048})
        assert params["temperature"] == 0.7
        assert params["top_p"] == 0.9
        assert params["max_tokens"] == 2048


class TestPresets:
    def test_precise_preset(self):
        """Precise preset should use low temperature."""
        import streamlit as st
        st.session_state["model_params"] = {"temperature": 0.1, "top_p": 0.3, "max_tokens": 1024}
        params = get_model_params()
        assert params["temperature"] == 0.1
        assert params["top_p"] == 0.3
        assert params["max_tokens"] == 1024

    def test_creative_preset(self):
        """Creative preset should use high temperature."""
        import streamlit as st
        st.session_state["model_params"] = {"temperature": 1.5, "top_p": 0.95, "max_tokens": 4096}
        params = get_model_params()
        assert params["temperature"] == 1.5
        assert params["top_p"] == 0.95
        assert params["max_tokens"] == 4096
