"""DCL recipe self-checks — the injector discipline:

each recipe breaks a known-green capability with its NAMED compiler error, by EXACTLY its
one intended edit (minimal diff), deterministically; a missing anchor raises loudly.
"""

from __future__ import annotations

import shutil

import pytest

from dcl import checker, recipes
from dcl.recipes import AnchorNotFound, apply_recipe, verify_breaks

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

# A rich known-green capability carrying every recipe's anchor (retry+idempotency, a
# renameable concern, a policy family, a lifecycle begin, a when branch, an actor-bound intent).
CANONICAL = """language dcl 1.0

actor Customer is human

shape OrderInput {
  orderId: Uuid required
  notes: Text
}

event OrderPlaced is {
  orderId: Uuid required
}

effect PersistOrder is persistence

policy OrderReliability {
  reliability {
    timeout 5 seconds
    idempotency required
    retry { attempts 3 backoff exponential }
  }
}

capability PlaceOrder {
  intent OrderInput from Customer
  outcomes {
    Accepted
    Rejected
  }
  rules {
    ValidTotal: total above 0
  }
  effects {
    PersistOrder
  }
  events {
    emits OrderPlaced
  }
  policies {
    OrderReliability governs capability
  }
  observe {
    capability duration as place_order_duration
  }
  lifecycle {
    begin step Started
    end step Completed
    step Started {
      kind active
    }
    move Started to Completed on outcome Accepted
  }
  when {
    ValidTotal violated then Rejected
    otherwise then Accepted
  }
}
"""


def test_recipe_count_and_ids():
    assert len(recipes.RECIPES) == 10
    for rid, r in recipes.RECIPES.items():
        assert r.id == rid
        assert r.defect_class and r.expected_error_code.startswith("DCL_")


@requires_node
def test_canonical_base_compiles_clean():
    assert checker.compiles_clean(CANONICAL)


@requires_node
@pytest.mark.parametrize("recipe_id", sorted(recipes.RECIPES))
def test_recipe_breaks_with_named_code_minimal_diff(recipe_id):
    result = apply_recipe(CANONICAL, recipe_id)
    # exactly the intended edit — a single-line substitution (2) or removal (1)
    assert result.broken_text != CANONICAL
    assert 1 <= result.changed_line_count <= 2
    assert result.diff
    # deterministic
    assert apply_recipe(CANONICAL, recipe_id).broken_text == result.broken_text
    # the real compiler REJECTS it with the recipe's named code
    compiled = verify_breaks(result)
    assert not compiled.ok
    assert result.expected_error_code in compiled.error_codes


def test_apply_recipe_is_pure_without_node():
    # apply_recipe does no compiler call — safe to run anywhere.
    result = apply_recipe(CANONICAL, "R-actor-kind")
    assert "is machine" in result.broken_text
    assert "is human" not in result.broken_text.split("\n")[2]


def test_missing_anchor_raises_loudly():
    no_retry = CANONICAL.replace("    retry { attempts 3 backoff exponential }\n", "")
    with pytest.raises(AnchorNotFound):
        apply_recipe(no_retry, "R-retry-no-idempotency")


def test_missing_anchor_actor_raises():
    with pytest.raises(AnchorNotFound):
        apply_recipe("language dcl 1.0\n", "R-actor-kind")


def test_unknown_recipe_raises_keyerror():
    with pytest.raises(KeyError):
        apply_recipe(CANONICAL, "R-NOPE")


@requires_node
def test_verify_breaks_rejects_a_clean_mutation(monkeypatch):
    # A recipe whose "broken" text still compiles must fail the self-check.
    from dcl.recipes import BrokenResult

    fake = BrokenResult(
        recipe_id="R-actor-kind", defect_class="x", expected_error_code="DCL_SEM_ACTOR_KIND_UNKNOWN",
        source_text=CANONICAL, broken_text=CANONICAL, diff="x", changed_line_count=1,
    )
    with pytest.raises(recipes.RecipeSelfCheckError):
        verify_breaks(fake)
