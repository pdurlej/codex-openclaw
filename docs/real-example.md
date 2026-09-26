[Home](../README.md) · [Documentation](README.md)

# A real feedback loop: improving this README

On 26 September 2026, we used OpenClaw Bridge to review its own public
README with Iskra, the maintainer’s OpenClaw agent. This is an actual
documentation workflow, not a simulated coding demo. Excerpts below are
shortened English translations of the Polish conversation.

## 1. Codex asks

> Does the plugin’s value come across? Does the README invite people to try it?
> What are the three most important improvements?

Codex sent the current README, the public repository URL, and the v1 scope
through `openclaw_ask`, then retrieved the answer with `openclaw_collect`.
It did not send credentials or personal connection settings.

## 2. The agent gives feedback

> The idea works, and the page finally talks about the benefit rather than
> the mechanism. The most valuable part is the loop: question → acceptance
> example → test → return with the result.

Iskra suggested a real before/after example, a clearer context boundary,
and a four-step first conversation. She reported reading the public README
and two documentation pages. She explicitly did **not** claim to have
installed the plugin or verified its runtime.

## 3. Codex changes the docs

| Before | After |
| --- | --- |
| A suggested prompt, without a completed example | This exchange, the changes it produced, and verification results |
| “Your OpenClaw agent brings its available context and preferences” | A note explaining selected question context, the agent’s own memory/tools, and what is not automatically shared |
| Setup commands in a long sequence | Four numbered steps: get the plugin, connect, check and install, ask |

The user approved implementing the feedback. Codex edited the documentation;
Iskra’s reply did not itself authorize changes. No live agent configuration
or runtime behavior was changed for this example.

## 4. Verify and follow up

Codex ran these **local documentation/package checks** on the updated files:

- All 38 local links, image references, and heading anchors resolved.
- The getting-started guide contained exactly four numbered setup steps.
- The existing package validator and `git diff --check` passed.

Codex sent the changes and these results back through the bridge, preserving
the same conversation. Iskra replied:

> As described, these changes address all three comments. It is especially good
> that the real example concerns documentation and does not pretend to test
> whether the plugin works.

She also qualified her assessment: she had not seen the new diff or rendered
page and was evaluating Codex’s description. She asked that the checks above
be labeled as local documentation checks, **not proof of installation or the
full user path**. We kept that distinction here.

The ask and follow-up produced real responses through the bridge. This exercise
did not repeat a fresh installation, validate a deployment, or measure cost
savings. It demonstrates the consultation loop and the resulting documentation
change.

## Try the same loop

> Ask my OpenClaw agent to review this change for unclear behavior and missing
> acceptance cases. Implement the changes I approve, verify them, and return
> to the same conversation with the observed results.

For code or personalization changes, replace documentation checks with the
relevant tests and exercise the actual deployed user path. An agent’s opinion
is useful feedback; it does not establish that the change works in production.
