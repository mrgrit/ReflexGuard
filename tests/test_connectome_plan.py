"""Reject mixed releases, unapproved origins and unearned loading claims."""
import pytest
from pydantic import ValidationError
from reflexguard.common.connectome import MaleCNSPlan


def test_malecns_plan_is_explicitly_not_downloaded():
    plan=MaleCNSPlan.load()
    assert plan.state=="planned_not_downloaded"
    assert plan.neuprint_dataset=="male-cns:"+plan.release


@pytest.mark.parametrize("change", [
    {"release":"v0.9"}, {"neuprint_dataset":"unrelated:v1"},
    {"neuprint_server":"https://untrusted.invalid"}, {"bucket":"gs://other-bucket/"},
    {"annotations":"body-annotations-male-cns-v0.9-minconf-0.5.feather"},
    {"connectivity":"body-neurotransmitters-male-cns-v1.0.feather"},
    {"state":"loaded"}, {"weights_sha256":"0"*64},
])
def test_invalid_or_misleading_provenance_rejected(change):
    data=MaleCNSPlan.load().model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        MaleCNSPlan(**data)
