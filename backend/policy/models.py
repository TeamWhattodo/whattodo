from pydantic import BaseModel


class HardOverride(BaseModel):
    name: str
    condition: dict
    action: dict


class Guardrail(BaseModel):
    name: str
    condition: dict
    blocks: str
    reason: str


class PolicyConfig(BaseModel):
    company_name: str = ""
    communication_rules: str = ""
    reporting_structure: str = ""
    project_priorities: str = ""
    hard_overrides: list[HardOverride] = []
    guardrails: list[Guardrail] = []
