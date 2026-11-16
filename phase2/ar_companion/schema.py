from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Evidence(Strict):
    kind: Literal['manual', 'project_policy']
    pdf_page: int | None = Field(default=None, ge=1)
    region: list[float] | None = None
    policy_id: Literal['unplugged_only_v1'] | None = None

    @model_validator(mode='after')
    def check(self):
        if self.kind == 'manual':
            if not self.pdf_page or not self.region or len(self.region) != 4:
                raise ValueError('Manual evidence needs a page and normalized [left,top,right,bottom] region')
            a,b,c,d = self.region
            if not (0 <= a < c <= 1 and 0 <= b < d <= 1):
                raise ValueError('Invalid source region')
            if self.policy_id:
                raise ValueError('Manual evidence cannot impersonate project policy')
        elif self.policy_id != 'unplugged_only_v1' or self.pdf_page or self.region:
            raise ValueError('Project safety evidence must use the fixed policy ID')
        return self


class Part(Strict):
    part_id: str = Field(pattern=r'^[a-z][a-z0-9_]{1,63}$')
    name: str = Field(min_length=2, max_length=150)
    aliases: list[str] = Field(default_factory=list, max_length=12)
    reference_image: str | None = None
    diagram_label: str | None = None


class Cause(Strict):
    cause_id: str = Field(pattern=r'^[a-z][a-z0-9_]{1,63}$')
    description: str = Field(min_length=5, max_length=500)
    confirmation_question: str = Field(min_length=5, max_length=500)


class Step(Strict):
    step_id: str = Field(pattern=r'^s[0-9]+$')
    part_id: str
    action: Literal['unplug', 'confirm_cool', 'fill', 'seat', 'clean', 'rotate', 'empty', 'inspect', 'remove', 'replace']
    instruction: str = Field(min_length=5, max_length=1000)
    cause_ids: list[str] = Field(default_factory=list)
    source: Evidence
    reference_image: str | None = None
    preconditions: list[str] = Field(min_length=1)
    completion_mode: Literal['tap'] = 'tap'
    completion_condition: str = Field(min_length=5, max_length=500)
    safety_class: Literal['project_safety', 'unpowered_external']


SAFETY = [
    dict(step_id='s1', part_id='power_plug', action='unplug',
         instruction='Unplug the machine.', cause_ids=[],
         source={'kind':'project_policy','policy_id':'unplugged_only_v1'},
         preconditions=['Machine is off and idle; no active pressure or steam cycle.'],
         completion_condition='User confirms the plug is disconnected.', safety_class='project_safety'),
    dict(step_id='s2', part_id='machine', action='confirm_cool',
         instruction='Wait until the machine and removable parts are cool before handling them.', cause_ids=[],
         source={'kind':'project_policy','policy_id':'unplugged_only_v1'},
         preconditions=['Machine is unplugged.'],
         completion_condition='User confirms the machine and parts are cool.', safety_class='project_safety'),
]


class Procedure(Strict):
    appliance_id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{1,79}$')
    manual_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    procedure_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    procedure_version: int = Field(default=1, ge=1)
    status: Literal['draft', 'published'] = 'draft'
    reviewer: str | None = None
    reviewed_at: str | None = None
    symptom: str = Field(min_length=5, max_length=500)
    symptom_aliases: list[str] = Field(default_factory=list, max_length=20)
    causes: list[Cause] = Field(min_length=1, max_length=20)
    parts: list[Part] = Field(min_length=1, max_length=40)
    steps: list[Step] = Field(min_length=3, max_length=40)
    scope_note: str = Field(min_length=10, max_length=1500)
    entry_condition: Literal['Machine is off and idle; no active pressure or steam cycle.'] = 'Machine is off and idle; no active pressure or steam cycle.'
    result_label: Literal['Intervention completed; outcome unverified.'] = 'Intervention completed; outcome unverified.'

    @model_validator(mode='after')
    def check(self):
        for items, attr in [(self.parts,'part_id'),(self.causes,'cause_id'),(self.steps,'step_id')]:
            ids=[getattr(x,attr) for x in items]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate '+attr)
        if [s.step_id for s in self.steps] != [f's{i+1}' for i in range(len(self.steps))]:
            raise ValueError('Steps must be consecutively ordered from s1')
        for actual, expected in zip(self.steps[:2], SAFETY):
            if actual.model_dump() != Step(**expected).model_dump():
                raise ValueError('The two mandatory project safety steps cannot be edited')
        parts={p.part_id for p in self.parts}
        causes={c.cause_id for c in self.causes}
        covered=set()
        for s in self.steps:
            if s.part_id not in parts or not set(s.cause_ids) <= causes:
                raise ValueError('Unknown part or cause')
            if s.step_id not in ['s1','s2']:
                if s.source.kind != 'manual' or s.safety_class != 'unpowered_external' or not s.cause_ids:
                    raise ValueError('Physical actions need manual evidence and explicit cause branches')
                if not {'unplugged','cool'} <= set(s.preconditions):
                    raise ValueError('Physical actions need unplugged and cool preconditions')
                covered.update(s.cause_ids)
        if covered != causes:
            raise ValueError('Every cause must have a supported step')
        if self.status == 'published' and (not self.reviewer or not self.reviewed_at):
            raise ValueError('Published procedures require a review record')
        if self.status == 'draft' and (self.reviewer or self.reviewed_at):
            raise ValueError('Drafts cannot claim review approval')
        return self


class DraftBundle(Strict):
    procedures: list[Procedure] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def unique(self):
        ids=[p.procedure_id for p in self.procedures]
        if len(set(ids)) != len(ids):
            raise ValueError('Duplicate procedure IDs')
        return self
