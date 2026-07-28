import psycopg
import pytest
from pydantic import ValidationError

from app.agents.trustee_compliance_reporting import WORKFLOW_YAML_PATH
from app.core.config import settings
from app.platform.runtime.loader import load_workflow_config, register_workflow
from app.platform.schema.workflow_config import WorkflowConfig


def test_trustee_compliance_yaml_validates_against_schema():
    config = load_workflow_config(WORKFLOW_YAML_PATH)
    assert isinstance(config, WorkflowConfig)
    assert config.name == "trustee_compliance_reporting"
    assert [node.name for node in config.nodes] == [
        "aggregation",
        "compliance_check",
        "reporting",
        "approval_gate",
        "finalize",
    ]


def test_invalid_node_type_is_rejected():
    with pytest.raises(ValidationError):
        WorkflowConfig.model_validate(
            {
                "name": "broken",
                "description": "x",
                "state_keys": ["report"],
                "nodes": [{"name": "n1", "type": "not_a_real_type"}],
            }
        )


def test_loading_workflow_registers_it_in_agent_registry():
    config = load_workflow_config(WORKFLOW_YAML_PATH)
    register_workflow(config)

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, version, config FROM agent_registry WHERE name = %s;",
                (config.name,),
            )
            row = cur.fetchone()

    assert row is not None
    name, version, stored_config = row
    assert name == "trustee_compliance_reporting"
    assert version == config.version
    assert stored_config["name"] == config.name
    assert len(stored_config["nodes"]) == len(config.nodes)
